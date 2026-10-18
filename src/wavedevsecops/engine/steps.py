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
from dataclasses import replace
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from wavedevsecops.config import Settings
from wavedevsecops.contracts import RepoState
from wavedevsecops.engine.operations import OpContext, Projection, StepOutcome, WorkspaceEngine
from wavedevsecops.engine.runfile import load_run, save_run
from wavedevsecops.events import StepObserved, StepVerdict
from wavedevsecops.scenarios import STEP_TYPES, Scenario, ScenarioError, load_scenario
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


def _public_quiz(quiz: Any) -> dict[str, Any] | None:
    """Ce que le panneau montre d'un quiz en attente de rétablissement (pas l'instantané)."""
    if not isinstance(quiz, dict):
        return None
    return {
        key: str(quiz.get(key) or "")
        for key in ("step_id", "choice_id", "command_text", "explanation_text")
    }


class StepRunner:
    """Valide l'étape courante des espaces et décrit leur panneau Scénario."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._cache: dict[Path, tuple[tuple[int, int], Scenario | None]] = {}

    def scenario(self, run: dict[str, Any]) -> Scenario | None:
        """Scénario de l'espace (relu quand son fichier change) ; `None` s'il n'existe plus ou
        s'il est invalide (journalisé une fois par version du fichier : l'étape reste ouverte)."""
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
            try:
                scenario: Scenario | None = load_scenario(path, self._settings).scenario
            except (ScenarioError, OSError, UnicodeDecodeError) as exc:
                log.warning("Scénario %s illisible, étapes non validées : %s", path.name, exc)
                scenario = None
            cached = (stamp, scenario)
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
        if scenario is None:
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
            intent=ctx.op.intent,
            data=dict(ctx.data),
            views=dict(projection.views or {}),
        )
        state = _state_from_views(projection.views)
        verdict = STEP_TYPES[step.type].check(state, context)
        if verdict.status == "pending":
            return None
        if verdict.status == "passed":
            following = steps[index + 1].step_id if index + 1 < len(steps) else None
            # `validated` : étapes réussies, citées par `step_id` (rejeu exact des faits).
            validated = [s for s in run.get("validated") or [] if s != step.step_id]
            save_run(
                ctx.layout,
                {**run, "step_id": following, "validated": [*validated, step.step_id]},
            )
            published = StepVerdict(
                step_id=step.step_id, passed=True, status="passed", next_step_id=following or ""
            )
            facts = self._facts_of(run, [step.step_id], finished=following is None)
            return replace(
                StepOutcome.explained(published, step.explanation_text, step.explain_ref),
                facts=tuple(facts),
            )
        published = StepVerdict(
            step_id=step.step_id,
            passed=False,
            status=verdict.status,
            reason_text=verdict.reason_text,
            expected_text=verdict.expected_text,
            observed=[StepObserved(text=o.text, element_id=o.element_id) for o in verdict.observed],
        )
        return StepOutcome(published)

    # ----------------------------------------------------------------- faits
    @staticmethod
    def _facts_of(run: dict[str, Any], step_ids: list[str], *, finished: bool) -> list[dict]:
        """Faits du premier passage établis par `run.json` (AD-14) : étapes validées, fin."""
        where = {
            "track": run.get("track"),
            "scenario_id": run.get("scenario_id"),
            "mode": run.get("mode"),
        }
        facts = [{"kind": "step_validated", "step_id": sid, **where} for sid in step_ids]
        if finished:
            facts.append({"kind": "scenario_completed", **where})
        return facts

    def replay(self, engine: WorkspaceEngine) -> list[dict[str, Any]]:
        """Faits que `run.json` établit déjà : l'écriture de `run.json` précède celle des faits,
        un arrêt brutal entre les deux en laisse des manquants (le magasin ignore les doublons).

        Les étapes viennent de `run.json["validated"]`, pas de leur position dans le scénario :
        une étape insérée ou déplacée par une mise à jour du contenu n'est pas tenue pour faite.
        """
        run = self._run(engine.layout)
        scenario = self.scenario(run) if run is not None else None
        if run is None or scenario is None:
            return []
        ids = [s.step_id for s in scenario.steps]
        current = run.get("step_id")
        validated = run.get("validated")
        if isinstance(validated, list):
            done = [s for s in validated if isinstance(s, str) and s]
            return self._facts_of(run, done, finished=current is None and bool(done))
        # `run.json` antérieur à `validated` : position dans le scénario.
        if current is None:
            return self._facts_of(run, ids, finished=bool(ids))
        if current not in ids:
            return []
        return self._facts_of(run, ids[: ids.index(current)], finished=False)

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
            entry = {
                "step_id": step.step_id,
                "title_text": step.title_text,
                "instruction_text": step.instruction_text,
                "state": "done" if done else ("current" if i == position else "todo"),
                # L'explication n'est révélée qu'une fois l'étape réussie.
                "explanation_text": step.explanation_text if done else "",
                "explain_ref": step.explain_ref if done else "",
            }
            extra = STEP_TYPES[step.type].panel
            if i == position and extra is not None:
                entry.update(extra(step))  # champs propres au type, pour l'étape courante
            steps.append(entry)
        altered = run.get("quiz") if engine.rest_state == "quiz_altered" else None
        failed = run.get("restore_failed")
        return {
            "quiz_altered": _public_quiz(altered),
            "restore_failed": {"reason_text": str(failed.get("reason_text") or "")}
            if isinstance(failed, dict)
            else None,
            "title_text": scenario.title_text,
            "mode": scenario.mode,
            "mode_text": MODE_TEXTS[scenario.mode],
            "current_step_id": current if position < len(ids) else "",
            "steps": steps,
        }
