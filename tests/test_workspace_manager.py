"""Espaces actifs, veille et réveil, surveillant de l'arbre (AD-1)."""

from __future__ import annotations

import threading
from collections.abc import Callable, Iterator
from pathlib import Path

import pytest

from wavedevsecops.config import Settings
from wavedevsecops.engine import (
    OpContext,
    Operation,
    OperationRefused,
    Projection,
    RunFileError,
    WorkspaceManager,
    WorkspaceNotFound,
    parse_workspace_id,
    save_run,
    workspace_id_for,
)
from wavedevsecops.engine.watcher import TreeWatcher
from wavedevsecops.events import Kind
from wavedevsecops.wsfs import Layout

WAIT = 20.0
IDS = ["llm.s1.A", "llm.s2.A", "no_ai.s1.A", "llm.s3.B"]


class FakeWatcher:
    def __init__(self, repo: Path, on_change: Callable[[], None]) -> None:
        self.repo = repo
        self.on_change = on_change
        self.calls: list[str] = []

    def start(self) -> None:
        self.calls.append("start")

    def stop(self) -> None:
        self.calls.append("stop")

    def suspend(self) -> None:
        self.calls.append("suspend")

    def resume(self) -> None:
        self.calls.append("resume")


DISK = {"fingerprint": "f"}


def _project(ctx: OpContext) -> Projection:
    return Projection({}, DISK["fingerprint"])


def _make(settings: Settings, workspace_id: str, epoch: int = 0) -> Layout:
    track, scenario_id, mode = parse_workspace_id(workspace_id)
    layout = Layout.for_scenario(settings.workspaces_path(), track, scenario_id, mode)
    (layout.repo / ".git").mkdir(parents=True)
    save_run(layout, {"epoch": epoch})
    return layout


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(data_dir=tmp_path / "data")


@pytest.fixture
def watchers() -> list[FakeWatcher]:
    return []


@pytest.fixture
def manager(settings: Settings, watchers: list[FakeWatcher]) -> Iterator[WorkspaceManager]:
    def factory(repo: Path, on_change: Callable[[], None]) -> FakeWatcher:
        watchers.append(FakeWatcher(repo, on_change))
        return watchers[-1]

    m = WorkspaceManager(settings, projector=_project, watcher_factory=factory)
    yield m
    m.close()


def test_identifiants_d_espace() -> None:
    assert workspace_id_for("llm", "bac-a-sable-libre.A") == "llm.bac-a-sable-libre.A"
    assert parse_workspace_id("no_ai.bac-a-sable-libre.B") == ("no_ai", "bac-a-sable-libre", "B")
    for bad in ("llm/x.A", "llm.x.C", "autre.x.A", "llm..A", "llm.x.A/../..", "llm.X.A"):
        with pytest.raises(WorkspaceNotFound):
            parse_workspace_id(bad)


def test_espace_absent(manager: WorkspaceManager) -> None:
    with pytest.raises(WorkspaceNotFound):
        manager.get("llm.absent.A")


def test_run_json_d_une_version_future(manager: WorkspaceManager, settings: Settings) -> None:
    layout = _make(settings, "llm.s1.A")
    save_run(layout, {})
    layout.run_json.write_text('{"schema_version": 99}', encoding="utf-8")
    with pytest.raises(RunFileError) as error:
        manager.get("llm.s1.A")
    assert "plus récente" in error.value.cause_text


def test_le_moins_recent_s_endort_puis_se_reveille(
    manager: WorkspaceManager, settings: Settings
) -> None:
    for index, workspace_id in enumerate(IDS):
        _make(settings, workspace_id, epoch=index)
    engines = {}
    for workspace_id in IDS[:3]:
        engines[workspace_id] = manager.get(workspace_id)
    manager.get(IDS[0])  # le premier redevient récent : c'est le deuxième qui s'endormira
    journal = manager.events(IDS[1])
    seq_before = journal.seq
    manager.get(IDS[3])
    assert manager.active_ids() == [IDS[2], IDS[0], IDS[3]]
    asleep = engines[IDS[1]]
    asleep.join(WAIT)
    assert asleep.closed
    with pytest.raises(Exception):  # noqa: B017 - OperationRefused : la file dort
        asleep.submit(Operation("x", lambda ctx: 0))
    awake = manager.get(IDS[1])
    assert awake is not asleep and awake.epoch == 1  # relu dans run.json
    assert manager.active_ids()[-1] == IDS[1] and len(manager.active_ids()) == 3
    assert awake.submit(Operation("x", lambda ctx: 0)).result(WAIT).code == 0
    # Le journal survit à la veille : `seq` continue de croître dans le même lancement.
    assert manager.events(IDS[1]) is journal and journal.seq > seq_before


