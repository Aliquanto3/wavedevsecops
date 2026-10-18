"""GitHub simulé d'un espace : seul écrivain de `github.json` (AD-5, AD-8, AD-20).

`github.json` n'est écrit qu'ici, par écriture atomique (`wsfs.write_json`), depuis une
opération de la file de l'espace (le setup passe lui-même par la file, AD-1). Chaque écriture
part d'une lecture, applique la modification, puis recalcule toutes les PR ouvertes contre
les refs courantes de `origin.git` (`refresh`) : quand `head_sha` ou `base_sha` d'une PR
change, ses checks repassent à `queued` dans la même écriture, et `mergeable` et les raisons
de blocage sont recalculés.

Une PR est mergeable si chaque check obligatoire est `success` pour ses `head_sha` et
`base_sha` courants, si les approbations requises sont atteintes et s'il n'y a pas de conflit
(`git merge-tree --write-tree`, sans worktree).
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from typing import Any

from pydantic import ValidationError

from wavedevsecops import gitio, wsfs
from wavedevsecops.contracts import AppError, element_id
from wavedevsecops.contracts.github import (
    GITHUB_SCHEMA_VERSION,
    BlockReason,
    BranchProtection,
    Check,
    CheckState,
    Finding,
    GithubState,
    PullRequest,
    Review,
    ReviewState,
)
from wavedevsecops.gitio import Git, GitError
from wavedevsecops.wsfs import Layout

MIGRATIONS: dict[int, Callable[[dict[str, Any]], dict[str, Any]]] = {}
"""`MIGRATIONS[n]` fait passer un `github.json` de la version `n` à `n + 1` (en ajout seulement)."""

FINGERPRINT_EXCLUDED_CHECK_FIELDS = frozenset({"output", "duration_ms", "updated_at"})
"""Champs d'un check exclus de l'empreinte (AD-6) : sortie, durée, horodatage."""

STATE_TEXT: dict[str, str] = {
    "queued": "est en attente",
    "running": "est en cours",
    "failure": "a échoué",
    "error": "s'est terminé en erreur",
}


class GithubSimError(AppError):
    """Le GitHub simulé refuse ou ne peut pas lire son état."""


@dataclass(frozen=True)
class DeclaredCheck:
    """Check déclaré à l'ouverture d'une PR (scénario de test, station) : lié aux SHA courants."""

    job_id: str
    state: CheckState = "queued"
    required: bool = False
    output: str = ""
    findings: tuple[Finding, ...] = ()


@dataclass(frozen=True)
class DeclaredReview:
    """Revue déclarée par le scénario : liée au `head_sha` courant de la PR."""

    author: str
    state: ReviewState
    body_text: str = ""


@dataclass
class RefreshResult:
    """Résultat d'un recalcul : l'état écrit et les PR touchées."""

    state: GithubState
    sha_changed: list[int] = field(default_factory=list)
    """PR dont `head_sha` ou `base_sha` a changé (checks remis à `queued` : un run est à
    demander au pipeline simulé)."""
    updated: list[int] = field(default_factory=list)
    """PR dont le contenu a changé (`pr_updated` à émettre)."""


# --- Lecture, migrations, écriture -------------------------------------------------------


def _read_raw(layout: Layout) -> dict[str, Any] | None:
    path = layout.github_json
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_bytes().decode("utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        raise GithubSimError(
            "L'état du GitHub simulé de cet espace (github.json) est illisible.",
            "Recommencez le scénario pour reconstruire l'espace.",
        ) from None
    version = data.get("schema_version") if isinstance(data, dict) else None
    if not isinstance(version, int) or version < 1:
        raise GithubSimError(
            "L'état du GitHub simulé de cet espace (github.json) n'a pas de version valide.",
            "Recommencez le scénario pour reconstruire l'espace.",
        )
    if version > GITHUB_SCHEMA_VERSION:
        raise GithubSimError(
            "L'état du GitHub simulé de cet espace vient d'une version plus récente de "
            "WaveDevSecOps.",
            "Mettez WaveDevSecOps à jour pour rouvrir cet espace.",
        )
    while version < GITHUB_SCHEMA_VERSION:
        data = MIGRATIONS[version](data)
        version += 1
        data["schema_version"] = version
    return data


def load(layout: Layout) -> GithubState:
    """État du GitHub simulé (fichier absent : état vide), mis à la version courante en mémoire."""
    data = _read_raw(layout)
    if data is None:
        return GithubState()
    try:
        return GithubState.model_validate(data)
    except ValidationError:
        raise GithubSimError(
            "L'état du GitHub simulé de cet espace (github.json) est invalide.",
            "Recommencez le scénario pour reconstruire l'espace.",
        ) from None


def _save(layout: Layout, state: GithubState) -> None:
    wsfs.write_json(layout.github_json, state.model_dump(mode="json"))


def init(layout: Layout) -> GithubState:
    """Crée un `github.json` vide (`schema_version`, aucune PR) s'il n'existe pas."""
    if layout.github_json.is_file():
        return load(layout)
    state = GithubState()
    _save(layout, state)
    return state


def canonical_digest(layout: Layout) -> str | None:
    """sha256 de la sérialisation canonique de `github.json` pour l'empreinte (AD-6) :
    JSON trié, sans `checks[].output`, durées ni horodatages. Fichier absent : `None`."""
    if _read_raw(layout) is None:
        return None
    data = load(layout).model_dump(mode="json")
    for pull in data["pulls"]:
        for check in pull["checks"]:
            for name in FINGERPRINT_EXCLUDED_CHECK_FIELDS:
                check.pop(name, None)
    text = json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


# --- Lectures de origin.git ----------------------------------------------------------------


def origin_branches(git: Git, layout: Layout) -> dict[str, str]:
    """Branches de `origin.git` : nom court -> SHA."""
    prefix = "refs/heads/"
    return {
        name.removeprefix(prefix): target
        for name, target in gitio.refs(git, layout.origin)
        if name.startswith(prefix)
    }


def has_conflict(git: Git, layout: Layout, base_sha: str, head_sha: str) -> bool:
    """Vrai si merger `head_sha` dans `base_sha` donne un conflit (`merge-tree --write-tree`,
    sans worktree ni écriture de ref). Des historiques sans ancêtre commun comptent comme
    un conflit."""
    args = ("merge-tree", "--write-tree", "--no-messages", base_sha, head_sha)
    result = git.run(*args, cwd=layout.origin)
    if result.returncode == 0:
        return False
    if result.returncode == 1 or "unrelated histories" in result.stderr:
        return True
    raise GitError(args, result)


# --- Calcul de mergeable --------------------------------------------------------------------


ConflictProbe = Callable[[str, str], bool | None]
"""`(base_sha, head_sha) -> conflit ?` ; `None` : fusion impossible à calculer."""


def _requeue(check: Check, head_sha: str, base_sha: str) -> Check:
    return check.model_copy(
        update={
            "head_sha": head_sha,
            "base_sha": base_sha,
            "state": "queued",
            "output": "",
            "findings": [],
            "duration_ms": None,
            "updated_at": None,
        }
    )


def _check_reason(pr: PullRequest, check: Check) -> BlockReason | None:
    if check.state == "success" and (check.head_sha, check.base_sha) == (
        pr.head_sha,
        pr.base_sha,
    ):
        return None
    if check.state == "success":
        text = (
            f"Le check obligatoire « {check.job_id} » a réussi sur un ancien commit : "
            "il doit repasser sur le commit courant de la PR."
        )
    else:
        text = f"Le check obligatoire « {check.job_id} » {STATE_TEXT[check.state]}."
    return BlockReason(kind="check", text=text, element_id=check.element(pr.number))


def evaluate(
    pr: PullRequest,
    protection: BranchProtection | None,
    branches: dict[str, str],
    conflict: ConflictProbe,
) -> tuple[PullRequest, bool]:
    """Recalcule une PR ouverte contre les branches de `origin`.

    Rend la PR mise à jour et un drapeau vrai si `head_sha` ou `base_sha` a changé (ses
    checks sont alors remis à `queued`)."""
    if pr.state != "open":
        return pr, False
    required_checks = list(protection.required_checks) if protection else []
    checks = [
        c.model_copy(update={"required": c.required or c.job_id in required_checks})
        for c in pr.checks
    ]
    head_sha = branches.get(pr.head)
    base_sha = branches.get(pr.base)
    update: dict[str, Any] = {
        "protection": protection,
        "required_approvals": protection.required_approvals if protection else 0,
    }
    if head_sha is None or base_sha is None:
        missing = pr.head if head_sha is None else pr.base
        reason = BlockReason(
            kind="head_missing",
            text=(
                f"La branche « {missing} » n'existe pas sur origin : le GitHub simulé ne peut "
                "pas calculer cette PR."
            ),
            element_id=element_id("ref", f"refs/remotes/origin/{missing}"),
        )
        update |= {"checks": checks, "mergeable": False, "blocking_reasons": [reason]}
        return pr.model_copy(update=update), False
    sha_changed = (head_sha, base_sha) != (pr.head_sha, pr.base_sha)
    if sha_changed:
        checks = [_requeue(c, head_sha, base_sha) for c in checks]
    known = {c.job_id for c in checks}
    checks += [
        Check(job_id=job, head_sha=head_sha, base_sha=base_sha, required=True)
        for job in required_checks
        if job not in known
    ]
    current = pr.model_copy(update=update | {"head_sha": head_sha, "base_sha": base_sha})
    reasons = [r for c in checks if c.required and (r := _check_reason(current, c))]
    stale_dismissed = protection is not None and protection.dismiss_stale_reviews
    approvals = current.count_approvals(head_sha=head_sha if stale_dismissed else None)
    if approvals < current.required_approvals:
        reasons.append(
            BlockReason(
                kind="approvals",
                text=(
                    f"Approbations : {approvals} sur {current.required_approvals} requise(s) "
                    f"par la protection de « {pr.base} »."
                ),
                element_id=current.element,
            )
        )
    conflicting = conflict(base_sha, head_sha)
    if conflicting is None:
        reasons.append(
            BlockReason(
                kind="conflict",
                text=(
                    f"Le GitHub simulé n'a pas pu calculer la fusion de « {pr.head} » dans "
                    f"« {pr.base} » : la PR reste bloquée."
                ),
                element_id=current.element,
            )
        )
    elif conflicting:
        reasons.append(
            BlockReason(
                kind="conflict",
                text=(
                    f"La branche « {pr.head} » est en conflit avec « {pr.base} » : "
                    "résolvez le conflit, puis poussez à nouveau."
                ),
                element_id=current.element,
            )
        )
    current = current.model_copy(
        update={
            "checks": checks,
            "approvals": approvals,
            "mergeable": not reasons,
            "blocking_reasons": reasons,
        }
    )
    return current, sha_changed


def _recompute(git: Git, layout: Layout, state: GithubState) -> RefreshResult:
    branches = origin_branches(git, layout)
    cache: dict[tuple[str, str], bool | None] = {}

    def conflict(base_sha: str, head_sha: str) -> bool | None:
        key = (base_sha, head_sha)
        if key not in cache:
            try:
                cache[key] = has_conflict(git, layout, base_sha, head_sha)
            except GitError:
                cache[key] = None
        return cache[key]

    result = RefreshResult(state)
    pulls = []
    for pr in state.pulls:
        new, sha_changed = evaluate(pr, state.protection(pr.base), branches, conflict)
        if sha_changed:
            result.sha_changed.append(pr.number)
        if new != pr:
            result.updated.append(pr.number)
        pulls.append(new)
    result.state = state.model_copy(update={"pulls": pulls})
    return result


def _commit(git: Git, layout: Layout, state: GithubState, *, force: bool = False) -> RefreshResult:
    """Recalcule puis écrit, en une seule écriture atomique."""
    result = _recompute(git, layout, state)
    if force or result.updated or not layout.github_json.is_file():
        _save(layout, result.state)
    return result


def refresh(git: Git, layout: Layout) -> RefreshResult:
    """Après un changement des refs de `origin` : recalcule toutes les PR ouvertes.

    N'écrit que si une PR a changé ; idempotent. Sans `github.json` (espace préparé avant le
    GitHub simulé), il n'y a aucune PR : rien n'est écrit."""
    if _read_raw(layout) is None:
        return RefreshResult(GithubState())
    return _commit(git, layout, load(layout))


# --- Modifications ----------------------------------------------------------------------------


def set_protection(git: Git, layout: Layout, protection: BranchProtection) -> RefreshResult:
    """Pose (ou remplace) la protection d'une branche, puis recalcule les PR."""
    state = load(layout)
    others = [p for p in state.protections if p.branch != protection.branch]
    protections = sorted([*others, protection], key=lambda p: p.branch)
    return _commit(git, layout, state.model_copy(update={"protections": protections}), force=True)


