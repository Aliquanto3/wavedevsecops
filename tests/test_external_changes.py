"""Story 2.9 : le surveillant réel, la file et l'événement `external_change` (FR-3, AD-1).

Le surveillant tourne en interrogation (`force_polling`) pour être identique sur les trois
systèmes ; l'empreinte du projecteur de test est le contenu de `repo/a.txt`.
"""

from __future__ import annotations

import math
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
    """Reçoit les événements du journal et date les `external_change` avec leur empreinte."""

    def __init__(self) -> None:
        self.stamps: list[float] = []
        self.seen: list[tuple[float, str]] = []
        self._cond = threading.Condition()

    def __call__(self, event: object) -> None:
        if getattr(event, "kind", None) == Kind.EXTERNAL_CHANGE:
            now = time.monotonic()
            with self._cond:
                self.stamps.append(now)
                self.seen.append((now, event.payload["fingerprint"]))  # type: ignore[attr-defined]
                self._cond.notify_all()

    def wait_for(self, fingerprint: str, timeout: float) -> float | None:
        """Instant du premier `external_change` portant `fingerprint`, ou `None`."""
        deadline = time.monotonic() + timeout
        with self._cond:
            while True:
                for stamp, seen in self.seen:
                    if seen == fingerprint:
                        return stamp
                left = deadline - time.monotonic()
                if left <= 0:
                    return None
                self._cond.wait(left)

    def clear(self) -> None:
        with self._cond:
            self.stamps.clear()
            self.seen.clear()


def _new_second() -> None:
    """Attend la seconde suivante : le polling de `watchfiles` (crate `notify`) compare les
    dates de modification à la seconde près, une 2e écriture dans la même seconde lui échappe.
    """
    now = time.time()
    time.sleep(math.floor(now) + 1.02 - now)


PRIMED = "amorce"
"""Contenu écrit au démarrage pour s'assurer que l'état de référence du polling est pris."""


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
    # `ready` : premier tour de `watchfiles` ; l'état de référence du polling n'est sûr
    # qu'un instant après. Une écriture d'amorce, réessayée sans contrainte de délai,
    # garantit qu'il est pris : les mesures qui suivent sont alors strictes.
    for attempt in range(10):
        _new_second()
        (layout.repo / "a.txt").write_text(f"{PRIMED}{attempt}", encoding="utf-8")
        if spy.wait_for(f"{PRIMED}{attempt}", 2.0) is not None:
            break
    else:
        raise AssertionError("le surveillant n'a jamais vu l'écriture d'amorce")
    # Contenu fixe pour la suite, écrit une fois l'opération d'amorce finie (sinon sa
    # projection l'absorberait sans événement) ; puis l'espace revient au repos.
    _resumed(watcher)
    _new_second()
    (layout.repo / "a.txt").write_text(PRIMED, encoding="utf-8")
    assert spy.wait_for(PRIMED, WAIT) is not None
    _resumed(watcher)
    time.sleep(QUIET_MS / 1000 + 0.2)
    spy.clear()
    return layout, spy, watcher


def _resumed(watcher: TreeWatcher) -> None:
    """Attend la reprise du surveillant (le résultat précède l'état de repos)."""
    deadline = time.monotonic() + WAIT
    while watcher.suspended and time.monotonic() < deadline:
        time.sleep(0.01)
    assert not watcher.suspended


def _edit_and_measure(layout: Layout, spy: Spy, *, wait_second: bool = True) -> float:
    """Écrit `a.txt` une fois et rend le délai jusqu'à l'`external_change` de ce contenu.

    Mesure stricte : une seule écriture, l'événement attendu porte son empreinte (un
    événement tardif d'une écriture précédente ne peut pas la valider), et le délai est
    rendu même au-delà de `BUDGET_S` pour que l'échec dise de combien il est dépassé.
    """
    content = "écrit par l'éditeur"
    if wait_second:
        _new_second()
    started = time.monotonic()
    (layout.repo / "a.txt").write_text(content, encoding="utf-8")
    stamp = spy.wait_for(content, WAIT)
    assert stamp is not None, f"aucun changement externe vu en {WAIT} s"
    return stamp - started


@pytest.mark.slow
def test_modification_externe_suivie_en_moins_de_deux_secondes(
    manager: WorkspaceManager, settings: Settings
) -> None:
    layout, spy, _ = _start(manager, settings)
    assert _edit_and_measure(layout, spy) < BUDGET_S


@pytest.mark.slow
def test_changement_sous_git_seul_ou_meme_empreinte_sans_operation(
    manager: WorkspaceManager, settings: Settings
) -> None:
    layout, spy, _ = _start(manager, settings)
    (layout.repo / ".git" / "index").write_text("interne", encoding="utf-8")
    (layout.repo / "a.txt").write_text(PRIMED, encoding="utf-8")  # même contenu : même empreinte
    time.sleep(1.5)
    assert spy.stamps == []


@pytest.mark.slow
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


@pytest.mark.slow
def test_ecriture_externe_juste_apres_une_commande_n_est_pas_perdue(
    manager: WorkspaceManager, settings: Settings
) -> None:
    layout, spy, watcher = _start(manager, settings)
    _new_second()
    manager.get(ID).submit(Operation("command", lambda ctx: 0, state="command")).result(WAIT)
    _resumed(watcher)
    assert watcher.accepting() is False  # l'écriture qui suit tombe dans le silence
    assert _edit_and_measure(layout, spy, wait_second=False) < BUDGET_S


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


def test_ecriture_externe_pendant_la_suspension_proposee_a_la_reprise() -> None:
    calls: list[int] = []
    watcher = TreeWatcher(Path("."), lambda: calls.append(1), quiet_s=0.05)
    watcher.suspend()
    watcher.notify()  # écriture externe pendant la commande, après sa projection
    assert calls == []
    watcher.resume()
    deadline = time.monotonic() + WAIT
    while not calls and time.monotonic() < deadline:  # le minuteur réel la propose
        time.sleep(0.01)
    time.sleep(0.1)
    assert calls == [1]
    watcher.stop()


@pytest.mark.slow
def test_ecriture_externe_pendant_une_commande_vue_apres(
    manager: WorkspaceManager, settings: Settings
) -> None:
    layout, spy, _ = _start(manager, settings)
    engine = manager.get(ID)
    projected = threading.Event()
    gate = threading.Event()

    def project_then_wait(ctx: OpContext) -> Projection:
        projection = _project(ctx)
        if ctx.op.intent == "command":
            projected.set()
            assert gate.wait(WAIT)
        return projection

    engine._projector = project_then_wait  # noqa: SLF001
    running = engine.submit(Operation("command", lambda ctx: 0, state="command"))
    assert projected.wait(WAIT)
    _new_second()
    (layout.repo / "a.txt").write_text("pendant la validation", encoding="utf-8")
    time.sleep(0.5)  # le surveillant voit le lot pendant la suspension
    gate.set()
    assert running.result(WAIT).code == 0
    assert spy.wait_for("pendant la validation", WAIT) is not None