def test_surveillant_suspendu_pendant_les_commandes(
    manager: WorkspaceManager, settings: Settings, watchers: list[FakeWatcher]
) -> None:
    _make(settings, "llm.s1.A")
    engine = manager.get("llm.s1.A")
    engine.submit(Operation("x", lambda ctx: 0)).result(WAIT)
    assert len(watchers) == 1
    assert watchers[0].calls == ["start", "suspend", "resume"]
    manager.sleep("llm.s1.A")
    assert watchers[0].calls[-1] == "stop"


def test_changement_externe_propose_avec_l_epoch_courant(
    manager: WorkspaceManager, settings: Settings, watchers: list[FakeWatcher]
) -> None:
    _make(settings, "llm.s1.A", epoch=7)
    engine = manager.get("llm.s1.A")
    engine.submit(Operation("x", lambda ctx: 0)).result(WAIT)
    events = []
    manager.events("llm.s1.A").attach(None, events.append)
    watchers[0].on_change()  # empreinte inchangée : rien de visible
    engine.submit(Operation("y", lambda ctx: 0, writes=False)).result(WAIT)
    assert not any(e.kind == Kind.EXTERNAL_CHANGE for e in events)
    DISK["fingerprint"] = "g"
    try:
        watchers[0].on_change()
        engine.submit(Operation("z", lambda ctx: 0, writes=False)).result(WAIT)  # file en série
    finally:
        DISK["fingerprint"] = "f"
    change = [e for e in events if e.kind == Kind.EXTERNAL_CHANGE]
    assert len(change) == 1 and change[0].epoch == 7 and change[0].payload == {"fingerprint": "g"}


def _hold(entered: threading.Event, gate: threading.Event) -> Operation:
    def body(ctx: OpContext) -> int:
        entered.set()
        assert gate.wait(WAIT)
        return 0

    return Operation("long", body)


def test_pas_de_reouverture_tant_que_l_ancienne_file_ecrit(tmp_path: Path) -> None:
    """Un seul écrivain : un espace endormi pendant une opération ne se rouvre qu'après elle."""
    settings = Settings(data_dir=tmp_path / "data", engine_stop_timeout_s=0.01)
    _make(settings, "llm.s1.A")
    manager = WorkspaceManager(settings, projector=_project, watch=False)
    gate, entered = threading.Event(), threading.Event()
    try:
        old = manager.get("llm.s1.A")
        running = old.submit(_hold(entered, gate))
        assert entered.wait(WAIT)
        manager.sleep("llm.s1.A")  # délai dépassé : la file tourne encore
        assert old.alive
        with pytest.raises(OperationRefused) as refused:
            manager.get("llm.s1.A")
        assert "veille" in refused.value.reason_text
        gate.set()
        assert running.result(WAIT).code == 0
        old.join(WAIT)
        assert manager.get("llm.s1.A") is not old
    finally:
        gate.set()
        manager.close()


def test_la_veille_prefere_un_espace_au_repos(tmp_path: Path) -> None:
    settings = Settings(data_dir=tmp_path / "data", max_active_workspaces=2)
    for workspace_id in IDS[:3]:
        _make(settings, workspace_id)
    manager = WorkspaceManager(settings, projector=_project, watch=False)
    gate, entered = threading.Event(), threading.Event()
    try:
        busy = manager.get(IDS[0])
        running = busy.submit(_hold(entered, gate))
        assert entered.wait(WAIT)
        manager.get(IDS[1])
        manager.get(IDS[2])  # le plus ancien travaille : c'est le deuxième qui s'endort
        assert manager.active_ids() == [IDS[0], IDS[2]]
        gate.set()
        assert running.result(WAIT).code == 0
    finally:
        gate.set()
        manager.close()


def test_watcher_reel_detecte_une_modification(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    (repo / ".git").mkdir(parents=True)
    seen = threading.Event()
    watcher = TreeWatcher(repo, seen.set, quiet_s=0, force_polling=True, poll_delay_ms=50)
    watcher.start()
    try:
        assert watcher.ready.wait(WAIT)
        (repo / ".git" / "index").write_text("interne", encoding="utf-8")
        (repo / "a.txt").write_text("x", encoding="utf-8")
        assert seen.wait(WAIT)
    finally:
        watcher.stop()
    assert not watcher.running


def test_watcher_suspendu_puis_silence() -> None:
    calls: list[int] = []
    watcher = TreeWatcher(Path("."), lambda: calls.append(1), quiet_s=3600)
    watcher.notify()
    assert calls == [1]
    watcher.suspend()
    watcher.notify()
    watcher.resume()  # délai de silence d'une heure : toujours ignoré
    watcher.notify()
    assert calls == [1]
