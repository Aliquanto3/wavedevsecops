"""Étape validée par l'état d'une pull request du GitHub simulé : ouverte, revue reçue, mergée.

L'état d'une PR n'est pas dans le dépôt git (`RepoState`) : l'étape lit le GitHub simulé de
l'espace (`ctx.layout`), relu après chaque opération. Elle ne juge que cet état : une PR qui
n'existe pas encore ou qui n'a pas l'état attendu donne `pending` (rien à dire), jamais d'échec
(AD-7, AD-8).
"""

from __future__ import annotations

import logging
import re
from typing import Literal

from pydantic import Field, field_validator

from wavedevsecops import github_sim
from wavedevsecops.contracts import RepoState
from wavedevsecops.contracts.github import JOB_ID_PATTERN, CheckState, HeadFile, PullRequest
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
    max_approvals: int | None = Field(default=None, ge=0)
    """Approbations au plus attendues (0 : la revue manque encore)."""
    check_states: dict[str, CheckState] = Field(default_factory=dict)
    """État attendu de chaque check, par `job_id`, sur les SHA courants de la PR (un résultat
    périmé ne compte pas : le push qui le remplace remet le check en attente)."""
    sbom_has: dict[str, list[str]] = Field(default_factory=dict)
    """Composants que le SBOM de chaque check (par `job_id`, SHA courants) doit encore contenir
    (nom de paquet) : un vert obtenu en vidant ou en supprimant le fichier de dépendances ne
    valide pas l'étape (leçon 6.2 : le geste enseigné, pas un contournement)."""
    finding_has: dict[str, list[str]] = Field(default_factory=dict)
    """Constats (`rule_id`) que chaque check (par `job_id`, SHA courants) doit porter : la quality
    gate doit avoir mesuré des lignes du nouveau code (`diff_coverage`), pas constaté qu'il n'y en
    a plus (`diff_coverage_none`) : supprimer le code non testé ne valide pas l'étape (leçon
    6.2 : le geste enseigné, pas un contournement)."""
    mergeable: bool | None = None
    """`True` : « Merger » est actif ; `False` : la PR est bloquée (`merge-blocked`)."""
    head_files: list[HeadFile] = Field(default_factory=list)
    """Fichiers du commit de tête de la PR (lus dans `origin.git`) : chacun existe et ne nomme
    aucun identifiant interdit. Un check vert obtenu en contournant l'outil (`getattr` au lieu
    d'`eval`) ou en supprimant le fichier ne valide pas l'étape (leçon 6.2)."""

    @field_validator("check_states", "sbom_has", "finding_has")
    @classmethod
    def _jobs(cls, value: dict) -> dict:
        for job in value:
            if not re.fullmatch(JOB_ID_PATTERN, job):
                raise ValueError(f"job_id invalide : « {job} »")
        return value


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
            and (step.max_approvals is None or pr.approvals <= step.max_approvals)
            and (step.mergeable is None or pr.mergeable is step.mergeable)
            and _checks_match(pr, step.check_states)
            and _sbom_match(pr, step.sbom_has)
            and _findings_match(pr, step.finding_has)
            and _files_match(pr, step.head_files, ctx)
        ):
            return Verdict(status="passed")
    return Verdict(status="pending")


def _files_match(pr: PullRequest, files: list[HeadFile], ctx: StepContext) -> bool:
    """Les fichiers demandés remplissent leur condition au commit de tête de la PR."""
    if not files:
        return True
    if ctx.git is None:
        return False
    try:
        return github_sim.head_files_ok(ctx.git(), ctx.layout, pr.head_sha, files)
    except Exception:  # noqa: BLE001 - un git indisponible ne valide rien et ne bloque rien
        log.exception("Fichiers de la PR illisibles pour l'étape %s", ctx.step.step_id)
        return False


def _sbom_match(pr: PullRequest, wanted: dict[str, list[str]]) -> bool:
    """Chaque composant demandé figure au SBOM du check, calculé pour les SHA courants."""
    checks = {c.job_id: c for c in pr.checks}
    for job_id, names in wanted.items():
        check = checks.get(job_id)
        if check is None or (check.head_sha, check.base_sha) != (pr.head_sha, pr.base_sha):
            return False
        present = {re.sub(r"[-_.]+", "-", item.name).lower() for item in check.sbom}
        if any(re.sub(r"[-_.]+", "-", name).lower() not in present for name in names):
            return False
    return True


def _findings_match(pr: PullRequest, wanted: dict[str, list[str]]) -> bool:
    """Chaque check demandé porte chacun des constats, calculé pour les SHA courants."""
    checks = {c.job_id: c for c in pr.checks}
    for job_id, rules in wanted.items():
        check = checks.get(job_id)
        if check is None or (check.head_sha, check.base_sha) != (pr.head_sha, pr.base_sha):
            return False
        present = {finding.rule_id for finding in check.findings}
        if any(rule not in present for rule in rules):
            return False
    return True


def _checks_match(pr: PullRequest, wanted: dict[str, CheckState]) -> bool:
    """Chaque check demandé existe, à l'état voulu, pour les SHA courants de la PR."""
    checks = {c.job_id: c for c in pr.checks}
    for job_id, state in wanted.items():
        check = checks.get(job_id)
        if (
            check is None
            or check.state != state
            or (check.head_sha, check.base_sha) != (pr.head_sha, pr.base_sha)
        ):
            return False
    return True
