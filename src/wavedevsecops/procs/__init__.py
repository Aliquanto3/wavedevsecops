"""Création de sous-processus, délais et arrêt d'arbre (AD-12).

Seul `procs` crée des sous-processus ; seuls `gitio` et `toolrun` l'appellent (AD-1).

Story 1.4 : lanceur bloquant `run` (sondes courtes) et `terminate_tree`. Story 2.4 : lanceur
non bloquant `spawn -> Handle` (sortie au fil de l'eau, délai, arrêt d'arbre) et Job Object de
Windows : l'arrêt atteint aussi un descendant dont le parent est déjà sorti.
"""

from __future__ import annotations

import codecs
import ctypes
import os
import queue
import signal
import subprocess
import sys
import threading
import time
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

IS_WINDOWS = sys.platform == "win32"
KILL_GRACE_S = 2.0
"""Attente bornée des tubes après l'arrêt d'arbre, en secondes."""


@dataclass(frozen=True)
class ProcResult:
    """Résultat d'un lancement : jamais d'exception pour un échec ordinaire."""

    returncode: int | None
    stdout: str = ""
    stderr: str = ""
    timed_out: bool = False
    error: str | None = None
    """Raison si le processus n'a pas pu être lancé (fichier absent, droits…)."""

    @property
    def ok(self) -> bool:
        return self.returncode == 0 and not self.timed_out and self.error is None


def _kernel() -> Any:
    """kernel32 avec les signatures des appels du Job Object (Windows seulement)."""
    from ctypes import wintypes

    kernel = ctypes.WinDLL("kernel32", use_last_error=True)  # type: ignore[attr-defined]
    kernel.CreateJobObjectW.restype = wintypes.HANDLE
    kernel.CreateJobObjectW.argtypes = [wintypes.LPVOID, wintypes.LPCWSTR]
    kernel.OpenProcess.restype = wintypes.HANDLE
    kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel.SetInformationJobObject.argtypes = [
        wintypes.HANDLE,
        ctypes.c_int,
        wintypes.LPVOID,
        wintypes.DWORD,
    ]
    kernel.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
    kernel.TerminateJobObject.argtypes = [wintypes.HANDLE, wintypes.UINT]
    kernel.QueryInformationJobObject.argtypes = [
        wintypes.HANDLE,
        ctypes.c_int,
        wintypes.LPVOID,
        wintypes.DWORD,
        wintypes.LPVOID,
    ]
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    return kernel


def _make_job(pid: int) -> int | None:
    """Job Object (Windows) qui contient le processus et tue tout l'arbre à sa fermeture.

    Rend `None` hors Windows ou si le processus n'a pas pu y être rangé (repli : taskkill).
    """
    if not IS_WINDOWS:
        return None
    from ctypes import wintypes

    class Basic(ctypes.Structure):
        _fields_ = [
            ("PerProcessUserTimeLimit", ctypes.c_int64),
            ("PerJobUserTimeLimit", ctypes.c_int64),
            ("LimitFlags", wintypes.DWORD),
            ("MinimumWorkingSetSize", ctypes.c_size_t),
            ("MaximumWorkingSetSize", ctypes.c_size_t),
            ("ActiveProcessLimit", wintypes.DWORD),
            ("Affinity", ctypes.c_size_t),
            ("PriorityClass", wintypes.DWORD),
            ("SchedulingClass", wintypes.DWORD),
        ]

    class Counters(ctypes.Structure):
        _fields_ = [(name, ctypes.c_uint64) for name in ("r", "w", "o", "rb", "wb", "ob")]

    class Extended(ctypes.Structure):
        _fields_ = [
            ("Basic", Basic),
            ("Io", Counters),
            ("ProcessMemoryLimit", ctypes.c_size_t),
            ("JobMemoryLimit", ctypes.c_size_t),
            ("PeakProcessMemoryUsed", ctypes.c_size_t),
            ("PeakJobMemoryUsed", ctypes.c_size_t),
        ]

    try:
        kernel = _kernel()
        job = kernel.CreateJobObjectW(None, None)
        if not job:
            return None
        info = Extended()
        info.Basic.LimitFlags = 0x2000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        process = kernel.OpenProcess(0x0101, False, pid)  # SET_QUOTA | TERMINATE
        ok = bool(process) and bool(
            kernel.SetInformationJobObject(job, 9, ctypes.byref(info), ctypes.sizeof(info))
        )
        ok = ok and bool(kernel.AssignProcessToJobObject(job, process))
        if process:
            kernel.CloseHandle(process)
        if not ok:
            kernel.CloseHandle(job)
            return None
        return int(job)
    except (OSError, AttributeError):
        return None


