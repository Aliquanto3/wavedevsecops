"""Enveloppe, catalogue des `kind` et journal à tampon circulaire (AD-17)."""

from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from wavedevsecops.events import (
    DIAGNOSTIC_CHECK,
    PAYLOADS,
    SEQUENCE_KINDS,
    EventLog,
    Kind,
    OpExit,
    TerminalOutput,
    validate_payload,
)
from wavedevsecops.events.journal import RESYNC_BOOT_TEXT, RESYNC_GAP_TEXT

AD17_KINDS = {
    "engine_state",
    "op_started",
    "terminal_output",
    "op_exit",
    "state_projected",
    "step_verdict",
    "step_explanation",
    "answer_corrected",
    "hint_opened",
    "quiz_altered",
    "restore_started",
    "restore_ended",
    "external_change",
    "check_updated",
    "pr_updated",
    "progress_updated",
    "diagnostic_check",
    "resync_required",
    "app_error",
}


def test_catalogue_complet_avec_un_modele_par_kind() -> None:
    assert {k.value for k in Kind} == AD17_KINDS
    assert set(PAYLOADS) == set(Kind)
    assert DIAGNOSTIC_CHECK == "diagnostic_check"
    assert SEQUENCE_KINDS <= set(Kind)


def test_charges_validees() -> None:
    assert validate_payload("op_exit", {"code": 0, "duration_ms": 3}) == {
        "code": 0,
        "duration_ms": 3,
    }
    with pytest.raises(ValidationError):
        validate_payload(Kind.OP_EXIT, {"code": 0})
    with pytest.raises(ValidationError):
        validate_payload(Kind.TERMINAL_OUTPUT, {"stream": "tty", "text": "x"})
    with pytest.raises(TypeError):
        validate_payload(Kind.OP_EXIT, TerminalOutput(stream="app", text="x"))
    with pytest.raises(ValueError):
        validate_payload("inconnu", {})


def _log(capacity: int = 5) -> EventLog:
    return EventLog("llm.demo.A", "boot1", capacity)


def _out(log: EventLog, text: str, op_id: str | None = "op") -> None:
    log.publish(
        Kind.TERMINAL_OUTPUT, TerminalOutput(stream="stdout", text=text), epoch=2, op_id=op_id
    )


def test_enveloppe_et_seq_strictement_croissant() -> None:
    log = _log()
    _out(log, "a")
    env = log.publish(Kind.OP_EXIT, OpExit(code=0, duration_ms=1), epoch=2, op_id="op")
    assert env.seq == 2 and log.seq == 2
    assert env.event_id == "boot1:2"
    dumped = env.model_dump(mode="json")
    assert set(dumped) == {
        "boot_id",
        "seq",
        "ts",
        "workspace_id",
        "epoch",
        "op_id",
        "kind",
        "payload",
    }
    assert dumped["kind"] == "op_exit" and dumped["workspace_id"] == "llm.demo.A"
    assert dumped["ts"].endswith("+00:00") and "." in dumped["ts"]  # milliseconde, fuseau
    sse = env.to_sse()
    assert sse.startswith("id: boot1:2\ndata: ") and sse.endswith("\n\n")
    assert json.loads(sse.split("data: ", 1)[1])["payload"] == {"code": 0, "duration_ms": 1}


def test_reprise_depuis_le_tampon() -> None:
    log = _log()
    for text in "abc":
        _out(log, text)
    received = []
    missed, detach = log.attach("boot1:1", received.append)
    assert [e.seq for e in missed] == [2, 3]
    _out(log, "d")
    assert [e.seq for e in received] == [4]
    detach()
    _out(log, "e")
    assert len(received) == 1


def test_premiere_connexion_et_reprise_a_jour() -> None:
    log = _log()
    _out(log, "a")
    assert log.attach(None, lambda e: None)[0] == []
    assert log.attach("boot1:1", lambda e: None)[0] == []


@pytest.mark.parametrize(
    "last", ["autre:1", "boot1:x", "n'importe", "boot1:99", "boot1:²", "boot1:٣"]
)
def test_reprise_impossible(last: str) -> None:
    log = _log()
    _out(log, "a")
    missed, _ = log.attach(last, lambda e: None)
    assert missed is None


def test_seq_sorti_du_tampon_demande_une_resynchronisation() -> None:
    log = _log(capacity=3)
    for text in "abcdef":
        _out(log, text)
    assert log.attach("boot1:2", lambda e: None)[0] is None  # 3 est sorti du tampon
    assert [e.seq for e in log.attach("boot1:3", lambda e: None)[0]] == [4, 5, 6]


def test_resync_hors_journal() -> None:
    log = _log()
    _out(log, "a")
    env = log.resync_envelope(log.resync_reason("autre:4"), epoch=2)
    assert env.kind == Kind.RESYNC_REQUIRED and env.seq == 1 and log.seq == 1
    assert env.payload == {"reason_text": RESYNC_BOOT_TEXT}
    assert log.resync_reason("boot1:0") == RESYNC_GAP_TEXT


def test_abonne_en_echec_ne_bloque_pas_la_publication() -> None:
    log = _log()

    def broken(_env: object) -> None:
        raise RuntimeError("flux fermé")

    log.attach(None, broken)
    _out(log, "a")
    assert log.seq == 1
