"""Catalogue des `kind` et modèle pydantic de chaque `payload` (AD-17).

Une story ajoute un `kind` (une valeur de `Kind` et une entrée de `PAYLOADS`) sans toucher
l'enveloppe. Les modèles sont en ajout seulement : un champ nouveau a une valeur par défaut.

Module feuille (AD-1) : les schémas de `contracts` (`DiagnosticCheck`, puis `RepoState` et les
vues) ne sont pas importés ici ; leurs charges sont transportées en dictionnaires, validés par
leur producteur.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict


class Kind(StrEnum):
    """`kind` fixés par AD-17."""

    ENGINE_STATE = "engine_state"
    OP_STARTED = "op_started"
    TERMINAL_OUTPUT = "terminal_output"
    OP_EXIT = "op_exit"
    STATE_PROJECTED = "state_projected"
    STEP_VERDICT = "step_verdict"
    STEP_EXPLANATION = "step_explanation"
    ANSWER_CORRECTED = "answer_corrected"
    HINT_OPENED = "hint_opened"
    QUIZ_ALTERED = "quiz_altered"
    RESTORE_STARTED = "restore_started"
    RESTORE_ENDED = "restore_ended"
    EXTERNAL_CHANGE = "external_change"
    CHECK_UPDATED = "check_updated"
    PR_UPDATED = "pr_updated"
    PROGRESS_UPDATED = "progress_updated"
    DIAGNOSTIC_CHECK = "diagnostic_check"
    RESYNC_REQUIRED = "resync_required"
    APP_ERROR = "app_error"


SEQUENCE_KINDS = frozenset(
    {
        Kind.ENGINE_STATE,
        Kind.OP_STARTED,
        Kind.OP_EXIT,
        Kind.STATE_PROJECTED,
        Kind.STEP_VERDICT,
        Kind.STEP_EXPLANATION,
        Kind.RESYNC_REQUIRED,
    }
)
"""`kind` réservés au séquenceur de la file (AD-1) : une opération ne les émet jamais elle-même."""

EngineStateName = Literal["idle", "command", "quiz_altered", "restoring", "setup", "exporting"]
"""États d'un espace (AD-1)."""

Stream = Literal["stdout", "stderr", "app", "refused", "exit"]
"""Flux d'une sortie de terminal ; `exit` porte le code de sortie non nul (texte du serveur)."""


class _Payload(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class _OpenPayload(BaseModel):
    """Charge dont le schéma est fixé par la story qui l'émet ; en attendant, champs libres."""

    model_config = ConfigDict(frozen=True, extra="allow")


class EngineState(_Payload):
    state: EngineStateName
    reason_text: str = ""


class OpStarted(_Payload):
    intent: str
    """Intention (`terminal_line`…) ou opération interne (`external_change`, `setup`)."""


class Span(_Payload):
    """Passage liable d'une sortie (SHA, ref, chemin, fichier:ligne), résolu contre le
    `RepoState` : seuls les éléments qui existent dans le bac à sable sont liables (AD-2).

    `start` et `end` sont des positions en unités UTF-16 dans `text` de la ligne (celles de
    `String.prototype.slice`) ; `text` répète le passage pour contrôle.
    """

    start: int
    end: int
    text: str
    element_id: str


class TerminalOutput(_Payload):
    stream: Stream
    text: str
    lang: str = ""
    """`fr` ou `en`, déterminé par le serveur ; vide si la sortie n'a pas de langue."""
    spans: list[Span] = []


class OutputSpans(_Payload):
    """Passages liables d'une sortie, résolus à nouveau contre l'état d'après l'opération."""

    seq: int
    """`seq` de l'événement `terminal_output` concerné."""
    spans: list[Span] = []


class OpExit(_Payload):
    code: int | None
    """Code de sortie ; `None` : l'opération n'a pas abouti (voir l'`app_error` qui précède)."""
    duration_ms: int


class StateProjected(_Payload):
    views: dict[str, Any] = {}
    """Projections calculées par le serveur (AD-2) : `contracts.Views` sérialisé (module
    feuille : pas d'import de `contracts`), validé par `projections` qui le produit."""
    fingerprint: str = ""
    """Empreinte canonique de l'espace après l'opération (AD-6) ; vide si l'espace est absent."""
    output_spans: list[OutputSpans] = []
    """Sorties de l'opération dont les passages liables changent avec le nouvel état (un SHA
    créé par la commande, une branche supprimée) : le front remplace leurs `spans`."""


class StepVerdict(_Payload):
    step_id: str
    passed: bool
    reason_text: str = ""


class StepExplanation(_Payload):
    step_id: str
    explanation_text: str
    explain_ref: str = ""


class RestoreEnded(_Payload):
    status: Literal["ok", "restore_failed"]


class ExternalChange(_Payload):
    fingerprint: str


class ResyncRequired(_Payload):
    reason_text: str


class AppErrorPayload(_Payload):
    cause_text: str
    action_text: str


class AnswerCorrected(_OpenPayload):
    pass


class HintOpened(_OpenPayload):
    pass


class QuizAltered(_OpenPayload):
    pass


class RestoreStarted(_OpenPayload):
    pass


class CheckUpdated(_OpenPayload):
    pass


class PrUpdated(_OpenPayload):
    pass


class ProgressUpdated(_OpenPayload):
    pass


class DiagnosticCheckPayload(_OpenPayload):
    """`contracts.DiagnosticCheck` sérialisé (module feuille : pas d'import de `contracts`)."""


PAYLOADS: dict[Kind, type[BaseModel]] = {
    Kind.ENGINE_STATE: EngineState,
    Kind.OP_STARTED: OpStarted,
    Kind.TERMINAL_OUTPUT: TerminalOutput,
    Kind.OP_EXIT: OpExit,
    Kind.STATE_PROJECTED: StateProjected,
    Kind.STEP_VERDICT: StepVerdict,
    Kind.STEP_EXPLANATION: StepExplanation,
    Kind.ANSWER_CORRECTED: AnswerCorrected,
    Kind.HINT_OPENED: HintOpened,
    Kind.QUIZ_ALTERED: QuizAltered,
    Kind.RESTORE_STARTED: RestoreStarted,
    Kind.RESTORE_ENDED: RestoreEnded,
    Kind.EXTERNAL_CHANGE: ExternalChange,
    Kind.CHECK_UPDATED: CheckUpdated,
    Kind.PR_UPDATED: PrUpdated,
    Kind.PROGRESS_UPDATED: ProgressUpdated,
    Kind.DIAGNOSTIC_CHECK: DiagnosticCheckPayload,
    Kind.RESYNC_REQUIRED: ResyncRequired,
    Kind.APP_ERROR: AppErrorPayload,
}
"""Modèle de `payload` de chaque `kind`."""


def validate_payload(kind: Kind | str, payload: BaseModel | dict[str, Any]) -> dict[str, Any]:
    """Valide `payload` contre le modèle de `kind` ; rend le dictionnaire JSON à publier."""
    model = PAYLOADS[Kind(kind)]
    if isinstance(payload, BaseModel):
        if not isinstance(payload, model):
            raise TypeError(f"charge {type(payload).__name__} invalide pour « {kind} »")
        return payload.model_dump(mode="json")
    return model.model_validate(payload).model_dump(mode="json")