def _job_active(job: int) -> int | None:
    """Processus encore vivants dans le job ; `None` si la question échoue."""

    class Accounting(ctypes.Structure):
        _fields_ = [
            *((name, ctypes.c_int64) for name in ("tu", "tk", "pu", "pk")),
            *((name, ctypes.c_uint32) for name in ("faults", "total", "active", "ended")),
        ]

    info = Accounting()
    try:
        ok = _kernel().QueryInformationJobObject(
            job, 1, ctypes.byref(info), ctypes.sizeof(info), None
        )
    except (OSError, AttributeError):
        return None
    return int(info.active) if ok else None


def _job_call(name: str, job: int, *extra: int) -> None:
    try:
        getattr(_kernel(), name)(job, *extra)
    except (OSError, AttributeError):
        pass


def terminate_tree(process: subprocess.Popen[bytes], job: int | None = None) -> None:
    """Arrête le processus et ses descendants (Job Object ou taskkill /T sous Windows, groupe
    sous Unix).

    Sous Unix, le groupe est tué même si le chef est déjà sorti : un petit-enfant peut encore
    tenir les tubes. Sous Windows, sans Job Object, un descendant dont le parent est sorti ne
    se retrouve plus (et son PID peut être réutilisé) : `run` borne alors l'attente. Le `job`
    de `spawn` règle ce cas : tout le job est terminé.
    """
    if IS_WINDOWS and job is not None:
        _job_call("TerminateJobObject", job, 1)
    if not IS_WINDOWS:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except OSError:
            pass
    elif process.poll() is None:
        try:
            done = subprocess.run(
                ["taskkill", "/F", "/T", "/PID", str(process.pid)],
                capture_output=True,
                check=False,
                timeout=10,
            )
            killed = done.returncode == 0
        except (OSError, subprocess.SubprocessError):
            killed = False
        if not killed and process.poll() is None:
            process.kill()
    if process.poll() is None:
        try:
            process.kill()
        except OSError:
            pass


def run(
    argv: Sequence[str | os.PathLike[str]],
    *,
    env: Mapping[str, str] | None = None,
    cwd: Path | None = None,
    timeout: float = 10.0,
) -> ProcResult:
    """Lance `argv` sans shell, entrée fermée, avec un délai ; l'arbre est arrêté au délai."""
    try:
        process = subprocess.Popen(
            [os.fspath(a) for a in argv],
            env=None if env is None else dict(env),
            cwd=cwd,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            start_new_session=not IS_WINDOWS,
        )
    except (OSError, ValueError) as exc:
        return ProcResult(returncode=None, error=f"{type(exc).__name__}: {exc}")
    try:
        out, err = process.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        terminate_tree(process)
        try:
            out, err = process.communicate(timeout=KILL_GRACE_S)
        except subprocess.TimeoutExpired:
            # Un descendant orphelin tient encore les tubes : on cesse d'attendre.
            out, err = b"", b""
        return ProcResult(None, _text(out), _text(err), timed_out=True)
    return ProcResult(process.returncode, _text(out), _text(err))


def _text(data: bytes | None) -> str:
    return (data or b"").decode("utf-8", errors="replace")


Stream = Literal["stdout", "stderr"]


@dataclass(frozen=True)
class Chunk:
    """Morceau de sortie, dans l'ordre d'arrivée des deux tubes."""

    stream: Stream
    text: str


_EOF = object()


