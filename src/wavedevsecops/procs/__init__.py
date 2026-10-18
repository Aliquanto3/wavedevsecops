"""Création de sous-processus, délais et arrêt d'arbre (AD-12).

Seul `procs` crée des sous-processus ; seuls `gitio` et `toolrun` l'appellent (AD-1).

Story 1.4 : lanceur bloquant `run` (sondes courtes) et `terminate_tree`. Le lanceur non
bloquant `spawn -> Handle` et le Job Object de Windows viennent avec les stories qui
exécutent des commandes longues.
"""

from __future__ import annotations

import os
import signal
import subprocess
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

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


def terminate_tree(process: subprocess.Popen[bytes]) -> None:
    """Arrête le processus et ses descendants (taskkill /T sous Windows, groupe sous Unix).

    Sous Unix, le groupe est tué même si le chef est déjà sorti : un petit-enfant peut encore
    tenir les tubes. Sous Windows, sans Job Object, un descendant dont le parent est sorti ne
    se retrouve plus (et son PID peut être réutilisé) : `run` borne alors l'attente.
    """
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
