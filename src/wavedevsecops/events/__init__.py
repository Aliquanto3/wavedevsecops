"""Enveloppe d'événements, catalogue des `kind` et journal (AD-17).

Module feuille (AD-1) : n'importe rien du projet ; tout module peut l'importer.
"""

from wavedevsecops.events.catalog import (
    PAYLOADS,
    SEQUENCE_KINDS,
    AppErrorPayload,
    EngineState,
    EngineStateName,
    ExternalChange,
    Kind,
    OpExit,
    OpStarted,
    OutputSpans,
    ResyncRequired,
    Span,
    StateProjected,
    StepExplanation,
    StepVerdict,
    Stream,
    TerminalOutput,
    validate_payload,
)
from wavedevsecops.events.journal import Envelope, EventLog, Subscriber, now_iso

DIAGNOSTIC_CHECK = Kind.DIAGNOSTIC_CHECK
"""`kind` d'un événement portant un `contracts.DiagnosticCheck` (catalogue d'AD-17)."""

__all__ = [
    "DIAGNOSTIC_CHECK",
    "PAYLOADS",
    "SEQUENCE_KINDS",
    "AppErrorPayload",
    "EngineState",
    "EngineStateName",
    "Envelope",
    "EventLog",
    "ExternalChange",
    "Kind",
    "OpExit",
    "OpStarted",
    "OutputSpans",
    "ResyncRequired",
    "Span",
    "StateProjected",
    "StepExplanation",
    "StepVerdict",
    "Stream",
    "Subscriber",
    "TerminalOutput",
    "now_iso",
    "validate_payload",
]
