"""Story 2.9 : le surveillant réel, la file et l'événement `external_change` (FR-3, AD-1).

Le surveillant tourne en interrogation (`force_polling`) pour être identique sur les trois
systèmes ; l'empreinte du projecteur de test est le contenu de `repo/a.txt`.
"""

from __future__ import annotations

import threading
import time
from collections.abc import Callable, Iterator
from pathlib import Path

import pytest

from wavedevsecops.config import Settings
from wavedevsecops.engine.manager import WorkspaceManager
from wavedevsecops.engine.operations import OpContext, Operation, Projection
from wavedevsecops.engine.watcher import TreeWatcher
from wavedevsecops.events import Kind
from wavedevsecops.wsfs import Layout

WAIT = 20.0
ID = "llm.s1.A"
QUIET_MS = 300
BUDGET_S = 2.0  # exigence : vues à jour en 2 s au plus après l'enregistrement


def _project(ctx: OpContext) -> Projection:
    target = ctx.layout.repo / "a.txt"
    content = target.read_text(encoding="utf-8") if target.exists() else ""
    return Projection({"repo": {"a": content}}, content)


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(data_dir=tmp_path / "data", watch_quiet_ms=QUIET_MS)


@pytest.fixture
def manager(settings: Settings) -> Iterator[WorkspaceManager]:
    def factory(repo: Path, on_change: Callable[[], None]) -> TreeWatcher:
        return TreeWatcher(
            repo,
            on_change,
            quiet_s=settings.watch_quiet_ms / 1000,
            force_polling=True,
            poll_delay_ms=50,
        )

    m = WorkspaceManager(settings, projector=_project, watcher_factory=factory)
    yield m
    m.close()


class Spy:
    """Reçoit les événements du journal et date les `external_change`."""

    def __init__(self) -> None:
        self.stamps: list[float] = []
        self.arrived = threading.Event()

    def __call__(self, event: object) -> None:
        if getattr(event, "kind", None) == Kind.EXTERNAL_CHANGE:
            self.stamps.append(time.monotonic())
            self.arrived.set()


def _start(manager: WorkspaceManager, settings: Settings) -> tuple[Layout, Spy, TreeWatcher]:
    layout = Layout.for_scenario(settings.workspaces_path(), "llm", "s1", "A")
    (layout.repo / ".git").mkdir(parents=True)
    (layout.repo / "a.txt").write_text("v0", encoding="utf-8")
    from wavedevsecops.engine.runfile import save_run

    save_run(layout, {"epoch": 0})
    engine = manager.get(ID)
    engine.submit(Operation("x", lambda ctx: 0)).result(
        WAIT
    )  # première projection, surveillant lancé
    spy = Spy()
    manager.events(ID).attach(None, spy)
    watcher = manager._active[ID].watcher  # noqa: SLF001
    assert watcher.ready.wait(WAIT)
    _resumed(watcher)
    # `ready` : premier tour de `watchfiles` ; l'état de référence du polling
    # n'est sûr qu'un instant après.
    time.sleep(0.4)
    return layout, spy, watcher


def _resumed(watcher: TreeWatcher) -> None:
    """Attend la reprise du surveillant (le résultat précède l'état de repos)."""
    deadline = time.monotonic() + WAIT
    while watcher.suspended and time.monotonic() < deadline:
        time.sleep(0.01)
    assert not watcher.suspended


def _edit_until_seen(layout: Layout, spy: Spy, attempts: int = 4) -> float:
    """Écrit `a.txt` (contenus distincts) jusqu'à voir `external_change` ; rend le délai constaté.

    Un seul essai doit tenir en `BUDGET_S`. Plusieurs essais absorbent la course de l'état de
    référence du polling (premier tour de `watchfiles`) et les machines de CI chargées, sans
    cacher une panne : si aucun essai n'aboutit, le test échoue.
    """
    for attempt in range(attempts):
        spy.arrived.clear()
        started = time.monotonic()
        (layout.repo / "a.txt").write_text(f"version {attempt} de l'éditeur", encoding="utf-8")
        if spy.arrived.wait(BUDGET_S):
            return spy.stamps[-1] - started
    raise AssertionError(f"aucun changement externe vu en {attempts} essais de {BUDGET_S} s")


def test_modification_externe_suivie_en_moins_de_deux_secondes(
    manager: WorkspaceManager, settings: Settings
) -> None:
    layout, spy, _ = _start(manager, settings)
    assert _edit_until_seen(layout, spy) < BUDGET_S


def test_changement_sous_git_seul_ou_meme_empreinte_sans_operation(
    manager: WorkspaceManager, settings: Settings
) -> None:
    layout, spy, _ = _start(manager, settings)
    (layout.repo / ".git" / "index").write_text("interne", encoding="utf-8")
    (layout.repo / "a.txt").write_text("v0", encoding="utf-8")  # même contenu : même empreinte
    time.sleep(1.5)
    assert spy.stamps == []


def test_aucune_operation_pendant_une_commande_ni_apres(
    manager: WorkspaceManager, settings: Settings
) -> None:
    layout, spy, watcher = _start(manager, settings)
    engine = manager.get(ID)
    noticed = threading.Event()
    gate = threading.Event()

    def command(ctx: OpContext) -> int:
        (ctx.layout.repo / "a.txt").write_text("fait par la commande", encoding="utf-8")
        noticed.set()
        assert gate.wait(WAIT)
        return 0

    running = engine.submit(Operation("command", command, state="command"))
    assert noticed.wait(WAIT)
    time.sleep(0.5)  # le surveillant a vu le lot, suspendu
    gate.set()
    assert running.result(WAIT).code == 0
    time.sleep(1.5)  # délai de silence écoulé, rien n'est venu
    assert spy.stamps == []
    assert watcher.running


def test_ecriture_externe_juste_apres_une_commande_n_est_pas_perdue(
    manager: WorkspaceManager, settings: Settings
) -> None:
    layout, spy, watcher = _start(manager, settings)
    manager.get(ID).submit(Operation("command", lambda ctx: 0, state="command")).result(WAIT)
    _resumed(watcher)
    assert _edit_until_seen(layout, spy) < BUDGET_S  # le premier essai tombe dans le silence


def test_lot_retenu_pendant_le_silence_puis_propose_une_fois() -> None:
    calls: list[int] = []
    watcher = TreeWatcher(Path("."), lambda: calls.append(1), quiet_s=0.2)
    watcher.resume()
    watcher.notify()
    watcher.flush_pending()
    assert calls == []
    time.sleep(0.3)
    watcher.flush_pending()
    watcher.flush_pending()
    assert calls == [1]


def test_lot_retenu_oublie_si_une_commande_reprend() -> None:
    calls: list[int] = []
    watcher = TreeWatcher(Path("."), lambda: calls.append(1), quiet_s=0.05)
    watcher.resume()
    watcher.notify()
    watcher.suspend()
    watcher.resume()
    time.sleep(0.1)
    watcher.flush_pending()
    assert calls == []
