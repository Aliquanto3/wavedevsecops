"""`llmrun` (Story 6.6) : environnement et lancement du code d'exercice, sans réseau ni modèle."""

from __future__ import annotations

import json
import os
import sys
import threading
import time
from pathlib import Path

import pytest

from wavedevsecops import llmrun, toolrun
from wavedevsecops.config import Settings
from wavedevsecops.wsfs import Layout

PROXIES = {
    "HTTPS_PROXY": "http://proxy.example:3128",
    "http_proxy": "http://proxy.example:3128",
    "NO_PROXY": "intranet.example",
}


def _settings(tmp_path: Path, **fields: object) -> Settings:
    return Settings(data_dir=tmp_path / "data", **fields)


def test_environnement_du_code_d_exercice(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    offline = toolrun.offline_environment(settings)
    assert offline[toolrun.NETGUARD_VARIABLE] == "1"  # les outils restent sous la garde
    env = llmrun.exercise_environment(settings, PROXIES)
    assert toolrun.NETGUARD_VARIABLE not in env  # llmrun seul lance sans la garde réseau
    assert env["HTTPS_PROXY"] == PROXIES["HTTPS_PROXY"]
    assert env["HTTP_PROXY"] == PROXIES["http_proxy"]  # casse ignorée à la lecture
    # La boucle locale (Ollama) reste hors proxy, l'exclusion de l'apprenant est gardée.
    assert env["NO_PROXY"] == "intranet.example,127.0.0.1,localhost"
    assert env["PYTHONUTF8"] == "1"


def test_environnement_sans_proxy_garde_la_boucle_locale(tmp_path: Path) -> None:
    env = llmrun.exercise_environment(_settings(tmp_path), {})
    assert not {n for n in env if n.upper() in {"HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY"}}
    assert env["NO_PROXY"] == "127.0.0.1,localhost"


def _fake_project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, source: str) -> Layout:
    layout = Layout(root=tmp_path / "ws")
    layout.repo.mkdir(parents=True)
    (layout.repo / "fake_entry.py").write_text(source, encoding="utf-8")
    monkeypatch.setattr(llmrun, "ENTRY_POINT", "fake_entry")
    monkeypatch.setattr(
        toolrun, "venv_python", lambda venv, platform=sys.platform: Path(sys.executable)
    )
    return layout


def _drain(handle: toolrun.Handle) -> dict[str, str]:
    out = {"stdout": "", "stderr": ""}
    for chunk in handle.chunks(tick=0.05):
        if chunk is not None:
            out[chunk.stream] += chunk.text
    return out


def test_environnement_ne_transmet_que_le_necessaire(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("GITHUB_TOKEN", "secret")
    monkeypatch.setenv("PYTHONPATH", "/ailleurs")
    monkeypatch.setenv("TZ", "Europe/Paris")
    env = llmrun.exercise_environment(_settings(tmp_path), {})
    assert "GITHUB_TOKEN" not in env and "PYTHONPATH" not in env
    assert env["TZ"] == "Europe/Paris"
    assert {k.upper() for k in env} >= {"PATH", "PYTHONUTF8", "UV_OFFLINE"}
    if sys.platform == "win32":
        assert "SYSTEMROOT" in {k.upper() for k in env}  # sans lui, pas de socket


def test_lancement_reel_dans_un_sous_processus(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("WDS_SECRET_TEST", "x")
    layout = _fake_project(
        tmp_path,
        monkeypatch,
        "import json, os, sys\n"
        "print(json.dumps({'argv': sys.argv[1:], 'guard': os.environ.get('WDS_NETGUARD'),"
        " 'proxy': os.environ.get('HTTPS_PROXY'), 'cwd': os.getcwd(),"
        " 'secret': os.environ.get('WDS_SECRET_TEST')}))\n",
    )
    handle = llmrun.start_exercise(layout, _settings(tmp_path), question="Salut", environ=PROXIES)
    out = _drain(handle)
    assert handle.returncode == 0, out["stderr"]
    data = json.loads(out["stdout"])
    assert data["argv"] == ["Salut"]
    assert data["guard"] is None and data["proxy"] == PROXIES["HTTPS_PROXY"]
    assert data["secret"] is None
    assert Path(data["cwd"]).resolve() == layout.repo.resolve()


def test_delai_arrete_le_code(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    layout = _fake_project(tmp_path, monkeypatch, "import time\ntime.sleep(60)\n")
    handle = llmrun.start_exercise(layout, _settings(tmp_path, llm_run_timeout_s=1.0))
    started = time.monotonic()
    _drain(handle)
    assert handle.timed_out and time.monotonic() - started < 20


def test_interruption_arrete_l_arbre(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Ctrl+C : le processus et son enfant sont arrêtés, bien avant le délai."""
    pid_file = tmp_path / "child.pid"
    layout = _fake_project(
        tmp_path,
        monkeypatch,
        "import subprocess, sys, time\n"
        "child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'])\n"
        f"open({str(pid_file)!r}, 'w').write(str(child.pid))\n"
        "print('pret', flush=True)\n"
        "time.sleep(60)\n",
    )
    handle = llmrun.start_exercise(layout, _settings(tmp_path))
    started = time.monotonic()
    seen: list[str] = []
    for chunk in handle.chunks(tick=0.05):
        if chunk is not None:
            seen.append(chunk.text)
            if "pret" in "".join(seen):
                threading.Thread(target=handle.terminate).start()
    assert handle.interrupted and not handle.timed_out
    assert time.monotonic() - started < 20
    assert handle.tree_stopped
    child = int(pid_file.read_text("utf-8"))
    if sys.platform != "win32":
        with pytest.raises(ProcessLookupError):
            os.kill(child, 0)


def test_environnement_absent_est_cree_hors_ligne_ou_signale(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    layout = Layout(root=tmp_path / "ws")
    layout.repo.mkdir(parents=True)
    called: list[tuple[Path, Path]] = []

    def failing_sync(project, venv, settings=None, **kwargs):
        called.append((project, venv))
        return toolrun.ProcResult(returncode=None, error="uv indisponible")

    monkeypatch.setattr(toolrun, "sync_environment", failing_sync)
    with pytest.raises(llmrun.ExerciseUnavailable) as failed:
        llmrun.start_exercise(layout, _settings(tmp_path))
    assert failed.value.reason == "uv indisponible"
    assert called == [(layout.repo, toolrun.venv_dir(layout.root))]


def test_spawn_module_sans_environnement(tmp_path: Path) -> None:
    with pytest.raises(OSError, match="absent"):
        toolrun.spawn_module(tmp_path / "absent", "inventory", env={})


def test_venv_python_selon_la_famille(tmp_path: Path) -> None:
    (tmp_path / "Scripts").mkdir()
    (tmp_path / "Scripts" / "python.exe").write_text("", encoding="utf-8")
    assert toolrun.venv_python(tmp_path, "win32") == tmp_path / "Scripts" / "python.exe"
    assert toolrun.venv_python(tmp_path, "linux") is None
