"""`procs.run` et `toolrun.resolve` : résolution par le registre, sans exception visible."""

from __future__ import annotations

import stat
import sys
import threading
import time
from pathlib import Path

import pytest

from wavedevsecops import procs, toolrun
from wavedevsecops.config import Settings
from wavedevsecops.registry import load_registry

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


# --- Story 7.1 : environnement d'exercice hors ligne (AD-12) -------------------------------


def _fake_venv(root: Path, platform: str, packages: dict[str, str]) -> Path:
    venv = root / "cache" / "venv"
    if toolrun.family(platform) == "windows":
        site, scripts, suffix = venv / "Lib" / "site-packages", venv / "Scripts", ".exe"
    else:
        site, scripts, suffix = venv / "lib" / "python3.14" / "site-packages", venv / "bin", ""
    site.mkdir(parents=True)
    scripts.mkdir(parents=True)
    for name, version in packages.items():
        (site / f"{name.replace('-', '_')}-{version}.dist-info").mkdir()
        (scripts / f"{name}{suffix}").write_text("", encoding="utf-8")
    return venv


@pytest.mark.parametrize("platform", ["win32", "linux"])
def test_outil_de_la_chaine_resolu_dans_le_venv(tmp_path: Path, platform: str) -> None:
    venv = _fake_venv(tmp_path, platform, {"ruff": "0.17.1", "pytest-cov": "6.0.0"})
    assert toolrun.venv_dir(tmp_path) == venv
    status = toolrun.resolve("ruff", Settings(data_dir=tmp_path), platform=platform, venv=venv)
    assert status.ok and status.source == "environment" and status.version == "0.17.1"
    assert status.path is not None and status.path.parent.parent == venv
    cov = toolrun.resolve("pytest-cov", Settings(), platform=platform, venv=venv)
    assert cov.state == "mismatch" and "abîmé" in cov.reason and "uv sync" in cov.reason
    absent = toolrun.resolve("bandit", Settings(), platform=platform, venv=venv)
    assert absent.state == "missing" and "uv sync" in absent.reason
    nowhere = toolrun.resolve("ruff", Settings(), platform=platform, venv=tmp_path / "x")
    assert nowhere.state == "missing"


