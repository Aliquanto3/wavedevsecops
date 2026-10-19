"""Désignation côté serveur, en un seul essai (Story 5.2, AD-2, AD-14, AD-17).

- `answer_submit{slots: [element_id], step_id}` : corrige la désignation de l'étape courante
  (type `designate`) contre le `RepoState` courant, émet `answer_corrected`, consigne la
  réponse dans `run.json["answers"]` (le premier essai, jamais remplacé) ; la validation
  d'étape ferme alors l'étape et son fait `quiz_first_attempt` part avec `step_validated`.
  Une seconde soumission sur la même étape est refusée (409).
- `GET /api/ws/<id>/resolve_sha?prefix=` : aperçu d'un commit à partir d'un préfixe de SHA, en
  lecture seule (`resolve_sha`) ; il ne consomme pas l'essai.
- `mark_views` : la projection marque `designable` tous les éléments des types acceptés par
  l'étape courante, pas seulement les bonnes réponses.
"""

from __future__ import annotations

import copy
import logging
import re
from typing import Any

from pydantic import BaseModel, Field, ValidationError

from wavedevsecops.contracts import AppError, RepoState, element_id, parse_element_id
from wavedevsecops.engine.intents import INTENTS, Intent, register_intent
from wavedevsecops.engine.operations import (
    OpContext,
    Operation,
    OperationRefused,
    WorkspaceEngine,
)
from wavedevsecops.engine.runfile import load_run, save_run
from wavedevsecops.events import Kind
from wavedevsecops.events.catalog import AnswerCorrected, SlotMark
from wavedevsecops.scenarios import Scenario
from wavedevsecops.scenarios.steps.designate import ANSWER_KEY

log = logging.getLogger("wavedevsecops")

INTENT = "answer_submit"
EXIT_REFUSED = 2
MIN_PREFIX = 7
NOT_DESIGNATION_TEXT = "Aucune désignation n'est attendue à cette étape."
ALREADY_TEXT = (
    "Vous avez déjà répondu à cette question : une seule tentative est permise. "
    "La correction est affichée."
)
UNDEFINED_TEXT = "Ce scénario ne définit pas la bonne réponse de cette question."
_HEX = re.compile(r"^[0-9a-f]+$")
VIEW_GROUPS = ("staged", "unstaged", "untracked")


# ----------------------------------------------------------------- marques
def accepted_types(step: Any) -> frozenset[str] | None:
    """Types d'éléments désignables de `step` ; `None` si ce n'est pas une désignation."""
    return frozenset(step.accept) if step is not None and step.type == "designate" else None


def _flag(item: dict[str, Any], accept: frozenset[str] | None) -> None:
    kind = str(item.get("element_id", "")).partition(":")[0]
    item["designable"] = accept is None or kind in accept


def mark_views(views: dict[str, Any], accept: frozenset[str] | None) -> dict[str, Any]:
    """Copie de `views` dont chaque élément porte `designable` : vrai pour les types de
    `accept` ; `None` (aucune désignation en cours) : tout est désignable, valeur par défaut."""
    if not views:
        return views
    marked = copy.deepcopy(views)
    for node in (marked.get("graph") or {}).get("nodes") or []:
        _flag(node, accept)
        for label in node.get("refs") or []:
            _flag(label, accept)
    staging = marked.get("staging") or {}
    for group in VIEW_GROUPS:
        for item in staging.get(group) or []:
            _flag(item, accept)
    remote = marked.get("remote") or {}
    for branch in remote.get("branches") or []:
        _flag(branch, accept)
    for card in remote.get("pulls") or []:
        _flag(card, accept)
        for check in card.get("checks") or []:
            _flag(check, accept)
        for entry in (card.get("review") or {}).get("entries") or []:
            _flag(entry, accept)
    return marked


# --------------------------------------------------------------- correction
def state_of(views: dict[str, Any] | None) -> RepoState | None:
    repo = (views or {}).get("repo")
    if not isinstance(repo, dict):
        return None
    try:
        return RepoState.model_validate(repo)
    except ValidationError:
        return None


def describe(element: str, state: RepoState | None) -> str:
    """Un élément en mots, pour les phrases de correction (écrites par le serveur, AD-2)."""
    try:
        kind, segments = parse_element_id(element)
    except ValueError:
        return element
    if kind == "commit":
        commit = next((c for c in state.commits if c.sha == segments[0]), None) if state else None
        return f"{segments[0][:7]} « {commit.subject} »" if commit else segments[0][:7]
    if kind == "ref":
        ref = next((r for r in state.refs if r.name == segments[0]), None) if state else None
        return f"la référence {ref.short_name if ref else segments[0]}"
    if kind == "tag":
        return f"le tag {segments[0]}"
    if kind == "path":
        return f"le fichier {segments[1]}"
    return element


