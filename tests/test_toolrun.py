"""`procs.run` et `toolrun.resolve` : résolution par le registre, sans exception visible."""

from __future__ import annotations

import stat
import sys
from pathlib import Path

import pytest

from wavedevsecops import procs, toolrun
from wavedevsecops.config import Settings

PY = Path(sys.executable)


def _registry(tmp_path: Path, **fields: str) -> Path:
    body = {
        "id": '"fake"',
        "usage": '"outil de test"',
        "milestone": '"m"',
        "resolution": '"host-or-provisioned"',
        "min_version": '"2.0"',
        "provisioned_version": '"2.5"',
        "probe": '["-c", "print(\'fake 3.1.4\')"]',
        "version_regex": "'fake (\\d+(?:\\.\\d+)+)'",
        "network": "false",
        "paths": '{ windows = ["fake/fake.cmd"], posix = ["fake/fake"] }',
    } | fields
    path = tmp_path / "tools.toml"
    lines = "\n".join(f"{k} = {v}" for k, v in body.items())
    path.write_text(f"[[tool]]\n{lines}\n", encoding="utf-8")
    return path


def _settings(tmp_path: Path, timeout: float = 20.0) -> Settings:
    return Settings(
        data_dir=tmp_path / "data", tools_file=_registry(tmp_path), probe_timeout_s=timeout
    )


def _provision(tmp_path: Path, version: str) -> Path:
    folder = tmp_path / "data" / "tools" / "fake"
    folder.mkdir(parents=True)
    if sys.platform == "win32":
        script = folder / "fake.cmd"
        script.write_text(f"@echo fake {version}\r\n", encoding="utf-8")
    else:
        script = folder / "fake"
        script.write_text(f"#!/bin/sh\necho fake {version}\n", encoding="utf-8")
        script.chmod(script.stat().st_mode | stat.S_IEXEC)
    return script


def test_run_capture_et_code_de_sortie() -> None:
    result = procs.run([PY, "-c", "import sys; print('a'); sys.exit(3)"])
    assert result.stdout.strip() == "a"
    assert result.returncode == 3 and not result.ok


def test_run_fichier_absent_sans_exception(tmp_path: Path) -> None:
    result = procs.run([tmp_path / "nexiste-pas"])
    assert result.error and result.returncode is None and not result.ok


def test_run_delai_arrete_le_processus() -> None:
    result = procs.run([PY, "-c", "import time; time.sleep(60)"], timeout=0.5)
    assert result.timed_out and not result.ok


def test_hote_assez_recent(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(toolrun.shutil, "which", lambda name: str(PY))
    status = toolrun.resolve("fake", _settings(tmp_path))
    assert (status.state, status.version, status.source) == ("ok", "3.1.4", "host")


def test_hote_trop_ancien_repli_sur_tools(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    registry = _registry(tmp_path, min_version='"9.0"')
    settings = Settings(data_dir=tmp_path / "data", tools_file=registry, probe_timeout_s=20.0)
    monkeypatch.setattr(toolrun.shutil, "which", lambda name: str(PY))
    status = toolrun.resolve("fake", settings)
    assert status.state == "too_old" and "9.0" in status.reason
    script = _provision(tmp_path, "9.5")
    assert toolrun.resolve("fake", settings) == toolrun.ToolStatus(
        "fake", "ok", version="9.5", path=script, source="provisioned"
    )


def test_absent(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(toolrun.shutil, "which", lambda name: None)
    status = toolrun.resolve("fake", _settings(tmp_path))
    assert status.state == "missing" and "introuvable" in status.reason


def test_sonde_trop_lente_marque_l_outil_absent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    registry = _registry(tmp_path, probe='["-c", "import time; time.sleep(60)"]')
    settings = Settings(data_dir=tmp_path / "data", tools_file=registry, probe_timeout_s=0.5)
    monkeypatch.setattr(toolrun.shutil, "which", lambda name: str(PY))
    status = toolrun.resolve("fake", settings)
    assert status.state == "missing" and "répondu" in status.reason


def test_sortie_illisible(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    registry = _registry(tmp_path, probe='["-c", "print(\'bonjour\')"]')
    settings = Settings(data_dir=tmp_path / "data", tools_file=registry)
    monkeypatch.setattr(toolrun.shutil, "which", lambda name: str(PY))
    status = toolrun.resolve("fake", settings)
    assert status.state == "missing" and "illisible" in status.reason


def test_xcode_select_avant_usr_bin_git(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    registry = _registry(tmp_path, id='"git"', version_regex="'fake (\\d+(?:\\.\\d+)+)'")
    settings = Settings(data_dir=tmp_path / "data", tools_file=registry)
    calls: list[list[str]] = []

    def fake_run(argv, **kwargs):  # noqa: ANN001, ANN003, ANN202
        calls.append([str(a) for a in argv])
        return procs.ProcResult(returncode=2, stderr="no developer tools")

    monkeypatch.setattr(toolrun.shutil, "which", lambda name: "/usr/bin/git")
    monkeypatch.setattr(toolrun.procs, "run", fake_run)
    status = toolrun.resolve("git", settings, platform="darwin")
    assert calls == [["xcode-select", "-p"]]  # /usr/bin/git n'est jamais lancé
    assert status.state == "missing" and "Xcode" in status.reason


def test_paquet_python_selon_le_lock(tmp_path: Path) -> None:
    registry = _registry(
        tmp_path, id='"pytest"', resolution='"uv-lock"', provisioned_version='"0.0.1"', probe="[]"
    )
    settings = Settings(data_dir=tmp_path / "data", tools_file=registry)
    status = toolrun.resolve("pytest", settings)
    assert status.state == "mismatch" and "uv sync" in status.reason
    absent = _registry(tmp_path, id='"paquet-inexistant-xyz"', resolution='"uv-lock"', probe="[]")
    settings = Settings(data_dir=tmp_path / "data", tools_file=absent)
    assert toolrun.resolve("paquet-inexistant-xyz", settings).state == "missing"


def test_registre_illisible_sans_exception(tmp_path: Path) -> None:
    settings = Settings(tools_file=tmp_path / "absent.toml")
    assert toolrun.resolve("git", settings).state == "missing"


def test_environnement_hors_ligne(tmp_path: Path) -> None:
    env = toolrun.offline_environment(Settings(data_dir=tmp_path))
    assert env["UV_OFFLINE"] == "1" and env["PIP_NO_INDEX"] == "1"
    assert env["NO_PROXY"] == "127.0.0.1,localhost"
    assert not any(k.lower() in toolrun.PROXY_NAMES for k in env)
    assert Path(env["UV_CACHE_DIR"]) == tmp_path / "uv-cache"


def test_run_tool_lance_l_outil_resolu(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(toolrun.shutil, "which", lambda name: str(PY))
    result = toolrun.run_tool("fake", ["-c", "print('ok')"], settings=_settings(tmp_path))
    assert result.ok and result.stdout.strip() == "ok"
    missing = toolrun.run_tool("inconnu", [], settings=_settings(tmp_path))
    assert missing.error and not missing.ok
