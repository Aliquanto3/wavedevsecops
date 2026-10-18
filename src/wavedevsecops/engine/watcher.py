"""Surveillant de l'arbre de travail d'un espace (AD-1).

Il ne regarde que `repo/`, hors `.git/`. Il est suspendu pendant `command`, `setup` et
`restoring`, et reprend après `Settings.watch_quiet_ms` de silence. Il ne décide pas lui-même
d'un changement : il propose une opération « changement externe », que la file n'exécute que
si l'empreinte de l'arbre diffère de celle de la dernière projection.
"""

from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable
from pathlib import Path

import watchfiles

log = logging.getLogger("wavedevsecops")


class TreeWatcher:
    """Fil `watchfiles` sur `repo/` ; `on_change()` est appelé hors suspension."""

    def __init__(
        self,
        repo: Path,
        on_change: Callable[[], None],
        *,
        quiet_s: float,
        force_polling: bool | None = None,
        poll_delay_ms: int = 300,
        debounce_ms: int = 200,
    ) -> None:
        self.repo = repo
        self._on_change = on_change
        self._quiet_s = quiet_s
        self._force_polling = force_polling
        self._poll_delay_ms = poll_delay_ms
        self._debounce_ms = debounce_ms
        self._stop = threading.Event()
        self._lock = threading.Lock()
        self._suspended = False
        self._quiet_until = 0.0
        self._thread: threading.Thread | None = None
        self.ready = threading.Event()
        """Posé quand le fil surveille (le premier lot peut alors arriver)."""

    @property
    def running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def start(self) -> None:
        if self._thread is not None:
            return
        self._thread = threading.Thread(target=self._run, name="wds-watch", daemon=True)
        self._thread.start()

    def stop(self, timeout: float = 10.0) -> None:
        self._stop.set()
        if self._thread is not None and self._thread is not threading.current_thread():
            self._thread.join(timeout)

    def suspend(self) -> None:
        with self._lock:
            self._suspended = True

    def resume(self) -> None:
        with self._lock:
            self._suspended = False
            self._quiet_until = time.monotonic() + self._quiet_s

    def accepting(self) -> bool:
        """Vrai si un changement observé maintenant doit être proposé à la file."""
        with self._lock:
            return not self._suspended and time.monotonic() >= self._quiet_until

    def notify(self) -> None:
        """Traite un lot de changements (appelé par le fil, ou directement par un test)."""
        if self.accepting():
            self._on_change()

    def _run(self) -> None:
        watch_filter = watchfiles.DefaultFilter(ignore_dirs=(".git",), ignore_entity_patterns=())
        try:
            for _changes in watchfiles.watch(
                self.repo,
                watch_filter=watch_filter,
                debounce=self._debounce_ms,
                step=50,
                stop_event=self._stop,
                rust_timeout=500,
                yield_on_timeout=True,
                raise_interrupt=False,
                force_polling=self._force_polling,
                poll_delay_ms=self._poll_delay_ms,
            ):
                self.ready.set()
                if self._stop.is_set():
                    return
                if _changes:
                    try:
                        self.notify()
                    except Exception:  # noqa: BLE001 - le surveillant survit à un rappel en échec
                        log.exception("Surveillant de %s", self.repo)
        except Exception:  # noqa: BLE001 - un surveillant en panne ne fait pas tomber l'espace
            log.exception("Surveillant arrêté pour %s", self.repo)
        finally:
            self.ready.set()