def open_pr(
    git: Git,
    layout: Layout,
    head: str,
    base: str = "main",
    *,
    title_text: str = "",
    checks: Iterable[DeclaredCheck] = (),
    reviews: Iterable[DeclaredReview] = (),
) -> PullRequest:
    """Ouvre une PR de `head` vers `base`, toutes deux sur `origin` ; rend la PR écrite."""
    branches = origin_branches(git, layout)
    for branch in (head, base):
        if branch not in branches:
            raise GithubSimError(
                f"La branche « {branch} » n'existe pas sur origin : le GitHub simulé ne peut "
                "pas ouvrir la PR.",
                "Poussez d'abord la branche vers origin, puis ouvrez la PR.",
            )
    if head == base:
        raise GithubSimError(
            f"La PR irait de « {head} » vers elle-même.",
            "Choisissez une branche de tête différente de la base.",
        )
    checks = list(checks)
    job_ids = [c.job_id for c in checks]
    if len(set(job_ids)) != len(job_ids):
        raise GithubSimError(
            "La PR déclare deux fois le même check.",
            "Déclarez chaque job_id une seule fois.",
        )
    state = load(layout)
    if any(p.state == "open" and (p.head, p.base) == (head, base) for p in state.pulls):
        raise GithubSimError(
            f"Une PR de « {head} » vers « {base} » est déjà ouverte.",
            "Ouvrez cette PR existante plutôt qu'une nouvelle.",
        )
    head_sha, base_sha = branches[head], branches[base]
    number = state.next_number
    declared_checks = [
        Check(
            job_id=c.job_id,
            head_sha=head_sha,
            base_sha=base_sha,
            state=c.state,
            required=c.required,
            output=c.output,
            findings=list(c.findings),
        )
        for c in checks
    ]
    declared_reviews = [
        Review(
            review_id=index,
            author=r.author,
            state=r.state,
            body_text=r.body_text,
            commit_sha=head_sha,
        )
        for index, r in enumerate(reviews, start=1)
    ]
    pr = PullRequest(
        number=number,
        title_text=title_text,
        head=head,
        base=base,
        head_sha=head_sha,
        base_sha=base_sha,
        checks=declared_checks,
        reviews=declared_reviews,
    )
    new_state = state.model_copy(update={"next_number": number + 1, "pulls": [*state.pulls, pr]})
    written = _commit(git, layout, new_state, force=True).state.pull(number)
    assert written is not None
    return written


__all__ = [
    "DeclaredCheck",
    "DeclaredReview",
    "GithubSimError",
    "RefreshResult",
    "canonical_digest",
    "evaluate",
    "has_conflict",
    "init",
    "load",
    "open_pr",
    "origin_branches",
    "refresh",
    "set_protection",
]
