"""Intentions `pr_open` et `pr_merge` (AD-8, AD-17) et rafraîchissement des PR après le terminal.

Le GitHub simulé (`github_sim`) ne connaît pas la file : ce module la relie à lui. Un refus
connu d'avance (branche absente d'`origin`, PR inconnue ou bloquée) part en 409 dès la
réception de l'intention ; le corps de l'opération revérifie dans la file, où l'état peut avoir
bougé, et dit alors le refus à l'écran du terminal. Chaque PR modifiée émet `pr_updated`.
"""

from __future__ import annotations

import logging
from pathlib import Path

from pydantic import BaseModel, Field

from wavedevsecops import github_sim
from wavedevsecops.engine.intents import INTENTS, Intent, register_intent
from wavedevsecops.engine.operations import (
    OpContext,
    Operation,
    OperationRefused,
    WorkspaceEngine,
)
from wavedevsecops.engine.workspace import resolve_git
from wavedevsecops.events import Kind
from wavedevsecops.github_sim import GithubSimError
from wavedevsecops.gitio import Git, GitError
from wavedevsecops.wsfs import Layout

log = logging.getLogger(__name__)

EXIT_REFUSED = 2
BRANCH = r"^[A-Za-z0-9][A-Za-z0-9._/-]*$"


class PrOpen(BaseModel):
    head: str = Field(max_length=200, pattern=BRANCH)
    base: str = Field(default="main", max_length=200, pattern=BRANCH)
    title_text: str = Field(default="", max_length=200)


class PrMerge(BaseModel):
    number: int = Field(ge=1)


def _git(git_path: Path | None, layout: Layout, settings) -> Git:  # noqa: ANN001
    return Git.for_workspace(git_path or resolve_git(settings), layout.root, settings)


def announce(ctx: OpContext, numbers: list[int]) -> None:
    """Émet `pr_updated` pour chaque PR modifiée."""
    state = github_sim.load(ctx.layout)
    for number in numbers:
        pr = state.pull(number)
        if pr is not None:
            ctx.emit(
                Kind.PR_UPDATED,
                {"number": number, "element_id": pr.element, "state": pr.state},
            )


def _announce_all(ctx: OpContext) -> None:
    """Annonce toutes les PR (recalculées ensemble) ; un état illisible ne fait pas échouer
    une opération déjà faite."""
    try:
        announce(ctx, [p.number for p in github_sim.load(ctx.layout).pulls])
    except GithubSimError:
        log.exception("Annonce des PR de %s", ctx.workspace_id)


def refresh_after_command(ctx: OpContext, command: object, code: int | None) -> None:
    """Crochet `terminal.AFTER_COMMAND_HOOKS` : push, pull ou fetch ont pu bouger `origin`."""
    if not (ctx.layout.repo / ".git").exists():
        return
    git = _git(ctx.git_path, ctx.layout, ctx.settings)
    announce(ctx, github_sim.refresh(git, ctx.layout).updated)


def _refuse(ctx: OpContext, error: GithubSimError) -> int:
    ctx.output(f"{error.cause_text} {error.action_text}", "refused")
    return EXIT_REFUSED


def _preflight(engine: WorkspaceEngine, work) -> None:  # noqa: ANN001
    """Refus synchrone (409) : relit `origin`, hors file, pour répondre sans attendre.

    Une lecture qui échoue (git, github.json en cours de remplacement) ne refuse rien : le
    corps de l'opération revérifie dans la file."""
    try:
        work(_git(engine.git_path, engine.layout, engine.settings))
    except GithubSimError as error:
        raise OperationRefused(f"{error.cause_text} {error.action_text}") from None
    except GitError:
        log.warning("Pré-vérification illisible pour %s", engine.workspace_id, exc_info=True)


def build_pr_open(engine: WorkspaceEngine, body: PrOpen) -> Operation:
    layout = engine.layout

    def check(git: Git) -> None:
        branches = github_sim.origin_branches(git, layout)
        for name in (body.head, body.base):
            if name not in branches:
                raise GithubSimError(
                    f"La branche « {name} » n'existe pas sur origin.",
                    "Poussez d'abord la branche avec git push, puis ouvrez la PR.",
                )

    _preflight(engine, check)

    def run(ctx: OpContext) -> int:
        git = _git(ctx.git_path, ctx.layout, ctx.settings)
        try:
            pr = github_sim.open_pr(
                git, ctx.layout, body.head, body.base, title_text=body.title_text
            )
        except GithubSimError as error:
            return _refuse(ctx, error)
        ctx.output(f"PR n°{pr.number} ouverte : {pr.head} vers {pr.base}.", "app")
        announce(ctx, [pr.number])
        return 0

    return Operation("pr_open", run)


def build_pr_merge(engine: WorkspaceEngine, body: PrMerge) -> Operation:
    layout = engine.layout

    def check(git: Git) -> None:
        try:
            state = github_sim.load(layout)
        except GithubSimError:
            log.warning("État des PR illisible hors file pour %s", engine.workspace_id)
            return
        pr = state.pull(body.number)
        if pr is None or pr.state != "open":
            raise GithubSimError(
                f"La PR n°{body.number} n'est pas ouverte.",
                "Ouvrez une PR depuis une branche poussée.",
            )
        if not pr.mergeable:
            raise GithubSimError(
                f"La PR n°{body.number} ne peut pas être mergée : "
                + " ".join(r.text for r in pr.blocking_reasons),
                "Levez ces blocages, puis réessayez.",
            )

    _preflight(engine, check)

    def run(ctx: OpContext) -> int:
        git = _git(ctx.git_path, ctx.layout, ctx.settings)
        try:
            pr = github_sim.merge_pr(git, ctx.layout, body.number)
        except GithubSimError as error:
            # Le recalcul a pu changer la PR (bloquée, course) : la vue doit le voir.
            _announce_all(ctx)
            return _refuse(ctx, error)
        ctx.output(f"PR n°{pr.number} mergée dans {pr.base}.", "app")
        _announce_all(ctx)
        return 0

    return Operation("pr_merge", run)


REVIEW_BARRIER = "review"
"""Barrière de `content/chain.yaml` que prouve la revue obligatoire (story 7.5)."""


def build_pr_request_review(engine: WorkspaceEngine, body: PrMerge) -> Operation:
    """« Demander une revue » (story 7.5) : le collègue simulé relit quand les checks sont
    verts. Sa revue entre dans le journal de la PR, preuve `evidence_seen` de la revue."""
    del engine

    def run(ctx: OpContext) -> int:
        tool = _git(ctx.git_path, ctx.layout, ctx.settings)
        try:
            result = github_sim.request_review(tool, ctx.layout, body.number)
        except GithubSimError as error:
            _announce_all(ctx)
            return _refuse(ctx, error)
        ctx.output(f"Revue demandée pour la PR n°{body.number}.", "app")
        announce(ctx, sorted({body.number, *result.updated}))
        ctx.submit_evidence(REVIEW_BARRIER)
        return 0

    return Operation("pr_request_review", run)


def register_intents() -> None:
    """Enregistre `pr_open`, `pr_merge` et `pr_request_review` (idempotent)."""
    for name, model, build in (
        ("pr_open", PrOpen, build_pr_open),
        ("pr_merge", PrMerge, build_pr_merge),
        ("pr_request_review", PrMerge, build_pr_request_review),
    ):
        if name not in INTENTS:
            register_intent(Intent(name, model, build))
