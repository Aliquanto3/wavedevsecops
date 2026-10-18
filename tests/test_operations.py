"""File d'opérations d'un espace : série, ordre fixe, `epoch`, erreurs (AD-1, AD-17)."""

from __future__ import annotations

import threading
from collections.abc import Iterator
from pathlib import Path

import pytest

from wavedevsecops.config import Settings
from wavedevsecops.contracts import AppError
from wavedevsecops.engine import (
    OpContext,
    Operation,
    OperationRefused,
    Projection,
    StaleOperation,
    StepOutcome,
    WorkspaceEngine,
    load_run,
    save_run,
)
from wavedevsecops.engine.manager import external_change
from wavedevsecops.engine.operations import GENERIC_ACTION, GENERIC_CAUSE
from wavedevsecops.events import Envelope, EventLog, Kind, StepExplanation, StepVerdict
from wavedevsecops.wsfs import Layout

WAIT = 20.0


class Disk:
    """Empreinte simulée de l'espace : la projection la lit."""

    def __init__(self) -> None:
        self.fingerprint = "f0"

    def project(self, ctx: OpContext) -> Projection:
        return Projection({"demo": self.fingerprint}, self.fingerprint)


@pytest.fixture
def disk() -> Disk:
    return Disk()


@pytest.fixture
def layout(tmp_path: Path) -> Layout:
    layout = Layout(tmp_path / "ws")
    save_run(layout, {"epoch": 4, "scenario_id": "demo"})
    return layout


def _validator(ctx: OpContext, projection: Projection) -> StepOutcome | None:
    return StepOutcome(
        StepVerdict(step_id="s1", passed=True),
        StepExplanation(step_id="s1", explanation_text="Bravo."),
    )


class Harness:
    def __init__(self, layout: Layout, disk: Disk, **settings: object) -> None:
        self.events: list[Envelope] = []
        self.log = EventLog("llm.demo.A", "boot", 1000)
        self.log.attach(None, self.events.append)
        self.engine = WorkspaceEngine(
            "llm.demo.A",
            layout,
            self.log,
            Settings(**settings),
            projector=disk.project,
            validator=_validator,
        )
        self.engine.start()

    def kinds(self, op_id: str | None = None) -> list[str]:
        return [e.kind.value for e in self.events if op_id is None or e.op_id == op_id]


@pytest.fixture
def harness(layout: Layout, disk: Disk) -> Iterator[Harness]:
    h = Harness(layout, disk)
    yield h
    h.engine.close()


def _op(body=lambda ctx: 0, **kwargs: object) -> Operation:
    return Operation("demo", body, **kwargs)


def test_ordre_fixe_des_evenements(harness: Harness) -> None:
    def body(ctx: OpContext) -> int:
        ctx.output("bonjour")
        return 0

    op = _op(body)
    result = harness.engine.submit(op).result(WAIT)
    assert result.code == 0 and result.projection == Projection({"demo": "f0"}, "f0")
    assert harness.kinds(op.op_id) == [
        "engine_state",
        "op_started",
        "terminal_output",
        "op_exit",
        "state_projected",
        "step_verdict",
        "step_explanation",
        "engine_state",
    ]
    states = [e.payload["state"] for e in harness.events if e.kind == Kind.ENGINE_STATE]
    assert states == ["idle", "command", "idle"]  # ouverture, opération, retour au repos
    seqs = [e.seq for e in harness.events]
    assert seqs == sorted(seqs) and len(set(seqs)) == len(seqs)
    assert all(e.epoch == 4 for e in harness.events)


def test_deux_intentions_simultanees_en_serie(harness: Harness) -> None:
    trace: list[str] = []
    first_in = threading.Event()
    release = threading.Event()

    def slow(ctx: OpContext) -> int:
        trace.append("début 1")
        first_in.set()
        assert release.wait(WAIT)
        trace.append("fin 1")
        return 0

    def quick(ctx: OpContext) -> int:
        trace.append("2")
        return 0

    first = harness.engine.submit(_op(slow))
    assert first_in.wait(WAIT)
    results = {}
    submitter = threading.Thread(
        target=lambda: results.setdefault("f", harness.engine.submit(_op(quick)))
    )
    submitter.start()
    submitter.join(WAIT)
    assert harness.engine.state == "command" and trace == ["début 1"]
    release.set()
    first.result(WAIT)
    results["f"].result(WAIT)
    assert trace == ["début 1", "fin 1", "2"]
    started = [e for e in harness.events if e.kind == Kind.OP_STARTED]
    exits = [e for e in harness.events if e.kind == Kind.OP_EXIT]
    assert started[0].seq < exits[0].seq < started[1].seq < exits[1].seq


def test_une_operation_ne_publie_pas_la_sequence(harness: Harness) -> None:
    refused: list[str] = []

    def body(ctx: OpContext) -> int:
        for kind in (Kind.STEP_EXPLANATION, Kind.STEP_VERDICT, Kind.STATE_PROJECTED, Kind.OP_EXIT):
            try:
                ctx.emit(kind, {})
            except ValueError:
                refused.append(kind.value)
        return 0

    op = _op(body)
    harness.engine.submit(op).result(WAIT)
    assert len(refused) == 4
    assert harness.kinds(op.op_id).count("step_explanation") == 1


def test_erreur_metier_devient_app_error(harness: Harness) -> None:
    def body(ctx: OpContext) -> int:
        ctx.output("avant")
        raise AppError("Le dépôt est verrouillé.", "Fermez l'autre programme.")

    op = _op(body)
    result = harness.engine.submit(op).result(WAIT)
    assert result.code is None
    assert harness.kinds(op.op_id) == [
        "engine_state",
        "op_started",
        "terminal_output",
        "app_error",
        "op_exit",
        "state_projected",
        "engine_state",
    ]
    error = next(e for e in harness.events if e.kind == Kind.APP_ERROR)
    assert error.payload == {
        "cause_text": "Le dépôt est verrouillé.",
        "action_text": "Fermez l'autre programme.",
    }
    assert harness.engine.state == "idle"


