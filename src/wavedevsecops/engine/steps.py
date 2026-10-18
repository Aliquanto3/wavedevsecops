"""Validation des étapes d'un scénario sur l'état réel du dépôt (AD-7, AD-1).

La file appelle `StepRunner.validate` après les projections : l'étape courante de l'espace
(`step_id` de `run.json`) juge le `RepoState` que la projection vient de publier, par le
`check` de son type (registre `scenarios/steps/`). Le moteur ne connaît aucun type d'étape.
Une réussite fait passer `run.json` à l'étape suivante ; la file publie le verdict, puis
l'explication.

`StepRunner.panel` écrit pour le serveur le panneau Scénario (titre, étapes, étape courante) :
le front ne calcule rien (AD-2).
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from wavedevsecops.config import Settings
from wavedevsecops.contracts import RepoState
from wavedevsecops.engine.operations import OpContext, Projection, StepOutcome, WorkspaceEngine
from wavedevsecops.engine.runfile import load_run, save_run
from wavedevsecops.events import StepObserved, StepVerdict
from wavedevsecops.scenarios import STEP_TYPES, Scenario, load_scenario
from wavedevsecops.scenarios.steps import StepContext
from wavedevsecops.wsfs import Layout

log = logging.getLogger("wavedevsecops")

MODE_TEXTS = {
    "A": "Mode A : vous tapez vous-même les commandes ; chaque étape se valide sur l'état "
    "réel du dépôt, quelle que soit la commande tapée.",
    "B": "Mode B : un agent a déjà agi dans le dépôt ; vous relisez son travail.",
}


def _state_from_views(views: dict[str, Any] | None) -> RepoState | None:
    repo = (views or {}).get("repo")
    if not isinstance(repo, dict):
        return None
    try:
        return RepoState.model_validate(repo)
    except ValidationError:
        return None


class StepRunner:
    """Valide l'étape courante des espaces et décrit leur panneau Scénario."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._cache: dict[Path, tuple[tuple[int, int], Scenario]] = {}

    def scenario(self, run: dict[str, Any]) -> Scenario | None:
        """Scénario de l'espace (relu quand son fichier change) ; `None` s'il n'existe plus."""
        scenario_id, mode = run.get("scenario_id"), run.get("mode")
        if not isinstance(scenario_id, str) or not isinstance(mode, str):
            return None
        path = self._settings.scenarios_path() / f"{scenario_id}.{mode}.yaml"
        try:
            info = path.stat()
            stamp = (info.st_mtime_ns, info.st_size)
        except OSError:
            return None
        cached = self._cache.get(path)
        if cached is None or cached[0] != stamp:
            cached = (stamp, load_scenario(path, self._settings).scenario)
            self._cache[path] = cached
        return cached[1]

    def _run(self, layout: Layout) -> dict[str, Any] | None:
        return load_run(layout) if layout.run_json.exists() else None

    # ------------------------------------------------------------ validation
    def validate(self, ctx: OpContext, projection: Projection) -> StepOutcome | None:
        """Verdict de l'étape courante sur l'état projeté ; `None` : rien à publier."""
        run = self._run(ctx.layout)
        if run is None or not run.get("step_id"):
            return None
        scenario = self.scenario(run)
        state = _state_from_views(projection.views)
        if scenario is None or state is None:
            return None
        steps = scenario.steps
        index = next((i for i, s in enumerate(steps) if s.step_id == run["step_id"]), None)
        if index is None:
            return None
        step = steps[index]
        context = StepContext(
            step=step,
            aliases=dict(run.get("aliases") or {}),
            previous=_state_from_views(ctx.before_views),
        )
        verdict = STEP_TYPES[step.type].check(state, context)
        if verdict.status == "pending":
            return None
        if verdict.status == "passed":
            following = steps[index + 1].step_id if index + 1 < len(steps) else None
            save_run(ctx.layout, {**run, "step_id": following})
            published = StepVerdict(
                step_id=step.step_id, passed=True, status="passed", next_step_id=following or ""
            )
            return StepOutcome.explained(published, step.explanation_text, step.explain_ref)
        published = StepVerdict(
            step_id=step.step_id,
            passed=False,
            status=verdict.status,
            reason_text=verdict.reason_text,
            expected_text=verdict.expected_text,
            observed=[StepObserved(text=o.text, element_id=o.element_id) for o in verdict.observed],
        )
        return StepOutcome(published)

    # --------------------------------------------------------------- panneau
    def panel(self, engine: WorkspaceEngine) -> dict[str, Any] | None:
        """Panneau Scénario de l'espace : `None` si l'espace n'a pas d'étape."""
        run = self._run(engine.layout)
        scenario = self.scenario(run) if run is not None else None
        if run is None or scenario is None or not scenario.steps:
            return None
        current = run.get("step_id") or ""
        ids = [s.step_id for s in scenario.steps]
        position = ids.index(current) if current in ids else len(ids)
        steps = []
        for i, step in enumerate(scenario.steps):
            done = i < position
            steps.append(
                {
                    "step_id": step.step_id,
                    "title_text": step.title_text,
                    "instruction_text": step.instruction_text,
                    "state": "done" if done else ("current" if i == position else "todo"),
                    # L'explication n'est révélée qu'une fois l'étape réussie.
                    "explanation_text": step.explanation_text if done else "",
                    "explain_ref": step.explain_ref if done else "",
                }
            )
        return {
            "title_text": scenario.title_text,
            "mode": scenario.mode,
            "mode_text": MODE_TEXTS[scenario.mode],
            "current_step_id": current if position < len(ids) else "",
            "steps": steps,
        }
