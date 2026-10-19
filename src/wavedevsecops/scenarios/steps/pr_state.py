"""Étape validée par l'état d'une pull request du GitHub simulé : ouverte, revue reçue, mergée.

L'état d'une PR n'est pas dans le dépôt git (`RepoState`) : l'étape lit le GitHub simulé de
l'espace (`ctx.layout`), relu après chaque opération. Elle ne juge que cet état : une PR qui
n'existe pas encore ou qui n'a pas l'état attendu donne `pending` (rien à dire), jamais d'échec
(AD-7, AD-8).
"""

from __future__ import annotations

import logging
from typing import Literal

from pydantic import Field

from wavedevsecops import github_sim
from wavedevsecops.contracts import RepoState
from wavedevsecops.scenarios.steps._base import StepArgs, StepContext, Verdict

log = logging.getLogger("wavedevsecops")


class Args(StepArgs):
    type: Literal["pr_state"]
    head: str = Field(min_length=1)
    """Branche de tête de la PR attendue (nom court)."""
    base: str = "main"
    pr_state: Literal["open", "merged"] = "open"
    """État attendu de la PR."""
    min_approvals: int = Field(default=0, ge=0)
    """Approbations au moins attendues."""


def check(state: RepoState | None, ctx: StepContext) -> Verdict:  # noqa: ARG001
    """`passed` si une PR de `head` vers `base` a l'état et les approbations attendus."""
    if ctx.layout is None:
        return Verdict(status="pending")
    step: Args = ctx.step
    try:
        pulls = github_sim.load(ctx.layout).pulls
    except Exception:  # noqa: BLE001 - un état illisible ne bloque rien
        log.exception("État des PR illisible pour l'étape %s", step.step_id)
        return Verdict(status="pending")
    for pr in pulls:
        if (
            pr.head == step.head
            and pr.base == step.base
            and pr.state == step.pr_state
            and pr.approvals >= step.min_approvals
        ):
            return Verdict(status="passed")
    return Verdict(status="pending")