def _exists(element: str, state: RepoState | None) -> bool:
    """Vrai si l'élément existe dans le dépôt ; les types que la projection ne couvre pas encore
    (lignes de diff, PR, contrôles…) ne sont vérifiés que par leur forme."""
    if state is None:
        return True
    kind, segments = parse_element_id(element)
    if kind == "commit":
        return any(c.sha == segments[0] for c in state.commits)
    if kind == "ref":
        return segments[0] == "HEAD" or any(r.name == segments[0] for r in state.refs)
    if kind == "tag":
        return any(r.kind == "tag" and r.short_name == segments[0] for r in state.refs)
    return True


def _resolve(value: str, aliases: dict[str, str]) -> str:
    return aliases.get(value[1:], "") if value.startswith("@") else value


def correct(
    step: Any, aliases: dict[str, str], chosen: list[str], state: RepoState | None
) -> AnswerCorrected:
    """Corrige `chosen` (un `element_id` par case) contre les bonnes réponses de `step`."""
    marks: list[SlotMark] = []
    for slot, element in zip(step.slots, chosen, strict=True):
        accepted = [e for e in (_resolve(a, aliases) for a in slot.answers) if e]
        primary = _resolve(slot.primary, aliases)
        if not primary:
            raise OperationRefused(UNDEFINED_TEXT)
        ok = element in accepted
        equivalent = ok and element != primary
        target, mine = describe(primary, state), describe(element, state)
        if not ok:
            text = (
                f"{slot.label_text} : {mine} n'est pas l'élément en cause ; l'attendu est {target}."
            )
            others = [describe(e, state) for e in accepted if e != primary]
            if others:
                text += f" Étaient aussi acceptés : {', '.join(others)}."
        elif equivalent:
            text = f"{slot.label_text} : {mine} convient aussi ; l'élément principal est {target}."
        else:
            text = f"{slot.label_text} : c'est bien {mine}."
        marks.append(
            SlotMark(
                slot_id=slot.slot_id,
                element_id=element,
                correct=ok,
                equivalent=equivalent,
                expected_element_id=primary,
                accepted_element_ids=accepted,
                text=text,
                label_text=slot.label_text,
                element_texts={
                    e: describe(e, state) for e in dict.fromkeys([element, primary, *accepted])
                },
            )
        )
    right = sum(m.correct for m in marks)
    if right == len(marks):
        summary = "Désignation juste."
    elif right == 0:
        summary = "Désignation fausse : la correction est affichée, vous n'avez plus d'essai."
    else:
        summary = (
            f"Désignation partielle : {right} case(s) juste(s) sur {len(marks)}. "
            "La correction est affichée, vous n'avez plus d'essai."
        )
    return AnswerCorrected(
        step_id=step.step_id, correct=right == len(marks), slots=marks, summary_text=summary
    )


# ------------------------------------------------------------------- intention
class AnswerSubmit(BaseModel):
    """Corps de `answer_submit` : un `element_id` par case, dans l'ordre des cases."""

    slots: list[str] = Field(min_length=1, max_length=20)
    step_id: str = Field(min_length=1, max_length=100)
    """Étape visée, obligatoire : sans elle, un second envoi parti après la fermeture de l'étape
    serait corrigé contre la désignation suivante et y consommerait l'unique essai."""


def _scenario(engine: WorkspaceEngine, run: dict[str, Any]) -> Scenario | None:
    from wavedevsecops.engine.steps import StepRunner  # noqa: PLC0415 - évite le cycle

    return StepRunner(engine.settings).scenario(run)


def _current_step(scenario: Scenario | None, run: dict[str, Any]) -> Any:
    step_id = run.get("step_id")
    return next((s for s in scenario.steps if s.step_id == step_id), None) if scenario else None


