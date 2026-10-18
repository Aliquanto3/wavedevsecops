"""Quiz à exécution réelle et rétablissement de l'état (FR-15, AD-1, AD-4, AD-6, AD-14).

`quiz_choice {choice_id}` : un instantané est pris (AD-6), puis la commande du choix s'exécute
dans le terminal comme si elle y était tapée (sortie en flux, même garde que `terminal_line`).
Une bonne réponse laisse l'état produit et valide l'étape. Une mauvaise passe l'espace en
`quiz_altered` : le quiz en attente est consigné dans `run.json.quiz` (il survit à un arrêt),
`quiz_altered` est publié, et seules les commandes de lecture passent (AD-4).

`restore_state {}` : rétablit l'instantané pris avant le choix (`restore_operation`, story 4.3).
L'état revient à `idle` et `run.json.quiz` est effacé par la restauration elle-même.

Premier essai (AD-14) : `run.json.quiz_first[step_id]` garde le premier choix de l'étape, et
`quiz_altered.first_attempt` dit si le choix en cours est ce premier essai. L'enregistrement
dans `progress.json` revient à la story des faits du premier passage.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from wavedevsecops.contracts import AppError
from wavedevsecops.engine import (
    INTENTS,
    Intent,
    OpContext,
    Operation,
    OperationRefused,
    StepRunner,
    WorkspaceEngine,
    load_run,
    register_intent,
    resolve_git,
    restore_operation,
    save_run,
    take_snapshot,
)
from wavedevsecops.events import Kind
from wavedevsecops.gitio import Git
from wavedevsecops.scenarios.steps.quiz import CHOICE_KEY, QUIZ_INTENT
from wavedevsecops.terminal import _run_git
from wavedevsecops.terminal.allowlist import get_allowlist
from wavedevsecops.terminal.parse import Refused, parse_line

RESTORE_INTENT = "restore_state"
NOT_A_QUIZ_TEXT = "L'étape en cours n'est pas un quiz : ce choix n'est pas pris en compte."
UNKNOWN_CHOICE_TEXT = "Cette commande ne fait pas partie des choix de l'étape. Rechargez la page."
NOTHING_TO_RESTORE_TEXT = "Aucun état modifié par le quiz n'est à rétablir."
BAD_COMMAND_TEXT = (
    "Une commande de ce quiz n'est pas acceptée par le terminal. Le scénario est à corriger : "
    "ouvrez le diagnostic ou signalez-le à l'auteur."
)


class QuizChoice(BaseModel):
    choice_id: str = Field(min_length=1, max_length=64)


class RestoreState(BaseModel):
    pass


def build_quiz_choice(engine: WorkspaceEngine, body: QuizChoice) -> Operation:
    """Traduit un choix de quiz en opération : instantané, puis commande dans le terminal."""
    run = load_run(engine.layout)
    scenario = StepRunner(engine.settings).scenario(run)
    step = next(
        (s for s in (scenario.steps if scenario else ()) if s.step_id == run.get("step_id")), None
    )
    if step is None or step.type != "quiz":
        raise OperationRefused(NOT_A_QUIZ_TEXT)
    choice = next((c for c in step.choices if c.choice_id == body.choice_id), None)
    if choice is None:
        raise OperationRefused(UNKNOWN_CHOICE_TEXT)
    allow = get_allowlist(engine.settings)
    try:
        command = parse_line(choice.command_text, allow)
    except Refused:
        command = None
    if command is None:
        raise OperationRefused(BAD_COMMAND_TEXT)

    def run_choice(ctx: OpContext) -> int | None:
        tool = Git.for_workspace(
            ctx.git_path or resolve_git(ctx.settings), ctx.layout.root, ctx.settings
        )
        snapshot = take_snapshot(ctx.layout, tool, ctx.settings, reason="quiz")
        ctx.data[CHOICE_KEY] = choice.choice_id
        data = load_run(ctx.layout)
        first = dict(data.get("quiz_first") or {})
        first_attempt = step.step_id not in first
        if first_attempt:
            first[step.step_id] = {"choice_id": choice.choice_id, "correct": choice.correct}
        pending = None
        if not choice.correct:
            # Consigné avant la commande : un arrêt en plein quiz laisse l'espace en `quiz_altered`.
            pending = {
                "step_id": step.step_id,
                "choice_id": choice.choice_id,
                "command_text": choice.command_text,
                "explanation_text": choice.effect_text,
                "snapshot_id": snapshot.snapshot_id,
            }
        save_run(ctx.layout, {**data, "quiz_first": first, "quiz": pending})
        ctx.output(choice.command_text, "input")
        code = _run_git(ctx, command, allow)
        if pending is not None:
            ctx.set_rest_state("quiz_altered")
            ctx.emit(
                Kind.QUIZ_ALTERED,
                {
                    **{k: v for k, v in pending.items() if k != "snapshot_id"},
                    "first_attempt": first_attempt,
                },
            )
        return code

    return Operation(QUIZ_INTENT, run_choice)


def build_restore_state(engine: WorkspaceEngine, body: RestoreState) -> Operation:
    """Rétablit l'instantané pris avant le choix de quiz en attente."""
    quiz = load_run(engine.layout).get("quiz")
    if engine.rest_state != "quiz_altered" or not isinstance(quiz, dict):
        raise OperationRefused(NOTHING_TO_RESTORE_TEXT)
    try:
        snapshot_id = int(quiz["snapshot_id"])
    except KeyError, TypeError, ValueError:
        raise AppError(
            "Le quiz en attente n'a pas d'instantané à rétablir.",
            "Recommencez le scénario pour repartir d'un état sûr.",
        ) from None
    return restore_operation(snapshot_id, engine.git_path or resolve_git(engine.settings))


def register_intents() -> None:
    """Enregistre `quiz_choice` et `restore_state` (idempotent)."""
    if QUIZ_INTENT not in INTENTS:
        register_intent(Intent(QUIZ_INTENT, QuizChoice, build_quiz_choice))
    if RESTORE_INTENT not in INTENTS:
        register_intent(Intent(RESTORE_INTENT, RestoreState, build_restore_state))