def test_exception_inattendue_sans_trace(harness: Harness) -> None:
    def body(ctx: OpContext) -> int:
        raise KeyError("secret interne")

    op = _op(body)
    assert harness.engine.submit(op).result(WAIT).code is None
    error = next(e for e in harness.events if e.kind == Kind.APP_ERROR)
    assert error.payload == {"cause_text": GENERIC_CAUSE, "action_text": GENERIC_ACTION}
    assert "Traceback" not in str(error.payload) and "secret" not in str(error.payload)
    # La file survit : l'opération suivante passe.
    assert harness.engine.submit(_op()).result(WAIT).code == 0


def test_setup_incremente_et_enregistre_l_epoch(harness: Harness, layout: Layout) -> None:
    op = _op(state="setup", validate=False)
    harness.engine.submit(op).result(WAIT)
    assert harness.engine.epoch == 5 and load_run(layout)["epoch"] == 5
    states = [
        e.payload["state"]
        for e in harness.events
        if e.op_id == op.op_id and e.kind == Kind.ENGINE_STATE
    ]
    assert states == ["setup", "idle"]
    assert "step_verdict" not in harness.kinds(op.op_id)
    assert all(e.epoch == 5 for e in harness.events if e.op_id == op.op_id)


def test_epoch_perime_refuse_a_l_entree(harness: Harness) -> None:
    with pytest.raises(StaleOperation) as refused:
        harness.engine.submit(_op(epoch=3, writes=False))
    assert "ignoré" in refused.value.reason_text


def test_epoch_perime_rejete_a_l_execution(harness: Harness) -> None:
    """Un résultat créé avant un Recommencer est rejeté, même s'il était déjà en file."""
    gate = threading.Event()
    ran: list[str] = []

    def wait(ctx: OpContext) -> int:
        assert gate.wait(WAIT)
        return 0

    harness.engine.submit(_op(wait))
    harness.engine.submit(_op(state="restoring", validate=False))
    late_op = _op(lambda ctx: ran.append("x") or 0, epoch=4, writes=False)
    late = harness.engine.submit(late_op)
    gate.set()
    with pytest.raises(StaleOperation):
        late.result(WAIT)
    assert ran == [] and harness.engine.epoch == 5
    assert harness.kinds(late_op.op_id) == []


def test_quiz_altered_refuse_les_ecritures(harness: Harness) -> None:
    harness.engine.submit(_op(lambda ctx: ctx.set_rest_state("quiz_altered") or 0)).result(WAIT)
    assert harness.engine.state == "quiz_altered"
    with pytest.raises(OperationRefused) as refused:
        harness.engine.submit(_op())
    assert "lecture" in refused.value.reason_text
    assert harness.engine.submit(_op(writes=False)).result(WAIT).code == 0


def test_file_pleine_refusee(layout: Layout, disk: Disk) -> None:
    h = Harness(layout, disk, max_pending_ops=1)
    gate = threading.Event()
    try:
        h.engine.submit(_op(lambda ctx: gate.wait(WAIT) and 0))
        # La première est peut-être déjà sortie de l'attente : on remplit jusqu'au refus.
        with pytest.raises(OperationRefused) as refused:
            for _ in range(3):
                h.engine.submit(_op())
        assert "attente" in refused.value.reason_text
    finally:
        gate.set()
        h.engine.close()


def test_veille_refuse_les_operations_en_attente(layout: Layout, disk: Disk) -> None:
    h = Harness(layout, disk)
    gate = threading.Event()
    entered = threading.Event()

    def hold(ctx: OpContext) -> int:
        entered.set()
        assert gate.wait(WAIT)
        return 0

    running = h.engine.submit(_op(hold))
    assert entered.wait(WAIT)  # en cours : la veille l'attend au lieu de la refuser
    pending = h.engine.submit(_op())
    closer = threading.Thread(target=h.engine.close)
    closer.start()
    with pytest.raises(OperationRefused):
        pending.result(WAIT)
    gate.set()
    closer.join(WAIT)
    assert running.result(WAIT).code == 0
    with pytest.raises(OperationRefused):
        h.engine.submit(_op())


def test_changement_externe_filtre_par_empreinte(harness: Harness, disk: Disk) -> None:
    same = external_change(harness.engine, disk.project)
    assert harness.engine.submit(same).result(WAIT).code is None
    assert harness.kinds(same.op_id) == []  # empreinte inchangée : aucune opération visible
    disk.fingerprint = "f1"
    changed = external_change(harness.engine, disk.project)
    assert harness.engine.submit(changed).result(WAIT).code == 0
    kinds = harness.kinds(changed.op_id)
    assert kinds.index("external_change") < kinds.index("op_exit") < kinds.index("state_projected")
    assert harness.engine.last_projection.fingerprint == "f1"


def test_etat_courant(harness: Harness) -> None:
    harness.engine.submit(_op()).result(WAIT)
    snap = harness.engine.snapshot()
    assert snap["boot_id"] == "boot" and snap["epoch"] == 4 and snap["state"] == "idle"
    assert snap["fingerprint"] == "f0" and snap["seq"] == harness.log.seq


def test_operation_dans_un_etat_de_repos_refusee() -> None:
    with pytest.raises(ValueError):
        Operation("x", lambda ctx: 0, state="idle")
