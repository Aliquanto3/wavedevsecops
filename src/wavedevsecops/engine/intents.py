"""Registre des intentions `POST /api/ws/<workspace_id>/<intent>` (AD-17).

Une intention est un corps JSON validé par un modèle pydantic, puis traduit en `Operation`
de la file. Chaque story enregistre les siennes (`terminal_line` avec le terminal,
`save_file` avec la vue Code…) sans toucher la route.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, ValidationError

from wavedevsecops.engine.operations import Operation, OperationRefused, WorkspaceEngine

CATALOGUE = (
    "terminal_line",
    "interrupt",
    "save_file",
    "open_external",
    "quiz_choice",
    "restore_state",
    "restart",
    "answer_submit",
    "hint_open",
    "pr_open",
    "pr_merge",
    "pr_request_review",
    "check_rerun",
    "check_output_seen",
    "run_exercise_code",
)
"""Intentions fixées par AD-17 (`interrupt` sera traité hors file) ; `check_output_seen`
(« Voir la sortie » d'un check, preuve `evidence_seen`) est un ajout de la story 7.4 ;
`pr_request_review` (« Demander une revue »), de la 7.5."""

_NAME = re.compile(r"^[a-z][a-z0-9]*(?:_[a-z0-9]+)*$")


class UnknownIntent(OperationRefused):
    """Intention absente du registre (404)."""


class InvalidIntent(OperationRefused):
    """Corps d'intention invalide (422)."""


@dataclass(frozen=True)
class Intent:
    name: str
    model: type[BaseModel]
    build: Callable[[WorkspaceEngine, Any], Operation]
    """Construit l'opération à partir du corps validé (instance de `model`)."""


INTENTS: dict[str, Intent] = {}


def register_intent(intent: Intent) -> None:
    if not _NAME.match(intent.name):
        raise ValueError(f"nom d'intention invalide : {intent.name}")
    if intent.name in INTENTS:
        raise ValueError(f"intention déjà enregistrée : {intent.name}")
    INTENTS[intent.name] = intent


def unregister_intent(name: str) -> None:
    INTENTS.pop(name, None)


def build_operation(engine: WorkspaceEngine, name: str, body: Any) -> Operation:
    """Valide le corps de l'intention `name` et rend son opération."""
    intent = INTENTS.get(name)
    if intent is None:
        raise UnknownIntent(f"L'action « {name} » n'existe pas dans cette version.")
    try:
        parsed = intent.model.model_validate(body if body is not None else {})
    except ValidationError:
        raise InvalidIntent(
            f"L'action « {name} » a été envoyée avec des données invalides. "
            "Rechargez la page, puis réessayez."
        ) from None
    return intent.build(engine, parsed)