def test_environnement_hors_ligne_story_7_1(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HTTPS_PROXY", "http://proxy.corp:3128")
    monkeypatch.setenv("all_proxy", "socks5://proxy.corp:1080")
    env = toolrun.offline_environment(Settings(data_dir=tmp_path))
    assert not any(k.lower() in toolrun.PROXY_NAMES for k in env)
    assert env["no_proxy"] == "127.0.0.1,localhost" and env["UV_PYTHON_DOWNLOADS"] == "never"
    assert Path(env["UV_PYTHON_INSTALL_DIR"]) == tmp_path / "uv-cache" / "python"
    assert env["WDS_NETGUARD"] == "1"
    for name in ("RUFF_CACHE_DIR", "COVERAGE_FILE", "PRE_COMMIT_HOME"):
        assert Path(env[name]).parent == tmp_path / "cache"


def test_sync_environment_hors_ligne(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[list[str], dict[str, str]]] = []
    venv = _fake_venv(tmp_path / "ws", sys.platform, {})

    real_spawn = procs.spawn
    started: list[procs.Handle] = []

    def fake_spawn(argv, *, env, cwd, timeout):  # noqa: ANN001, ANN202
        calls.append(([str(a) for a in argv], env))
        return real_spawn([PY, "-c", "pass"], env=env, cwd=cwd, timeout=timeout)

    uv = toolrun.ToolStatus("uv", "ok", "0.13.1", PY, "host")
    monkeypatch.setattr(toolrun, "resolve", lambda tool_id, *a, **k: uv)
    monkeypatch.setattr(toolrun.procs, "spawn", fake_spawn)
    project = tmp_path / "ws" / "repo"
    project.mkdir(parents=True)
    result = toolrun.sync_environment(
        project, venv, Settings(data_dir=tmp_path / "data"), on_start=started.append
    )
    assert result.ok and len(started) == 1  # `on_start` reçoit le Handle (arrêt possible)
    ((argv, env),) = calls
    assert argv == [str(PY), "sync", "--offline", "--frozen", "--project", str(project)]
    assert env["UV_PROJECT_ENVIRONMENT"] == str(venv) and env["UV_OFFLINE"] == "1"
    assert env["UV_CACHE_DIR"] == str(tmp_path / "data" / "uv-cache")
    site = toolrun.site_packages(venv)
    assert site is not None
    assert (site / "_wds_netguard.pth").read_text("utf-8").strip() == "import _wds_netguard"
    # Sans uv utilisable, aucune exception : l'erreur est rendue.
    monkeypatch.setattr(
        toolrun, "resolve", lambda *a, **k: toolrun.ToolStatus("uv", "missing", reason="absent")
    )
    failed = toolrun.sync_environment(project, venv, Settings(data_dir=tmp_path / "data"))
    assert not failed.ok and failed.error == "absent"


def test_sync_environment_est_interruptible(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Report de la 6.6 : `uv sync` s'arrête sur `terminate` (Ctrl+C, mise en veille)."""
    real_spawn = procs.spawn
    sleeper = [PY, "-c", "import time; time.sleep(60)"]
    uv = toolrun.ToolStatus("uv", "ok", "0.13.1", PY, "host")
    monkeypatch.setattr(toolrun, "resolve", lambda tool_id, *a, **k: uv)
    monkeypatch.setattr(
        toolrun.procs,
        "spawn",
        lambda argv, *, env, cwd, timeout: real_spawn(sleeper, env=env, cwd=cwd, timeout=timeout),
    )
    project = tmp_path / "repo"
    project.mkdir()
    started = time.monotonic()
    result = toolrun.sync_environment(
        project,
        tmp_path / "venv",
        Settings(data_dir=tmp_path / "data"),
        on_start=lambda handle: threading.Timer(0.5, handle.terminate).start(),
    )
    assert not result.ok and result.error == "interrompu"
    assert time.monotonic() - started < 30


_CONNECT = """
import socket
server = socket.socket()
server.bind(("127.0.0.1", 0))
server.listen(1)
client = socket.socket()
client.connect(server.getsockname())  # loopback : permis
client.close()
try:
    socket.socket().connect(("192.0.2.1", 9))  # TEST-NET-1 : refusé avant tout envoi
except PermissionError as exc:
    print("refusé", exc)
"""


def test_garde_reseau_du_venv(tmp_path: Path) -> None:
    script = tmp_path / "essai.py"
    script.write_text(toolrun.NETGUARD_SOURCE + _CONNECT, encoding="utf-8")
    env = toolrun.probe_environment()
    env["WDS_NETGUARD"] = "1"
    result = procs.run([PY, "-I", script], env=env, timeout=30)
    assert result.ok, result.stderr
    assert "WaveDevSecOps" in result.stdout and "192.0.2.1" in result.stdout


_UDP_ET_DNS = """
import socket
for essai in (
    lambda: socket.socket(socket.AF_INET, socket.SOCK_DGRAM).sendto(b"x", ("192.0.2.1", 53)),
    lambda: socket.getaddrinfo("exemple.invalid", 80),
):
    try:
        essai()
        print("PASSE")
    except PermissionError:
        print("REFUSE")
"""


def test_garde_reseau_refuse_udp_et_resolution(tmp_path: Path) -> None:
    script = tmp_path / "essai.py"
    script.write_text(toolrun.NETGUARD_SOURCE + _UDP_ET_DNS, encoding="utf-8")
    env = toolrun.probe_environment()
    env["WDS_NETGUARD"] = "1"
    result = procs.run([PY, "-I", script], env=env, timeout=30)
    assert result.ok, result.stderr
    assert result.stdout.split() == ["REFUSE", "REFUSE"]


@pytest.mark.parametrize(
    ("event", "args", "permis"),
    [
        ("socket.connect", (None, ("127.0.0.1", 80)), True),
        ("socket.connect", (None, ("::1", 80, 0, 0)), True),
        ("socket.connect", (None, ("::ffff:127.0.0.1", 80)), True),
        ("socket.connect", (None, ("localhost", 80)), True),
        ("socket.connect", (None, "/tmp/socket"), True),
        ("socket.connect", (None, ("127.evil.example", 80)), False),
        ("socket.connect", (None, ("192.0.2.1", 80)), False),
        ("socket.sendto", (None, ("192.0.2.1", 53)), False),
        ("socket.sendmsg", (None, ("192.0.2.1", 53)), False),
        ("socket.sendmsg", (None, None), True),
        ("socket.getaddrinfo", ("127.evil.example", 80, 0, 0, 0, 0), False),
        ("socket.getaddrinfo", ("localhost", 80, 0, 0, 0, 0), True),
        ("socket.getaddrinfo", ("192.0.2.1", 80, 0, 0, 0, 0), True),
        ("socket.gethostbyname", ("pypi.org",), False),
    ],
)
def test_garde_reseau_loopback_strict(event: str, args: tuple, permis: bool) -> None:
    namespace: dict[str, object] = {}
    exec(toolrun.NETGUARD_SOURCE.replace('os.environ.get("WDS_NETGUARD")', "None"), namespace)
    hook = namespace["_wds_netguard"]
    if permis:
        hook(event, args)  # type: ignore[operator]
    else:
        with pytest.raises(PermissionError):
            hook(event, args)  # type: ignore[operator]


@pytest.mark.parametrize("platform", ["win32", "linux"])
def test_commande_manquante_mais_greffon_pret(tmp_path: Path, platform: str) -> None:
    venv = _fake_venv(tmp_path, platform, {"ruff": "0.17.1", "pytest-cov": "7.1.0"})
    site = toolrun.site_packages(venv, platform)
    assert site is not None
    (site / "ruff-0.17.1.dist-info" / "entry_points.txt").write_text(
        "[console_scripts]\nruff = ruff.__main__:main\n", encoding="utf-8"
    )
    (site / "pytest_cov-7.1.0.dist-info" / "entry_points.txt").write_text(
        "[pytest11]\npytest_cov = pytest_cov.plugin\n", encoding="utf-8"
    )
    for name in ("ruff", "pytest-cov"):
        for exe in venv.glob(f"*/{name}*"):
            exe.unlink()
    ruff = toolrun.resolve("ruff", Settings(), platform=platform, venv=venv)
    assert ruff.state == "mismatch" and "commande ruff manque" in ruff.reason
    cov = toolrun.resolve("pytest-cov", Settings(), platform=platform, venv=venv)
    assert cov.ok and cov.path is None  # greffon pytest : aucune commande attendue


def test_uv_hors_du_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(toolrun.shutil, "which", lambda name: None)
    monkeypatch.delenv("UV", raising=False)
    monkeypatch.setenv("UV_INSTALL_DIR", str(tmp_path / "bin"))
    tool = load_registry().get("uv")
    assert toolrun._host_candidate(tool, "linux", 1.0)[0] is None
    (tmp_path / "bin").mkdir()
    installed = tmp_path / "bin" / "uv.exe"
    installed.write_text("", encoding="utf-8")
    assert toolrun._host_candidate(tool, "win32", 1.0)[0] == installed
    launcher = tmp_path / "uv-lanceur"
    launcher.write_text("", encoding="utf-8")
    monkeypatch.setenv("UV", str(launcher))  # posé par `uv run` au lancement de l'application
    assert toolrun._host_candidate(tool, "linux", 1.0)[0] == launcher
