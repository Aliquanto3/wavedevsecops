"""Intention `run_exercise_code` (AD-13, AD-17, AD-19) : lancer, à la demande, le code d'exercice.

La confirmation est vérifiée ici, côté serveur : sans `confirmed: true`, l'intention est refusée
(409). Le cookie de session et l'`Origin` sont vérifiés en amont par l'intergiciel de `app.py`.
L'opération passe par la file en état `command`. Un instantané (`reason="exercise"`, API de la
story 4.3, contrôlé par l'empreinte de l'espace) précède toute écriture du lancement ; le
processus est ensuite suivi au fil de l'eau, et Ctrl+C (`interrupt`) ou la mise en veille de
l'espace arrête son arbre.
"""

from __future__ import annotations

import logging

from pydantic import BaseModel, ConfigDict

from wavedevsecops import llmrun
from wavedevsecops.contracts import AppError
from wavedevsecops.engine import (
    INTENTS,
    Intent,
    OpContext,
    Operation,
    OperationRefused,
    WorkspaceEngine,
    fingerprint,
    parse_workspace_id,
    register_intent,
    resolve_git,
    take_snapshot,
)
from wavedevsecops.engine.snapshots import SnapshotError
from wavedevsecops.gitio import Git

log = logging.getLogger("wavedevsecops")

NOT_CONFIRMED_TEXT = (
    "Ce code peut appeler un service en ligne : le lancement doit être confirmé. "
    "Cliquez sur « Exécuter le code (réseau possible) », puis acceptez la confirmation."
)
WRONG_TRACK_TEXT = "Le code d'exercice à lancer n'existe que dans le parcours avec l'IA."
RUNNING_TEXT = "Le code d'exercice tourne (il peut appeler un service en ligne)."
TIMEOUT_TEXT = "Le code d'exercice n'a pas fini à temps : il a été arrêté."
INTERRUPTED_TEXT = "Le code d'exercice a été arrêté."
EXIT_INTERRUPTED = 130
EXIT_TIMEOUT = 124
SNAPSHOT_REASON = "exercise"
SNAPSHOT_CAUSE = (
    "L'état de l'espace n'a pas pu être sauvegardé avant le lancement.",
    "Le code n'a pas été lancé. Vérifiez l'espace disque, puis réessayez.",
)


class RunExerciseCode(BaseModel):
    """Corps de l'intention : la confirmation de l'apprenant, rien d'autre."""

    model_config = ConfigDict(extra="forbid")

    confirmed: bool = False


def _snapshot(ctx: OpContext) -> None:
    """Instantané d'avant le lancement (AD-6), contrôlé par l'empreinte de l'espace."""
    git = Git.for_workspace(
        ctx.git_path or resolve_git(ctx.settings), ctx.layout.root, ctx.settings
    )
    try:
        take_snapshot(
            ctx.layout,
            git,
            ctx.settings,
            reason=SNAPSHOT_REASON,
            expected=fingerprint(ctx.layout, git),
        )
    except SnapshotError:
        raise
    except OSError:
        log.exception("Instantané avant le code d'exercice de %s", ctx.workspace_id)
        raise AppError(*SNAPSHOT_CAUSE) from None


def _build(engine: WorkspaceEngine, body: RunExerciseCode) -> Operation:
    if body.confirmed is not True:
        raise OperationRefused(NOT_CONFIRMED_TEXT)
    if parse_workspace_id(engine.workspace_id)[0] != "llm":
        raise OperationRefused(WRONG_TRACK_TEXT)

    def run(ctx: OpContext) -> int:
        _snapshot(ctx)
        ctx.output(f"$ {llmrun.COMMAND}", "app")
        try:
            handle = llmrun.start_exercise(ctx.layout, ctx.settings)
        except llmrun.ExerciseUnavailable as exc:
            raise AppError(
                f"Le code d'exercice n'a pas pu être lancé : {exc.reason}.",
                "Vérifiez le diagnostic, puis réessayez.",
            ) from None
        ctx.on_interrupt(handle.terminate)
        for chunk in handle.chunks():
            if chunk is not None:
                ctx.output(chunk.text, chunk.stream)
        if handle.timed_out:
            ctx.output(TIMEOUT_TEXT, "app")
            return EXIT_TIMEOUT
        if handle.interrupted or ctx.interrupted:
            ctx.output(INTERRUPTED_TEXT, "app")
            return EXIT_INTERRUPTED
        code = handle.returncode
        return code if code is not None else EXIT_INTERRUPTED

    return Operation(llmrun.INTENT, run, state="command", validate=False, reason_text=RUNNING_TEXT)


def register_exercise_intent() -> None:
    """Enregistre `run_exercise_code` (une fois par processus)."""
    if llmrun.INTENT not in INTENTS:
        register_intent(Intent(llmrun.INTENT, RunExerciseCode, _build))
