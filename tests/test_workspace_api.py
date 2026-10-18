"""Routes d'un espace sur le vrai serveur : état, intentions, flux SSE et reprise (AD-17)."""

from __future__ import annotations

import http.client
import json
import threading
from collections.abc import Iterator
from pathlib import Path

import pytest
from pydantic import BaseModel

from wavedevsecops import cli
from wavedevsecops.config import Settings
from wavedevsecops.engine import (
    Intent,
    OpContext,
    Operation,
    OperationRefused,
    prepare_workspace,
    register_intent,
    unregister_intent,
)
from wavedevsecops.scenarios import load_scenario

FREE = Path(__file__).resolve().parent.parent / "content" / "scenarios" / "bac-a-sable-libre.A.yaml"
WS = "llm.bac-a-sable-libre.A"
WAIT = 30.0


class Echo(BaseModel):
    text: str
    refuse: bool = False


GATE = threading.Event()


def _echo(engine: object, body: Echo) -> Operation:
    if body.refuse:
        raise OperationRefused("Action refusée pour le test.")

    def run(ctx: OpContext) -> int:
        assert GATE.wait(WAIT)
        ctx.output(body.text)
        return 0

    return Operation("echo_test", run)


@pytest.fixture(autouse=True)
def echo_intent() -> Iterator[None]:
    register_intent(Intent("echo_test", Echo, _echo))
    GATE.set()
    yield
    GATE.set()
    unregister_intent("echo_test")


@pytest.fixture
def instance(tmp_path: Path, git_path: Path) -> Iterator[cli.Instance]:
    settings = Settings(data_dir=tmp_path / "data", event_buffer=6)
    prepare_workspace(load_scenario(FREE, settings), "llm", settings=settings, git_path=git_path)
    inst = cli.start_instance(settings)
    try:
        yield inst
    finally:
        inst.stop()


def _conn(inst: cli.Instance) -> http.client.HTTPConnection:
    return http.client.HTTPConnection(cli.HOST, inst.port, timeout=WAIT)


@pytest.fixture
def cookie(instance: cli.Instance) -> dict[str, str]:
    conn = _conn(instance)
    conn.request("GET", f"/?t={instance.token}")
    resp = conn.getresponse()
    resp.read()
    conn.close()
    return {"Cookie": resp.getheader("Set-Cookie", "").split(";")[0]}


def _call(inst: cli.Instance, method: str, path: str, cookie: dict, body: object = None):
    headers = dict(cookie)
    data = None
    if method == "POST":
        headers["Origin"] = f"http://{cli.HOST}:{inst.port}"
        headers["Content-Type"] = "application/json"
        data = json.dumps(body).encode("utf-8") if body is not None else b""
    conn = _conn(inst)
    conn.request(method, path, body=data, headers=headers)
    resp = conn.getresponse()
    raw = resp.read()
    conn.close()
    return resp.status, (json.loads(raw) if raw else None)


class Stream:
    """Lecteur SSE minimal sur une connexion http.client."""

    def __init__(self, inst: cli.Instance, cookie: dict, last_event_id: str | None = None):
        headers = dict(cookie)
        if last_event_id is not None:
            headers["Last-Event-ID"] = last_event_id
        self.conn = _conn(inst)
        self.conn.request("GET", f"/api/ws/{WS}/events", headers=headers)
        self.resp = self.conn.getresponse()
        assert self.resp.status == 200
        assert self.resp.getheader("Content-Type", "").startswith("text/event-stream")

    def next(self) -> tuple[str, dict]:
        event_id, data = "", None
        while True:
            line = self.resp.readline().decode("utf-8")
            if not line:
                raise AssertionError("flux fermé")
            line = line.rstrip("\n")
            if line.startswith("id: "):
                event_id = line[4:]
            elif line.startswith("data: "):
                data = json.loads(line[6:])
            elif line == "" and data is not None:
                return event_id, data

    def until(self, kind: str, op_id: str | None = None) -> list[dict]:
        seen = []
        while True:
            _, data = self.next()
            seen.append(data)
            if data["kind"] == kind and (op_id is None or data["op_id"] == op_id):
                return seen

    def close(self) -> None:
        self.conn.close()


def test_etat_de_l_espace(instance: cli.Instance, cookie: dict) -> None:
    status, state = _call(instance, "GET", f"/api/ws/{WS}/state", cookie)
    assert status == 200
    assert state["workspace_id"] == WS and state["epoch"] == 0
    assert state["state"] in ("idle", "command") and state["boot_id"]
    status, missing = _call(instance, "GET", "/api/ws/llm.absent.A/state", cookie)
    assert status == 404 and "n'existe pas" in missing["reason_text"]
    status, _ = _call(instance, "GET", "/api/ws/..%2F..%2Fx/state", cookie)
    assert status == 404


