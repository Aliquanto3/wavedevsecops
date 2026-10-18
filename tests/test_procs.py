"""`procs.run` : délai, arrêt d'arbre et attente bornée même si un descendant tient les tubes."""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

import pytest

from wavedevsecops import procs

PYTHON = getattr(sys, "_base_executable", sys.executable)
"""Interpréteur réel : sous Windows, celui du venv est un lanceur qui ajoute un niveau."""

TIMEOUT = 3.0
BOUND = TIMEOUT + 10 + procs.KILL_GRACE_S + 5
"""Délai + taskkill (10 s au plus) + attente bornée + démarrage de deux interpréteurs."""


def _leader(pid_file: Path, *, leader_waits: bool) -> list[str]:
    """Chef qui lance un petit-enfant héritant des tubes, puis attend ou sort aussitôt."""
    grandchild = "import time; time.sleep(60)"
    code = (
        "import subprocess, sys, time\n"
        f"p = subprocess.Popen([sys.executable, '-c', {grandchild!r}], close_fds=False)\n"
        f"open({str(pid_file)!r}, 'w').write(str(p.pid))\n"
        "print('chef', flush=True)\n" + ("time.sleep(60)\n" if leader_waits else "")
    )
    return [PYTHON, "-c", code]


def _alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


@pytest.mark.parametrize("leader_waits", [True, False], ids=["chef-vivant", "chef-sorti"])
def test_delai_borne_avec_petit_enfant(tmp_path: Path, leader_waits: bool) -> None:
    pid_file = tmp_path / "pid"
    start = time.monotonic()
    result = procs.run(_leader(pid_file, leader_waits=leader_waits), timeout=TIMEOUT)
    elapsed = time.monotonic() - start
    assert result.timed_out and not result.ok
    assert elapsed < BOUND, f"run a attendu {elapsed:.1f} s"
    if not pid_file.exists():
        return
    pid = int(pid_file.read_text())
    if sys.platform != "win32":
        # Sous Unix, le groupe entier est tué, chef sorti ou non.
        deadline = time.monotonic() + 5
        while _alive(pid) and time.monotonic() < deadline:
            time.sleep(0.1)
        assert not _alive(pid), "le petit-enfant a survécu à l'arrêt du groupe"
    elif _alive(pid):
        # Sous Windows sans Job Object, un orphelin peut survivre (report AD-12) : ménage.
        os.kill(pid, 9)


def test_programme_absent_rend_une_erreur(tmp_path: Path) -> None:
    result = procs.run([tmp_path / "absent.exe"])
    assert result.error and not result.ok and result.returncode is None
