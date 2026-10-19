"""Intention `run_exercise_code` (Story 6.6) sur le vrai serveur, sans modèle ni réseau.

Le lancement est remplacé (`llmrun.start_exercise` rend un faux `Handle`) : on vérifie la
confirmation, les refus, l'instantané `exercise` pris avant, l'état `command`, la sortie dans
le terminal et l'arrêt par `interrupt`.
"""

from __future__ import annotations

import http.client
import json
import threading
from collections.abc import Iterator
from pathlib import Path

import pytest
from test_workspace_api import WS, Stream, _call, _conn, cookie, instance  # noqa: F401

from wavedevsecops import cli, llmrun
from wavedevsecops.engine import INTENTS, OperationRefused, list_snapshots
from wavedevsecops.procs import Chunk
from wavedevsecops.web import exercise
from wavedevsecops.wsfs import Layout

PATH = f"/api/ws/{WS}/run_exercise_code"


class FakeHandle:
    """Doublure de `procs.Handle` : morceaux donnés, puis code ; `block` attend `terminate`."""

    def __init__(
        self,
        chunks: list[tuple[str, str]] = (),
        *,
        code: int | None = 0,
        timed_out: bool = False,
        block: bool = False,
    ) -> None:
        self._chunks = list(chunks)
        self._code = code
        self.timed_out = timed_out
        self.interrupted = False
        self.tree_stopped = True
        self._stop = threading.Event()
        self._block = block

    @property
    def returncode(self) -> int | None:
        return None if self.interrupted else self._code

    def terminate(self) -> None:
        self.interrupted = True
        self._stop.set()

    def chunks(self, tick: float = 0.2) -> Iterator[Chunk | None]:
        for stream, text in self._chunks:
            yield Chunk(stream, text)
        while self._block and not self._stop.wait(tick):
            yield None


def _layout(instance: cli.Instance) -> Layout:  # noqa: F811
    return Layout.for_scenario(instance.data_dir / "workspaces", "llm", "bac-a-sable-libre", "A")


@pytest.fixture
def fake_run(monkeypatch: pytest.MonkeyPatch, instance: cli.Instance) -> list[dict]:  # noqa: F811
    """Remplace le lancement ; note les instantanés présents au moment de l'appel."""
    calls: list[dict] = []

    def fake(lay, settings=None, **kwargs):
        calls.append({"snapshots": list_snapshots(lay), "layout": lay})
        return FakeHandle([("stdout", "Deux articles sont sous le seuil.\n")])

    monkeypatch.setattr(llmrun, "start_exercise", fake)
    return calls


def test_intention_enregistree_et_catalogue() -> None:
    from wavedevsecops.engine.intents import CATALOGUE

    exercise.register_exercise_intent()
    exercise.register_exercise_intent()  # idempotent
    assert llmrun.INTENT in CATALOGUE and llmrun.INTENT in INTENTS


def test_lancement_confirme_snapshot_etat_command_et_sortie(
    instance: cli.Instance,  # noqa: F811
    cookie: dict,  # noqa: F811
    fake_run: list[dict],
) -> None:
    _call(instance, "GET", f"/api/ws/{WS}/state", cookie)
    stream = Stream(instance, cookie)
    try:
        status, accepted = _call(instance, "POST", PATH, cookie, {"confirmed": True})
        assert status == 202
        events = stream.until("engine_state", accepted["op_id"])
        events += stream.until("engine_state", accepted["op_id"])
    finally:
        stream.close()
    mine = [e for e in events if e["op_id"] == accepted["op_id"]]
    assert [e["kind"] for e in mine] == [
        "engine_state",
        "op_started",
        "terminal_output",
        "terminal_output",
        "op_exit",
        "state_projected",
        "engine_state",
    ]
    assert mine[0]["payload"]["state"] == "command"
    assert mine[1]["payload"]["intent"] == "run_exercise_code"
    assert mine[2]["payload"]["text"] == f"$ {llmrun.COMMAND}"
    assert mine[3]["payload"] == {
        "stream": "stdout",
        "text": "Deux articles sont sous le seuil.\n",
        "lang": "",
        "spans": [],
        "tool": "",
        "explain_ref": "",
    }
    assert mine[4]["payload"]["code"] == 0
    # Un instantané `exercise` existait déjà au lancement, après celui du setup (le 0).
    assert len(fake_run) == 1
    snapshots = fake_run[0]["snapshots"]
    assert snapshots[0].snapshot_id == 0 and snapshots[0].reason == "setup"
    assert snapshots[-1].reason == "exercise" and snapshots[-1].snapshot_id > 0
    # Son empreinte (calculée sur la copie) est celle de l'espace au moment du lancement.
    assert snapshots[-1].fingerprint == snapshots[0].fingerprint


def test_refus_sans_confirmation(instance: cli.Instance, cookie: dict, fake_run: list) -> None:  # noqa: F811
    for body in ({}, {"confirmed": False}, None):
        status, refused = _call(instance, "POST", PATH, cookie, body)
        assert status == 409
        assert refused["reason_text"] == exercise.NOT_CONFIRMED_TEXT
    status, _ = _call(instance, "POST", PATH, cookie, {"confirmed": "oui"})
    assert status == 422
    status, _ = _call(instance, "POST", PATH, cookie, {"confirmed": True, "autre": 1})
    assert status == 422
    assert fake_run == []  # rien n'a été lancé ni sauvegardé
    assert all(s.reason != "exercise" for s in list_snapshots(_layout(instance)))