def test_intention_executee_et_diffusee_dans_l_ordre(instance: cli.Instance, cookie: dict) -> None:
    _call(instance, "GET", f"/api/ws/{WS}/state", cookie)
    stream = Stream(instance, cookie)
    try:
        status, accepted = _call(
            instance, "POST", f"/api/ws/{WS}/echo_test", cookie, {"text": "ok"}
        )
        assert status == 202
        events = stream.until("engine_state", accepted["op_id"])  # entrée dans `command`
        events += stream.until("engine_state", accepted["op_id"])  # retour au repos
    finally:
        stream.close()
    mine = [e for e in events if e["op_id"] == accepted["op_id"]]
    assert [e["kind"] for e in mine] == [
        "engine_state",
        "op_started",
        "terminal_output",
        "op_exit",
        "state_projected",
        "engine_state",
    ]
    assert mine[0]["payload"]["state"] == "command" and mine[-1]["payload"]["state"] == "idle"
    assert mine[2]["payload"]["text"] == "ok"
    assert len(mine[4]["payload"]["fingerprint"]) == 64  # vraie empreinte, relue après l'opération
    assert all(e["workspace_id"] == WS and e["epoch"] == 0 for e in mine)


def test_refus_et_erreurs_d_intention(instance: cli.Instance, cookie: dict) -> None:
    status, body = _call(
        instance, "POST", f"/api/ws/{WS}/echo_test", cookie, {"text": "x", "refuse": True}
    )
    assert status == 409 and body == {"reason_text": "Action refusée pour le test."}
    status, body = _call(instance, "POST", f"/api/ws/{WS}/inconnue", cookie, {})
    assert status == 404 and "n'existe pas" in body["reason_text"]
    status, body = _call(instance, "POST", f"/api/ws/{WS}/echo_test", cookie, {"autre": 1})
    assert status == 422 and body["reason_text"]
    status, body = _call(instance, "POST", "/api/ws/llm.absent.A/echo_test", cookie, {"text": "x"})
    assert status == 404


def test_intention_sans_origine_refusee(instance: cli.Instance, cookie: dict) -> None:
    conn = _conn(instance)
    conn.request("POST", f"/api/ws/{WS}/echo_test", body=b'{"text": "x"}', headers=cookie)
    assert conn.getresponse().status == 403
    conn.close()


def test_reprise_par_last_event_id(instance: cli.Instance, cookie: dict) -> None:
    _, state = _call(instance, "GET", f"/api/ws/{WS}/state", cookie)
    boot = state["boot_id"]
    stream = Stream(instance, cookie)
    try:
        _, first = _call(instance, "POST", f"/api/ws/{WS}/echo_test", cookie, {"text": "1"})
        events = stream.until("op_exit", first["op_id"])
    finally:
        stream.close()
    # Déconnecté après `op_exit` : la suite de l'opération est rattrapée depuis le tampon.
    last_id = f"{boot}:{events[-1]['seq']}"
    resumed = Stream(instance, cookie, last_event_id=last_id)
    try:
        replay = resumed.until("engine_state", first["op_id"])
    finally:
        resumed.close()
    assert [e["kind"] for e in replay] == ["state_projected", "engine_state"]
    assert replay[0]["seq"] == events[-1]["seq"] + 1


def test_resync_si_boot_different_ou_sorti_du_tampon(instance: cli.Instance, cookie: dict) -> None:
    _, state = _call(instance, "GET", f"/api/ws/{WS}/state", cookie)
    stream = Stream(instance, cookie, last_event_id="ancien-lancement:3")
    try:
        _, data = stream.next()
    finally:
        stream.close()
    assert data["kind"] == "resync_required" and "redémarré" in data["payload"]["reason_text"]
    # Deux opérations (six événements chacune) débordent le tampon de six événements.
    live = Stream(instance, cookie)
    try:
        for text in ("a", "b"):
            _, accepted = _call(instance, "POST", f"/api/ws/{WS}/echo_test", cookie, {"text": text})
        live.until("state_projected", accepted["op_id"])
        live.until("engine_state", accepted["op_id"])
    finally:
        live.close()
    late = Stream(instance, cookie, last_event_id=f"{state['boot_id']}:{state['seq']}")
    try:
        first_id, first = late.next()
    finally:
        late.close()
    assert first["kind"] == "resync_required" and "manqués" in first["payload"]["reason_text"]
    assert first_id.startswith(state["boot_id"] + ":")
