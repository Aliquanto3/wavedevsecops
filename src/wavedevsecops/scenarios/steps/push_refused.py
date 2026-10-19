"""Étape validée par le refus d'un push direct sur une branche protégée (AD-7, AD-8).

Le refus ne laisse aucune trace dans le dépôt (la branche locale reste en avance sur `origin`) :
le terminal dépose `ctx.data[REFUSED_KEY] = <branche>` quand il explique le refus du hook
`pre-receive`, et seule cette opération valide l'étape. Un push accepté, un autre refus ou
une autre commande ne la valident pas.
"""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from wavedevsecops.contracts import RepoState
from wavedevsecops.scenarios.steps._base import StepArgs, StepContext, Verdict

REFUSED_KEY = "push_refused"
"""Clé de `ctx.data` : branche protégée dont le push vient d'être refusé."""


class Args(StepArgs):
    type: Literal["push_refused"]
    branch: str = Field(min_length=1)
    """Branche protégée dont le push direct doit être refusé (nom court)."""


def check(state: RepoState | None, ctx: StepContext) -> Verdict:  # noqa: ARG001
    """`passed` quand l'opération courante est le refus du push direct de `branch`."""
    if ctx.data.get(REFUSED_KEY) == ctx.step.branch:
        return Verdict(status="passed")
    return Verdict(status="pending")
