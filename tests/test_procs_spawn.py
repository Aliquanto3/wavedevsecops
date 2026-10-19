"""`procs.spawn` : sortie au fil de l'eau, délai, Ctrl+C et arrêt d'arbre sans orphelin (AD-12)."""

from __future__ import annotations

import os
import sys
import threading
import time
from pathlib import Path

import pytest

from wavedevsecops import procs

PYTHON = getattr(sys, "_base_executable", sys.executable)
"""Interpréteur réel : sous Windows, celui du venv est un lanceur qui ajoute un niveau."""

WAIT = 30.0
"""Borne des attentes : très au-delà du besoin, pour ne jamais dépendre de la charge."""


def alive(pid: int) -> bool:
    """Vrai si le processus existe encore (un zombie compte pour mort)."""
    if sys.platform == "win32":
        import ctypes

        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.OpenProcess.restype = ctypes.c_void_p
        handle = kernel.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
        if not handle:
            return False
        code = ctypes.c_ulong()
        kernel.GetExitCodeProcess(ctypes.c_void_p(handle), ctypes.byref(code))
        kernel.CloseHandle(ctypes.c_void_p(handle))
        return code.value == 259  # STILL_ACTIVE
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    try:
        stat = Path(f"/proc/{pid}/stat").read_text(encoding="utf-8")
    except OSError:
        return True
    return stat.rsplit(")", 1)[-1].split()[0] != "Z"


def wait_dead(pid: int) -> bool:
    deadline = time.monotonic() + WAIT
    while alive(pid) and time.monotonic() < deadline:
        time.sleep(0.05)
    return not alive(pid)


def collect(handle: procs.Handle) -> list[procs.Chunk]:
    return [chunk for chunk in handle.chunks(tick=0.05) if chunk is not None]


def tree(pid_file: Path, *, leader_waits: bool) -> list[str]:
    """Chef qui lance un petit-enfant (qui tient les tubes), puis attend ou sort aussitôt."""
    code = (
        "import subprocess, sys, time\n"
        "p = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(120)'],"
        " close_fds=False)\n"
        f"open({str(pid_file)!r}, 'w').write(str(p.pid))\n"
        "print('chef', flush=True)\n" + ("time.sleep(120)\n" if leader_waits else "")
    )
    return [PYTHON, "-c", code]


def test_sortie_au_fil_de_l_eau_et_flux_distincts() -> None:
    code = (
        "import sys, time\n"
        "print('un', flush=True)\n"
        "time.sleep(0.3)\n"
        "print('erreur', file=sys.stderr, flush=True)\n"
        "time.sleep(0.3)\n"
        "print('deux', flush=True)\n"
        "sys.exit(3)\n"
    )
    handle = procs.spawn([PYTHON, "-c", code], timeout=WAIT)
    seen = collect(handle)
    assert [(c.stream, c.text.strip()) for c in seen] == [
        ("stdout", "un"),
        ("stderr", "erreur"),
        ("stdout", "deux"),
    ]
    assert handle.returncode == 3
    assert not handle.timed_out and not handle.interrupted


@pytest.mark.slow
def test_spawn_ne_bloque_pas_et_rend_des_battements() -> None:
    handle = procs.spawn([PYTHON, "-c", "import time; time.sleep(1.5)"], timeout=WAIT)
    assert handle.returncode is None  # rendu aussitôt, le processus tourne encore
    ticks = sum(1 for chunk in handle.chunks(tick=0.05) if chunk is None)
    assert ticks >= 3
    assert handle.returncode == 0


def test_octets_utf8_coupes_entre_deux_lectures() -> None:
    code = (
        "import sys, time\n"
        "out = sys.stdout.buffer\n"
        "data = 'é€'.encode('utf-8')\n"
        "out.write(data[:1]); out.flush(); time.sleep(0.3)\n"
        "out.write(data[1:]); out.flush()\n"
    )
    text = "".join(c.text for c in collect(procs.spawn([PYTHON, "-c", code], timeout=WAIT)))
    assert text == "é€"


def test_demarrage_impossible() -> None:
    with pytest.raises(OSError):
        procs.spawn(["wds-commande-inexistante"])


def test_delai_arrete_l_arbre(tmp_path: Path) -> None:
    pid_file = tmp_path / "pid"
    handle = procs.spawn(tree(pid_file, leader_waits=True), timeout=WAIT)
    deadline = time.monotonic() + WAIT
    while not (pid_file.exists() and pid_file.read_text()) and time.monotonic() < deadline:
        time.sleep(0.02)
    handle._deadline = time.monotonic()  # le délai est atteint : sans dépendre de la charge
    start = time.monotonic()
    collect(handle)
    assert handle.timed_out and not handle.interrupted
    assert time.monotonic() - start < WAIT
    assert wait_dead(int(pid_file.read_text()))


@pytest.mark.parametrize("leader_waits", [True, False], ids=["chef-vivant", "chef-sorti"])
def test_ctrl_c_arrete_l_arbre_sans_orphelin(tmp_path: Path, leader_waits: bool) -> None:
    pid_file = tmp_path / "pid"
    handle = procs.spawn(tree(pid_file, leader_waits=leader_waits), timeout=WAIT)
    first = threading.Event()
    seen: list[procs.Chunk] = []

    def drain() -> None:
        for chunk in handle.chunks(tick=0.05):
            if chunk is not None:
                seen.append(chunk)
                first.set()

    reader = threading.Thread(target=drain)
    reader.start()
    assert first.wait(WAIT)
    deadline = time.monotonic() + WAIT
    while not pid_file.exists() and time.monotonic() < deadline:
        time.sleep(0.02)
    grandchild = int(pid_file.read_text())
    assert alive(grandchild)
    handle.terminate()  # depuis un autre fil que celui qui lit, comme l'intention `interrupt`
    reader.join(WAIT)
    assert not reader.is_alive()
    assert handle.interrupted and not handle.timed_out
    assert wait_dead(grandchild), "le petit-enfant a survécu à l'arrêt d'arbre"
    assert seen and seen[0].text.strip() == "chef"


def test_terminate_apres_la_fin_est_sans_effet() -> None:
    handle = procs.spawn([PYTHON, "-c", "print('ok')"], timeout=WAIT)
    collect(handle)
    handle.terminate()
    assert not handle.interrupted
    assert handle.returncode == 0