class Handle:
    """Processus lancé par `spawn` : sa sortie arrive au fil de l'eau, sans bloquer le serveur.

    `chunks()` donne les morceaux dans l'ordre d'arrivée, et `None` à chaque battement
    (de quoi afficher un chronomètre ou tester une annulation). Le délai et l'arrêt d'arbre
    (`terminate`, appelable depuis un autre fil) sont gérés ici ; après un arrêt, un
    descendant qui tiendrait encore les tubes ne retient pas l'appelant au-delà de
    `KILL_GRACE_S`.
    """

    def __init__(
        self, process: subprocess.Popen[bytes], *, timeout: float, job: int | None = None
    ) -> None:
        self._process = process
        self._job = job
        self._deadline = time.monotonic() + timeout
        self._queue: queue.Queue[object] = queue.Queue()
        self._lock = threading.Lock()
        self.timed_out = False
        self.interrupted = False
        self.tree_stopped = True
        """Faux si, après un arrêt, un descendant semble encore vivre (voir `chunks`)."""
        self._done = False
        for pipe, name in ((process.stdout, "stdout"), (process.stderr, "stderr")):
            threading.Thread(target=self._pump, args=(pipe, name), daemon=True).start()

    @property
    def pid(self) -> int:
        return self._process.pid

    @property
    def returncode(self) -> int | None:
        return self._process.poll()

    def _pump(self, pipe: Any, name: Stream) -> None:
        decoder = codecs.getincrementaldecoder("utf-8")(errors="replace")
        try:
            while data := pipe.read1(65536):
                if text := decoder.decode(data):
                    self._queue.put(Chunk(name, text))
            if tail := decoder.decode(b"", final=True):
                self._queue.put(Chunk(name, tail))
        except (OSError, ValueError):
            pass
        finally:
            self._queue.put(_EOF)

    def _kill(self) -> None:
        with self._lock:
            terminate_tree(self._process, self._job)

    def terminate(self) -> None:
        """Arrête l'arbre à la demande de l'apprenant (Ctrl+C) ; sans effet si c'est fini."""
        if self._done:
            return
        self.interrupted = True
        self._kill()

    def chunks(self, tick: float = 0.2) -> Iterator[Chunk | None]:
        """Sortie au fil de l'eau jusqu'à la fin du processus (ou de son arrêt)."""
        eof = 0
        gone_at: float | None = None
        killed_at: float | None = None
        while eof < 2:
            if killed_at is None and time.monotonic() >= self._deadline:
                if self._process.poll() is None:
                    self.timed_out = True
                self._kill()
                killed_at = time.monotonic()
            try:
                item = self._queue.get(timeout=tick)
            except queue.Empty:
                item = None
            if item is _EOF:
                eof += 1
                continue
            if isinstance(item, Chunk):
                yield item
                continue
            if self._process.poll() is not None:
                # Chef sorti, tubes encore tenus : on laisse un instant, puis on arrête l'arbre.
                gone_at = gone_at or time.monotonic()
                if time.monotonic() - gone_at >= KILL_GRACE_S and killed_at is None:
                    self._kill()
                    killed_at = time.monotonic()
            if killed_at is not None and time.monotonic() - killed_at >= KILL_GRACE_S:
                break  # un orphelin tient encore les tubes : on cesse d'attendre
            yield None
        try:
            self._process.wait(timeout=KILL_GRACE_S)
        except subprocess.TimeoutExpired:
            self._kill()
        if killed_at is not None or self.interrupted:
            self.tree_stopped = self._wait_tree_gone()
        self._done = True
        self.close()

    def _tree_alive(self) -> bool | None:
        """Un processus de l'arbre vit-il encore ? `None` : on ne sait pas le dire."""
        if IS_WINDOWS:
            if self._job is None:
                return None
            active = _job_active(self._job)
            return None if active is None else active > 0
        try:
            os.killpg(self._process.pid, 0)
        except ProcessLookupError:
            return False
        except OSError:
            return None
        return True

    def _wait_tree_gone(self) -> bool:
        """Attend (au plus `KILL_GRACE_S`) que l'arbre arrêté ait disparu ; vrai s'il l'est.

        Sans moyen de le savoir (Windows sans Job Object), l'arrêt est tenu pour acquis.
        """
        deadline = time.monotonic() + KILL_GRACE_S
        while True:
            alive = self._tree_alive()
            if not alive:
                return True
            if time.monotonic() >= deadline:
                return False
            time.sleep(0.05)

    def close(self) -> None:
        """Ferme le Job Object : tout descendant restant est arrêté (Windows)."""
        job, self._job = self._job, None
        if job is not None:
            _job_call("CloseHandle", job)


def spawn(
    argv: Sequence[str | os.PathLike[str]],
    *,
    env: Mapping[str, str] | None = None,
    cwd: Path | None = None,
    timeout: float = 30.0,
) -> Handle:
    """Lance `argv` sans shell, entrée fermée, et rend aussitôt un `Handle` (jamais bloquant).

    Lève `OSError` si le processus ne peut pas démarrer (fichier absent, droits…).
    """
    process = subprocess.Popen(
        [os.fspath(a) for a in argv],
        env=None if env is None else dict(env),
        cwd=cwd,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        start_new_session=not IS_WINDOWS,
    )
    return Handle(process, timeout=timeout, job=_make_job(process.pid))
