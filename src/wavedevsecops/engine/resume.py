"""Reprise d'un scénario là où l'apprenant l'a laissé (Story 6.4, AD-5, AD-6, AD-20).

`check_resume` lit l'espace conservé sans le modifier ni lancer git : `run.json` (étape
courante, `content_hash`, restauration en échec). Il ne rouvre rien et ne recrée rien :
« Reprendre » rouvre l'espace existant.

L'empreinte n'est pas comparée ici. AD-6 : l'empreinte d'un espace repris est recalculée à
l'ouverture (projection d'ouverture du moteur), et un écart avec la dernière projection est
un « changement externe » que les vues suivent (2.9), pas un motif de refus : l'apprenant a
le droit de travailler dans son dépôt hors de l'application entre deux séances. Calculer
l'empreinte à chaque affichage du catalogue coûterait un parcours complet du dépôt, et un
verrou git passager (`index.lock`) y donnerait un faux refus.
"""

from __future__ import annotations

from dataclasses import dataclass

from wavedevsecops.contracts import AppError
from wavedevsecops.engine.runfile import load_run
from wavedevsecops.scenarios import LoadedScenario
from wavedevsecops.wsfs import Layout

CANNOT_RESUME_TEXT = "Ce scénario ne peut pas reprendre là où vous l'aviez laissé."


@dataclass(frozen=True)
class ResumeCheck:
    """Étape conservée d'un espace, et ce qui empêche (ou non) de la rouvrir."""

    can_resume: bool
    step_number: int = 0
    step_total: int = 0
    reason: str = ""
    """`workspace_missing`, `repo_broken`, `run_unreadable`, `content_changed`, `step_unknown`,
    `broken` ou `finished` ; vide si la reprise est possible."""

    @property
    def offered(self) -> bool:
        """« Reprendre » (ou l'encart) s'affiche ; un scénario terminé n'a plus d'étape."""
        return self.reason != "finished"


def check_resume(layout: Layout, loaded: LoadedScenario) -> ResumeCheck:
    """Contrôle de la reprise de `loaded` dans l'espace `layout` (lecture seule, sans git)."""
    total = len(loaded.scenario.steps)
    if not layout.root.is_dir() or not layout.repo.is_dir():
        return ResumeCheck(False, 0, total, "workspace_missing")
    if not (layout.repo / ".git").exists() or not layout.origin.is_dir():
        # Le setup crée toujours `repo/.git` et `origin.git/` : sans eux, le bac à sable n'est
        # plus celui du scénario (contrôle structurel, sans lancer git).
        return ResumeCheck(False, 0, total, "repo_broken")
    try:
        run = load_run(layout)
    except AppError:
        return ResumeCheck(False, 0, total, "run_unreadable")
    if "step_id" not in run:
        return ResumeCheck(False, 0, total, "run_unreadable")
    step_id = run.get("step_id")
    if not step_id:
        # `step_id: null` : la dernière étape est validée, le scénario est terminé.
        return ResumeCheck(False, total, total, "finished")
    if run.get("content_hash") != loaded.content_hash:
        return ResumeCheck(False, 0, total, "content_changed")
    ids = [step.step_id for step in loaded.scenario.steps]
    if step_id not in ids:
        return ResumeCheck(False, 0, total, "step_unknown")
    number = ids.index(step_id) + 1
    if run.get("restore_failed") or run.get("restoring"):
        return ResumeCheck(False, number, total, "broken")
    return ResumeCheck(True, number, total)