def _verify(
    scenario: Scenario | None, run: dict[str, Any], body: AnswerSubmit, views: dict[str, Any]
) -> Any:
    """Refus connus d'avance (409) ; rend l'étape à corriger."""
    step = _current_step(scenario, run)
    answers = run.get("answers") or {}
    if step is None or step.type != "designate":
        raise OperationRefused(ALREADY_TEXT if body.step_id in answers else NOT_DESIGNATION_TEXT)
    if body.step_id != step.step_id:
        raise OperationRefused(ALREADY_TEXT if body.step_id in answers else NOT_DESIGNATION_TEXT)
    if step.step_id in answers:
        return step  # arrêt entre l'écriture de la réponse et la fermeture : on termine
    if len(body.slots) != len(step.slots):
        raise OperationRefused(
            f"Cette question attend {len(step.slots)} réponse(s) : "
            f"désignez un élément pour chaque case ({len(body.slots)} reçue(s))."
        )
    state = state_of(views)
    for element in body.slots:
        try:
            kind, _ = parse_element_id(element)
        except ValueError:
            raise OperationRefused(
                "Une des réponses n'est pas un élément du dépôt. Désignez-le dans les vues."
            ) from None
        if kind not in step.accept:
            raise OperationRefused(
                f"Ce type d'élément n'est pas accepté ici (types acceptés : "
                f"{', '.join(step.accept)})."
            )
        if not _exists(element, state):
            raise OperationRefused(
                "Cet élément n'existe pas dans le dépôt de ce bac à sable. Désignez-en un autre."
            )
    return step


def build_answer_submit(engine: WorkspaceEngine, body: AnswerSubmit) -> Operation:
    layout = engine.layout

    def preflight() -> None:
        try:
            run = load_run(layout)
        except AppError as error:
            raise OperationRefused(f"{error.cause_text} {error.action_text}") from None
        _verify(_scenario(engine, run), run, body, engine.last_projection.views)

    preflight()

    def run_op(ctx: OpContext) -> int:
        run = load_run(ctx.layout)
        try:
            step = _verify(_scenario(engine, run), run, body, ctx.last_views)
        except OperationRefused as refused:
            ctx.output(refused.reason_text, "refused")
            return EXIT_REFUSED
        answers = dict(run.get("answers") or {})
        record = answers.get(step.step_id)
        if record is None:
            try:
                payload = correct(
                    step,
                    dict(run.get("aliases") or {}),
                    body.slots,
                    state_of(ctx.last_views),
                )
            except OperationRefused as refused:
                ctx.output(refused.reason_text, "refused")
                return EXIT_REFUSED
            answers[step.step_id] = {
                "slots": list(body.slots),
                "correct": payload.correct,
                "payload": payload.model_dump(mode="json"),
            }
            # `run.json` d'abord : le premier essai est acquis avant d'être publié.
            save_run(ctx.layout, {**run, "answers": answers})
        else:
            payload = AnswerCorrected.model_validate(record["payload"])
        ctx.emit(Kind.ANSWER_CORRECTED, payload)
        ctx.data[ANSWER_KEY] = step.step_id
        return 0

    return Operation(
        INTENT, run_op, writes=False, reason_text="Correction de votre désignation en cours."
    )


def register_intents() -> None:
    """Enregistre `answer_submit` (idempotent)."""
    if INTENT not in INTENTS:
        register_intent(Intent(INTENT, AnswerSubmit, build_answer_submit))


# ---------------------------------------------------------------- resolve_sha
def resolve_sha(views: dict[str, Any] | None, prefix: str) -> tuple[int, dict[str, Any]]:
    """`(statut HTTP, corps)` de `GET …/resolve_sha?prefix=` : lecture seule, sans essai."""
    wanted = prefix.strip().lower()
    if len(wanted) < MIN_PREFIX or len(wanted) > 40 or not _HEX.match(wanted):
        return 422, {
            "reason_text": f"Saisissez au moins {MIN_PREFIX} caractères hexadécimaux "
            "(0 à 9, a à f) du SHA du commit."
        }
    state = state_of(views)
    found = [c for c in (state.commits if state else []) if c.sha.startswith(wanted)]
    if not found:
        return 404, {
            "reason_text": "Aucun commit ne correspond à ce SHA dans le bac à sable. "
            "Vérifiez le SHA, ou désignez le commit dans le graphe."
        }
    if len(found) > 1:
        return 409, {
            "reason_text": f"Plusieurs commits commencent par « {wanted} » : "
            "saisissez quelques caractères de plus."
        }
    commit = found[0]
    return 200, {
        "element_id": element_id("commit", commit.sha),
        "sha": commit.sha,
        "short_sha": commit.sha[:7],
        "subject": commit.subject,
        "author_text": commit.author_name,
        "actor": commit.actor,
    }


__all__ = [
    "ALREADY_TEXT",
    "INTENT",
    "NOT_DESIGNATION_TEXT",
    "AnswerSubmit",
    "accepted_types",
    "build_answer_submit",
    "correct",
    "describe",
    "mark_views",
    "register_intents",
    "resolve_sha",
]