def test_refus_sans_cookie_ou_sans_origine(instance: cli.Instance, fake_run: list) -> None:  # noqa: F811
    body = json.dumps({"confirmed": True}).encode("utf-8")
    origin = f"http://{cli.HOST}:{instance.port}"
    for headers, expected in (
        ({"Origin": origin, "Content-Type": "application/json"}, 401),  # sans cookie
        ({"Origin": origin, "Cookie": "wds_session=faux"}, 401),  # mauvais cookie
        ({"Origin": "http://evil.example", "Cookie": "wds_session=faux"}, 403),
    ):
        conn: http.client.HTTPConnection = _conn(instance)
        conn.request("POST", PATH, body=body, headers=headers)
        assert conn.getresponse().status == expected
        conn.close()
    assert fake_run == []


def test_parcours_sans_ia_refuse() -> None:
    class Engine:
        workspace_id = "no_ai.bac-a-sable-libre.A"

    with pytest.raises(OperationRefused) as refused:
        INTENTS[llmrun.INTENT].build(Engine(), exercise.RunExerciseCode(confirmed=True))
    assert refused.value.reason_text == exercise.WRONG_TRACK_TEXT


def test_echec_de_lancement_et_delai(
    instance: cli.Instance,  # noqa: F811
    cookie: dict,  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def unavailable() -> FakeHandle:
        raise llmrun.ExerciseUnavailable("l'environnement d'exercice est absent")

    results = iter(
        [
            unavailable,
            lambda: FakeHandle([("stdout", "début\n")], code=None, timed_out=True),
            lambda: FakeHandle([("stderr", "Traceback\n")], code=1),
        ]
    )
    monkeypatch.setattr(llmrun, "start_exercise", lambda *a, **k: next(results)())
    _call(instance, "GET", f"/api/ws/{WS}/state", cookie)
    stream = Stream(instance, cookie)
    seen: list[dict] = []
    try:
        for _ in range(3):
            _, accepted = _call(instance, "POST", PATH, cookie, {"confirmed": True})
            seen += stream.until("engine_state", accepted["op_id"])
            seen += stream.until("engine_state", accepted["op_id"])
    finally:
        stream.close()
    errors = [e for e in seen if e["kind"] == "app_error"]
    assert (
        len(errors) == 1
        and "environnement d'exercice est absent" in errors[0]["payload"]["cause_text"]
    )
    texts = [e["payload"]["text"] for e in seen if e["kind"] == "terminal_output"]
    assert exercise.TIMEOUT_TEXT in texts and "Traceback\n" in texts
    exits = [e["payload"]["code"] for e in seen if e["kind"] == "op_exit"]
    assert exits == [None, exercise.EXIT_TIMEOUT, 1]


def test_interruption_arrete_le_code(
    instance: cli.Instance,  # noqa: F811
    cookie: dict,  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    handles: list[FakeHandle] = []

    def start(*args, **kwargs) -> FakeHandle:
        handles.append(FakeHandle([("stdout", "réflexion…\n")], block=True))
        return handles[-1]

    monkeypatch.setattr(llmrun, "start_exercise", start)
    _call(instance, "GET", f"/api/ws/{WS}/state", cookie)
    stream = Stream(instance, cookie)
    try:
        _, accepted = _call(instance, "POST", PATH, cookie, {"confirmed": True})
        events = stream.until("terminal_output", accepted["op_id"])
        events += stream.until("terminal_output", accepted["op_id"])
        status, body = _call(instance, "POST", f"/api/ws/{WS}/interrupt", cookie, {})
        assert status == 202 and body["interrupted"] is True
        events += stream.until("engine_state", accepted["op_id"])
    finally:
        stream.close()
    assert handles and handles[0].interrupted
    texts = [e["payload"]["text"] for e in events if e["kind"] == "terminal_output"]
    assert exercise.INTERRUPTED_TEXT in texts
    exits = [e["payload"]["code"] for e in events if e["kind"] == "op_exit"]
    assert exits == [exercise.EXIT_INTERRUPTED]


def test_instantane_en_echec_n_execute_rien(
    instance: cli.Instance,  # noqa: F811
    cookie: dict,  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def broken(*args, **kwargs):
        raise OSError("disque plein")

    ran: list[bool] = []
    monkeypatch.setattr(exercise, "take_snapshot", broken)
    monkeypatch.setattr(llmrun, "start_exercise", lambda *a, **k: ran.append(True))
    _call(instance, "GET", f"/api/ws/{WS}/state", cookie)
    stream = Stream(instance, cookie)
    try:
        _, accepted = _call(instance, "POST", PATH, cookie, {"confirmed": True})
        events = stream.until("engine_state", accepted["op_id"])
        events += stream.until("engine_state", accepted["op_id"])
    finally:
        stream.close()
    errors = [e for e in events if e["kind"] == "app_error"]
    assert errors and "sauvegardé" in errors[0]["payload"]["cause_text"]
    assert ran == []


def test_sources_sans_chemin_pour_lancer_hors_llmrun() -> None:
    """Aucune étape de scénario ne déclare l'intention : voir aussi `test_scenarios.py`."""
    root = Path(__file__).resolve().parent.parent / "content" / "scenarios"
    assert all(llmrun.INTENT not in p.read_text("utf-8") for p in root.glob("*.yaml"))
