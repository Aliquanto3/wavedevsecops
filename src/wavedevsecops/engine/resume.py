"""Reprise d'un scénario là où l'apprenant l'a laissé (Story 6.4, AD-5, AD-6, AD-20).

`check_resume` lit l'espace conservé sans le modifier : `run.json` (étape courante,
`content_hash`), puis l'état du dépôt (empreinte recalculée, AD-6). Il ne rouvre rien et ne
recrée rien : « Reprendre » rouvre l'espace existant.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

from wavedevsecops.config import Settings
from wavedevsecops.contracts import AppError
from wavedevsecops.engine.fingerprint import fingerprint
from wavedevsecops.engine.runfile import load_run
from wavedevsecops.gitio import Git
from wavedevsecops.scenarios import LoadedScenario
from wavedevsecops.wsfs import Layout

log = logging.getLogger("wavedevsecops")

CANNOT_RESUME_TEXT = "Ce scénario ne peut pas reprendre là où vous l'aviez laissé."


@dataclass(frozen=True)
class ResumeCheck:
    """Étape conservée d'un espace, et ce qui empêche (ou non) de la rouvrir."""

    can_resume: bool
    step_number: int = 0
    step_total: int = 0
    reason: str = ""
    """`workspace_missing`, `run_unreadable`, `content_changed`, `step_unknown`, `broken`,
    `finished` ou `fingerprint` ; vide si la reprise est possible."""

    @property
    def offered(self) -> bool:
        """« Reprendre » (ou l'encart) s'affiche ; un scénario terminé n'a plus d'étape."""
        return self.reason != "finished"


def check_resume(
    layout: Layout, loaded: LoadedScenario, settings: Settings, git_path: Path
) -> ResumeCheck:
    """Contrôle de la reprise de `loaded` dans l'espace `layout` (lecture seule)."""
    total = len(loaded.scenario.steps)
    if not layout.root.is_dir() or not layout.repo.is_dir():
        return ResumeCheck(False, 0, total, "workspace_missing")
    try:
        run = load_run(layout)
    except AppError:
        return ResumeCheck(False, 0, total, "run_unreadable")
    step_id = run.get("step_id")
    if not step_id:
        return ResumeCheck(False, total, total, "finished")
    if run.get("content_hash") != loaded.content_hash:
        return ResumeCheck(False, 0, total, "content_changed")
    ids = [step.step_id for step in loaded.scenario.steps]
    if step_id not in ids:
        return ResumeCheck(False, 0, total, "step_unknown")
    number = ids.index(step_id) + 1
    if run.get("restore_failed") or run.get("restoring"):
        return ResumeCheck(False, number, total, "broken")
    try:
        # AD-6 : l'empreinte est recalculée à la reprise ; un dépôt qui ne se lit plus l'écarte.
        if not fingerprint(layout, Git.for_workspace(git_path, layout.root, settings)):
            return ResumeCheck(False, number, total, "fingerprint")
    except Exception as error:  # noqa: BLE001 - tout échec de lecture de l'état écarte la reprise
        log.warning("Empreinte illisible à la reprise (%s) : %s", layout.root, error)
        return ResumeCheck(False, number, total, "fingerprint")
    return ResumeCheck(True, number, total)
