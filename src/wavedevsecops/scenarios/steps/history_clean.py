"""Étape validée quand un fichier a quitté tout l'historique accessible et est ignoré (AD-7).

`RepoState` ne détaille pas le contenu des commits : l'étape interroge git par `ctx.git`
(lecture seule). Elle réussit quand aucun commit accessible depuis une ref (branche, tag,
distant, stash) n'ajoute ou ne modifie `path`, et que `.gitignore` l'ignore, quelle que soit la
suite de commandes qui y mène. Les commits seulement cités par le reflog ne comptent pas.
"""

from __future__ import annotations

import logging
from typing import Literal

from pydantic import Field

from wavedevsecops.contracts import RepoState, element_id
from wavedevsecops.scenarios.steps._base import Observed, StepArgs, StepContext, Verdict

log = logging.getLogger("wavedevsecops")

SHOWN = 5
"""Commits au plus cités dans l'état observé."""


class Args(StepArgs):
    type: Literal["history_clean"]
    path: str = Field(min_length=1)
    """Fichier à retirer de l'historique (chemin posix relatif au dépôt)."""
    ignored: bool = True
    """Le fichier doit aussi être ignoré par `.gitignore`."""


def _leaking(ctx: StepContext, path: str) -> list[str] | None:
    """SHA des commits accessibles qui ajoutent ou modifient `path` ; `None` si illisible."""
    git = ctx.git() if ctx.git is not None else None
    if git is None or ctx.layout is None:
        return None
    # Tout commit dont l'arbre contient `path` descend d'un commit qui l'ajoute (ou le renomme).
    found = git.run(
        "log",
        "--all",
        "--diff-filter=AMRC",
        "--format=%H",
        "--",
        f":(literal){path}",
        cwd=ctx.layout.repo,
    )
    if not found.ok:
        log.warning("Historique de %s illisible pour l'étape %s", path, ctx.step.step_id)
        return None
    return list(dict.fromkeys(found.stdout.split()))


def _is_ignored(ctx: StepContext, path: str) -> bool | None:
    git = ctx.git() if ctx.git is not None else None
    if git is None or ctx.layout is None:
        return None
    # `--no-index` : la règle de `.gitignore` compte même si le fichier est encore suivi.
    result = git.run("check-ignore", "-q", "--no-index", "--", path, cwd=ctx.layout.repo)
    if result.returncode not in (0, 1):
        return None
    return result.returncode == 0


def check(state: RepoState | None, ctx: StepContext) -> Verdict:
    """`passed` si `path` est hors de l'historique accessible (et ignoré) ; sinon `failed`
    avec ce qu'il reste à faire, ou `pending` si l'état n'a pas bougé."""
    if state is None:
        return Verdict(status="pending")
    step: Args = ctx.step
    try:
        leaking = _leaking(ctx, step.path)
        ignored = _is_ignored(ctx, step.path) if step.ignored else True
    except Exception:  # noqa: BLE001 - un git indisponible ne bloque rien
        log.exception("Étape %s : historique illisible", step.step_id)
        return Verdict(status="pending")
    if leaking is None or ignored is None:
        return Verdict(status="pending")
    if not leaking and ignored:
        return Verdict(status="passed")
    if ctx.previous is not None and ctx.previous == state:
        return Verdict(status="pending")  # rien n'a bougé : rien à signaler
    expected = f"Aucun commit accessible ne contient `{step.path}`"
    expected += f", et `{step.path}` est ignoré par `.gitignore`." if step.ignored else "."
    observed = [
        Observed(
            text=f"Le commit `{sha[:7]}` contient encore `{step.path}`.",
            element_id=element_id("commit", sha),
        )
        for sha in leaking[:SHOWN]
    ]
    if leaking:
        reason = (
            f"`{step.path}` est encore dans l'historique : au moins un commit accessible depuis "
            "une branche, un tag ou le stash le contient. Le supprimer dans un nouveau commit "
            "ne l'efface pas des commits précédents."
        )
    else:
        reason = (
            f"`{step.path}` n'est plus dans l'historique, mais rien ne l'ignore : "
            "un prochain `git add` pourrait le remettre. Ajoutez-le à `.gitignore`."
        )
        observed = [Observed(text=f"`{step.path}` n'est pas ignoré par `.gitignore`.")]
    return Verdict(status="failed", reason_text=reason, expected_text=expected, observed=observed)
