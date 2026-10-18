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
from wavedevsecops.engine.designation import accepted_types, mark_views
from wavedevsecops.engine.operations import (
    OpContext,
    Projection,
    Projector,
    StepOutcome,
    WorkspaceEngine,
)
from wavedevsecops.engine.runfile import load_run, save_run
from wavedevsecops.events import StepObserved, StepVerdict
from wavedevsecops.progress.facts import ProgressStore
from wavedevsecops.progress.summary import FIRST_ATTEMPT_STEP_TYPES, build_summary
from wavedevsecops.scenarios import (
    STEP_TYPES,
    Scenario,
    ScenarioError,
    load_scenario,
    scenario_files,
)
from wavedevsecops.scenarios.order import catalogue_rank, section_of
from wavedevsecops.scenarios.steps import StepContext
from wavedevsecops.wsfs import Layout

log = logging.getLogger("wavedevsecops")

MODE_TEXTS = {
    "A": "Mode A : vous tapez vous-même les commandes ; chaque étape se valide sur l'état "
    "réel du dépôt, quelle que soit la commande tapée.",
    "B": "Mode B : un agent a déjà agi dans le dépôt ; vous relisez son travail.",
}


NO_NEXT_TEXT = "Aucun autre scénario n'est disponible pour l'instant."


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

    def __init__(self, settings: Settings, progress: ProgressStore | None = None) -> None:
        self._settings = settings
        self._progress = progress
        self._cache: dict[Path, tuple[tuple[int, int], Scenario | None]] = {}

    def scenario(self, run: dict[str, Any]) -> Scenario | None:
        """Scénario de l'espace (relu quand son fichier change) ; `None` s'il n'existe plus ou
        s'il est invalide (journalisé une fois par version du fichier : l'étape reste ouverte)."""
        scenario_id, mode = run.get("scenario_id"), run.get("mode")
        if not isinstance(scenario_id, str) or not isinstance(mode, str):
            return None
        return self._load(self._settings.scenarios_path() / f"{scenario_id}.{mode}.yaml")

    def _load(self, path: Path) -> Scenario | None:
        """Scénario du fichier, relu seulement quand il change (date, taille)."""
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

    def designating(self, projector: Projector) -> Projector:
        """Projecteur qui marque `designable` selon l'étape courante (désignation, story 5.2) :
        les éléments des types acceptés, et eux seuls, quand l'étape courante est une
        désignation ; sinon les vues restent telles quelles."""

        def project(ctx: OpContext) -> Projection:
            projection = projector(ctx)
            try:
                run = self._run(ctx.layout)
                scenario = self.scenario(run) if run is not None else None
                step = (
                    next(
                        (s for s in scenario.steps if s.step_id == (run or {}).get("step_id")), None
                    )
                    if scenario
                    else None
                )
                accept = accepted_types(step)
            except Exception:  # noqa: BLE001 - un `run.json` illisible ne bloque pas la projection
                log.exception("Marques designable de %s", ctx.workspace_id)
                return projection
            if accept is None:
                return projection
            return replace(projection, views=mark_views(projection.views, accept))

        return project

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
            facts = self._quiz_facts(run, [step.step_id])
            facts += self._facts_of(run, [step.step_id], finished=following is None)
            after = accepted_types(steps[index + 1]) if index + 1 < len(steps) else None
            remarked = (
                mark_views(projection.views, after)
                if accepted_types(step) != after  # entrée dans une désignation, ou sortie
                else None
            )
            return replace(
                StepOutcome.explained(published, step.explanation_text, step.explain_ref),
                facts=tuple(facts),
                views=remarked,
            )
        published = StepVerdict(
            step_id=step.step_id,
            passed=False,
            status=verdict.status,
            reason_text=verdict.reason_text,
            expected_text=verdict.expected_text,
            observed=[StepObserved(text=o.text, element_id=o.element_id) for o in verdict.observed],
        )
        return StepOutcome(published, facts=tuple(self._quiz_facts(run, [step.step_id])))

    # ----------------------------------------------------------------- faits
    @staticmethod
    def _facts_of(run: dict[str, Any], step_ids: list[str], *, finished: bool) -> list[dict]:
        """Faits du premier passage établis par `run.json` (AD-14) : étapes validées, fin."""
        where = {
            "track": run.get("track"),
            "scenario_id": run.get("scenario_id"),
            "mode": run.get("mode"),
        }
        answers = run.get("answers") if isinstance(run.get("answers"), dict) else {}
        facts: list[dict] = []
        for sid in step_ids:
            answer = answers.get(sid)
            if isinstance(answer, dict) and isinstance(answer.get("correct"), bool):
                # Désignation : le premier essai (juste ou faux) compte pour le score (AD-14).
                facts.append(
                    {
                        "kind": "quiz_first_attempt",
                        "step_id": sid,
                        "correct": answer["correct"],
                        **where,
                    }
                )
            facts.append({"kind": "step_validated", "step_id": sid, **where})
        if finished:
            facts.append({"kind": "scenario_completed", **where})
        return facts

    @staticmethod
    def _quiz_facts(run: dict[str, Any], step_ids: list[str] | None = None) -> list[dict]:
        """Premiers essais de quiz (AD-14) consignés dans `run.json.quiz_first` par le choix.

        Le magasin garde le premier fait de chaque étape : un essai suivant, ou le même essai
        rejoué après un arrêt brutal, n'ajoute rien.
        """
        first = run.get("quiz_first")
        if not isinstance(first, dict):
            return []
        where = {
            "track": run.get("track"),
            "scenario_id": run.get("scenario_id"),
            "mode": run.get("mode"),
        }
        return [
            {
                "kind": "quiz_first_attempt",
                "step_id": sid,
                "correct": entry.get("correct") is True,
                **where,
            }
            for sid, entry in first.items()
            if isinstance(sid, str)
            and isinstance(entry, dict)
            and (step_ids is None or sid in step_ids)
        ]

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
        return self._quiz_facts(run) + self._replay_steps(run, scenario)

    def _replay_steps(self, run: dict[str, Any], scenario: Scenario) -> list[dict[str, Any]]:
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

    # ----------------------------------------------------------------- bilan
    def _next_scenario(self, scenario: Scenario, track: str) -> dict[str, str] | None:
        """Scénario suivant dans l'ordre du catalogue (FR-9, `scenarios.order`) : même section,
        même mode, servant le même parcours ; `None` s'il n'y en a pas."""
        section = section_of(scenario.section)
        current = catalogue_rank(scenario.scenario_id)
        following: Scenario | None = None
        for path in scenario_files(self._settings):
            other = self._load(path)
            if (
                other is None
                or not other.catalogue
                or other.mode != scenario.mode
                or section_of(other.section) != section
                or track not in other.tracks
                or catalogue_rank(other.scenario_id) <= current
            ):
                continue
            if following is None or catalogue_rank(other.scenario_id) < catalogue_rank(
                following.scenario_id
            ):
                following = other
        if following is None:
            return None
        return {
            "scenario_id": following.scenario_id,
            "mode": following.mode,
            "track": track,
            "title_text": following.title_text,
        }

    def _summary(self, run: dict[str, Any], scenario: Scenario) -> dict[str, Any] | None:
        """Bilan du scénario terminé, lu dans `progress.json` ; `None` si illisible."""
        if self._progress is None:
            return None
        track = str(run.get("track") or "")
        try:
            derived = self._progress.progress(track, scenario.scenario_id, scenario.mode)
            asked = sum(1 for s in scenario.steps if s.type in FIRST_ATTEMPT_STEP_TYPES)
            summary = build_summary(derived, asked)
        except Exception:  # noqa: BLE001 - un suivi illisible ne bloque pas le panneau
            log.exception("Bilan de %s", scenario.key)
            return None
        summary["next"] = self._next_scenario(scenario, track)
        summary["next_none_text"] = NO_NEXT_TEXT
        return summary

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
            "summary": self._summary(run, scenario) if not current else None,
        }
