"""Installeur macOS et Linux (Story 1.7) : `install.sh` exécuté par `sh` POSIX.

Aucun accès réseau ni installation réelle : le mode simulation (`WDS_INSTALL_SIMULATE=1`)
journalise les actions dans `<data>/install.simulation.log` et fabrique de faux artefacts.
Ignorés sous Windows (la CI exécute ces tests sur ubuntu et macos). Le téléchargement réel,
pixi, le proxy et l'absence de droits administrateur ne se vérifient que sur un poste réel.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from wavedevsecops.config import Settings
from wavedevsecops.registry import load_registry

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "install.sh"
TOOLS = ROOT / "tools.toml"
SH = shutil.which("sh") if sys.platform != "win32" else None
CURL = shutil.which("curl")

pytestmark = pytest.mark.skipif(SH is None, reason="sh POSIX absent (Windows)")


def _env(data: Path | None, **extra: str) -> dict[str, str]:
    env = {k: v for k, v in os.environ.items() if not k.upper().startswith(("WDS_", "HTTPS_PROXY"))}
    env.pop("https_proxy", None)
    if data is not None:
        env["WDS_DATA_DIR"] = str(data)
    env.update({"WDS_INSTALL_SIMULATE": "1", "WDS_INSTALL_SIMULATE_OS": "Linux", **extra})
    return env


def _sh(
    args: list[str], env: dict[str, str], cwd: Path | None = None
) -> subprocess.CompletedProcess[str]:
    assert SH is not None
    return subprocess.run(  # noqa: S603 - sh du poste, script du dépôt
        [SH, *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=env,
        cwd=cwd,
        timeout=120,
        check=False,
        stdin=subprocess.DEVNULL,
    )


def _install(data: Path, **extra: str) -> subprocess.CompletedProcess[str]:
    return _sh([str(SCRIPT)], _env(data, **extra))


def _lib(code: str, data: Path | None = None, **extra: str) -> str:
    """Évalue du code sh après chargement des fonctions de l'installeur."""
    env = _env(data, WDS_INSTALL_LIBONLY="1", **extra)
    out = _sh(["-c", f". '{SCRIPT}'; REGISTRY='{TOOLS}'; {code}"], env)
    assert out.returncode == 0, out.stderr
    return out.stdout.strip()


def _log(data: Path) -> list[str]:
    return (data / "install.simulation.log").read_text("utf-8").splitlines()


def _record(data: Path) -> dict[str, object]:
    return json.loads((data / "install.json").read_text("utf-8"))


def test_syntaxe_posix_et_fins_de_ligne() -> None:
    assert b"\r" not in SCRIPT.read_bytes()
    assert SCRIPT.read_text("utf-8").startswith("#!/bin/sh\n")
    assert _sh(["-n", str(SCRIPT)], os.environ.copy()).returncode == 0
    dash = shutil.which("dash")
    if dash:
        out = subprocess.run([dash, "-n", str(SCRIPT)], capture_output=True, check=False)  # noqa: S603
        assert out.returncode == 0, out.stderr


def test_versions() -> None:
    cases = {
        ("2.43.0", "2.38"): 0,
        ("2.38", "2.38"): 0,
        ("2.38.0", "2.38"): 0,
        ("2.37.9", "2.38"): 1,
        ("2.9.0", "2.38"): 1,
        ("2.100.0", "2.38"): 0,
        ("v2.39.5", "2.38"): 0,
        ("abc", "2.38"): 1,
    }
    for (version, minimum), expected in cases.items():
        out = _lib(f"version_at_least '{version}' '{minimum}'; echo $?")
        assert out == str(expected), (version, minimum)


def test_registre_lu_comme_python() -> None:
    tools = {t.id: t for t in load_registry(TOOLS).tool}
    assert _lib("tool_value git min_version") == tools["git"].min_version
    assert (
        _lib("tool_value git posix provisioned_version")
        == tools["git"].provisioned_version["posix"]
    )
    assert _lib("tool_value uv provisioned_version") == tools["uv"].provisioned_version
    assert _lib("tool_value uv min_version") == tools["uv"].min_version
    assert _lib("tool_value pixi provisioned_version") == tools["pixi"].provisioned_version
    assert _lib("tool_value gitleaks provisioned_version") == tools["gitleaks"].provisioned_version
    assert _lib("tool_value inconnu provisioned_version") == ""


def test_sommes_sha256(tmp_path: Path) -> None:
    archive = tmp_path / "a.tar.gz"
    archive.write_bytes(b"contenu")
    good = hashlib.sha256(b"contenu").hexdigest()
    sums = tmp_path / "sums.txt"
    sums.write_text(f"{'0' * 64}  autre.tar.gz\n{good}  a.tar.gz\n", "utf-8")
    assert _lib(f"checksum_for '{sums.as_posix()}' a.tar.gz") == good
    assert _lib(f"checksum_for '{sums.as_posix()}' absent.tar.gz") == ""
    assert _lib(f"verify_sha256 '{archive.as_posix()}' {good}; echo $?") == "0"
    assert _lib(f"verify_sha256 '{archive.as_posix()}' {'0' * 64}; echo $?") == "1"


@pytest.mark.skipif(sys.platform not in ("linux", "darwin"), reason="platformdirs")
@pytest.mark.parametrize("xdg", [None, "custom"])
def test_dossier_de_donnees_comme_l_application(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, xdg: str | None
) -> None:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.delenv("XDG_DATA_HOME", raising=False)
    if xdg:
        monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / xdg))
    env = {k: v for k, v in os.environ.items() if not k.upper().startswith("WDS_")}
    env["WDS_INSTALL_LIBONLY"] = "1"
    # Système réel (pas de simulation) : macOS lit ~/Library, Linux XDG_DATA_HOME ou ~/.local/share.
    out = _sh(
        ["-c", f". '{SCRIPT}'; detect_platform; get_data_dir; printf '%s' \"$DATA_DIR\""], env
    )
    assert out.returncode == 0, out.stderr
    assert Path(out.stdout) == Settings().resolved_data_dir()


def test_dossier_de_donnees_macos(tmp_path: Path) -> None:
    out = _lib(
        "OS_NAME=macos; get_data_dir; printf '%s' \"$DATA_DIR\"",
        HOME=str(tmp_path),
    )
    assert out == f"{tmp_path}/Library/Application Support/WaveDevSecOps"


def test_installation_simulee_avec_git_du_poste(tmp_path: Path) -> None:
    out = _install(tmp_path, WDS_INSTALL_SIMULATE_GIT="2.43.0", WDS_INSTALL_SIMULATE_UV="0.13.1")
    assert out.returncode == 0, out.stdout + out.stderr
    log = "\n".join(_log(tmp_path))
    assert "pixi" not in log and "uv-install" not in log
    assert "clone -c core.autocrlf=false" in log and "uv sync --frozen" in log
    assert "gitleaks-extract gitleaks_8.30.1_" in log
    record = _record(tmp_path)
    assert record["schema_version"] == 1
    assert record["installed_at"] and record["run_count"] == 1
    assert isinstance(record["duration_s"], int) and record["duration_s"] >= 0
    assert record["method"] == "clone" and record["app_dir"] == str(tmp_path / "app")
    versions = record["versions"]
    assert isinstance(versions, dict)
    assert versions["git"] == "2.43.0" and versions["git_source"] == "host"
    assert versions["uv"] == "0.13.1" and versions["gitleaks"] == "8.30.1"
    assert (tmp_path / "tools" / "gitleaks" / "gitleaks").exists()
    assert "Installation terminée" in out.stdout


@pytest.mark.parametrize("host_git", ["none", "2.30.0"])
def test_git_provisionne_par_pixi_si_absent_ou_trop_ancien(tmp_path: Path, host_git: str) -> None:
    out = _install(tmp_path, WDS_INSTALL_SIMULATE_GIT=host_git)
    assert out.returncode == 0, out.stdout + out.stderr
    log = "\n".join(_log(tmp_path))
    assert "download https://github.com/prefix-dev/pixi/releases/download/v0.82.0/pixi-" in log
    assert f"pixi global install git==2.56.0 (PIXI_HOME={tmp_path / 'tools'})" in log
    assert "uv-install 0.13.1" in log
    versions = _record(tmp_path)["versions"]
    assert isinstance(versions, dict)
    assert versions["git_source"] == "provisioned" and versions["git"] == "2.56.0"
    assert versions["pixi"] == "0.82.0"
    assert (tmp_path / "tools" / "bin" / "pixi").exists()
    # Chemins attendus par `toolrun` (tools.toml, posix) : <data>/tools/bin/git.
    assert (tmp_path / "tools" / "bin" / "git").exists()


def test_git_provisionne_reutilise_a_la_relance(tmp_path: Path) -> None:
    env = {"WDS_INSTALL_SIMULATE_GIT": "none"}
    assert _install(tmp_path, **env).returncode == 0
    assert _install(tmp_path, **env).returncode == 0
    log = _log(tmp_path)
    assert sum(line.startswith("pixi global install") for line in log) == 1
    assert sum("gitleaks-extract" in line for line in log) == 1
    assert _record(tmp_path)["run_count"] == 2


def test_force_provision_ignore_le_git_du_poste(tmp_path: Path) -> None:
    out = _install(tmp_path, WDS_INSTALL_SIMULATE_GIT="2.43.0", WDS_INSTALL_FORCE_PROVISION_GIT="1")
    assert out.returncode == 0, out.stdout + out.stderr
    assert "pixi global install" in "\n".join(_log(tmp_path))


def test_macos_ne_lance_jamais_usr_bin_git_sans_xcode(tmp_path: Path) -> None:
    out = _install(
        tmp_path,
        WDS_INSTALL_SIMULATE_OS="Darwin",
        WDS_INSTALL_SIMULATE_ARCH="arm64",
        WDS_INSTALL_SIMULATE_GIT="2.39.5",
        WDS_INSTALL_SIMULATE_GIT_PATH="/usr/bin/git",
        WDS_INSTALL_SIMULATE_XCODE="missing",
    )
    assert out.returncode == 0, out.stdout + out.stderr
    log = _log(tmp_path)
    assert "xcode-select -p" in log and "skip /usr/bin/git (xcode-select -p échoue)" in log
    assert any(line.startswith("pixi global install") for line in log)
    assert any("aarch64-apple-darwin" in line for line in log)
    assert any("gitleaks_8.30.1_darwin_arm64.tar.gz" in line for line in log)
    versions = _record(tmp_path)["versions"]
    assert isinstance(versions, dict) and versions["git_source"] == "provisioned"


def test_macos_utilise_usr_bin_git_si_xcode_present(tmp_path: Path) -> None:
    out = _install(
        tmp_path,
        WDS_INSTALL_SIMULATE_OS="Darwin",
        WDS_INSTALL_SIMULATE_GIT="2.39.5",
        WDS_INSTALL_SIMULATE_GIT_PATH="/usr/bin/git",
        WDS_INSTALL_SIMULATE_XCODE="ok",
    )
    assert out.returncode == 0, out.stdout + out.stderr
    log = _log(tmp_path)
    assert "xcode-select -p" in log and not any(line.startswith("pixi") for line in log)
    versions = _record(tmp_path)["versions"]
    assert isinstance(versions, dict) and versions["git_source"] == "host"


def test_linux_ne_teste_pas_xcode(tmp_path: Path) -> None:
    out = _install(
        tmp_path, WDS_INSTALL_SIMULATE_GIT="2.43.0", WDS_INSTALL_SIMULATE_GIT_PATH="/usr/bin/git"
    )
    assert out.returncode == 0, out.stdout + out.stderr
    assert "xcode-select -p" not in _log(tmp_path)


def test_mise_a_jour_conserve_progress(tmp_path: Path) -> None:
    env = {"WDS_INSTALL_SIMULATE_GIT": "2.43.0"}
    assert _install(tmp_path, **env).returncode == 0
    first = _record(tmp_path)
    progress = tmp_path / "progress.json"
    content = '{"schema_version": 1, "events": ["gardé"]}'
    progress.write_text(content, "utf-8")
    assert _install(tmp_path, **env).returncode == 0
    assert progress.read_text("utf-8") == content
    second = _record(tmp_path)
    assert second["installed_at"] == first["installed_at"]
    assert second["run_count"] == 2 and str(second["updated_at"]) >= str(first["updated_at"])
    assert "update-clone" in "\n".join(_log(tmp_path))


def test_echec_telechargement_message_francais_et_reprise(tmp_path: Path) -> None:
    out = _install(tmp_path, WDS_INSTALL_SIMULATE_GIT="none", WDS_INSTALL_SIMULATE_FAIL="download")
    assert out.returncode == 1
    text = out.stdout + out.stderr
    assert "Cause :" in text and "HTTPS_PROXY" in text and "UV_SYSTEM_CERTS" in text
    assert "clone" in text and "zip" in text and "Relancez" in text and "étape" in text
    assert not (tmp_path / "install.json").exists()
    out = _install(tmp_path, WDS_INSTALL_SIMULATE_GIT="none")
    assert out.returncode == 0, out.stdout + out.stderr
    assert (tmp_path / "install.json").exists()


def test_echec_pixi_puis_reprise(tmp_path: Path) -> None:
    out = _install(tmp_path, WDS_INSTALL_SIMULATE_GIT="none", WDS_INSTALL_SIMULATE_FAIL="pixi")
    assert out.returncode == 1 and "pixi global install" in out.stderr
    assert not (tmp_path / "install.json").exists()
    assert _install(tmp_path, WDS_INSTALL_SIMULATE_GIT="none").returncode == 0


def test_somme_fausse_arrete_gitleaks(tmp_path: Path) -> None:
    out = _install(
        tmp_path, WDS_INSTALL_SIMULATE_GIT="2.43.0", WDS_INSTALL_SIMULATE_FAIL="checksum"
    )
    assert out.returncode == 1
    assert "ne correspond pas" in out.stderr and "gitleaks" in out.stderr.lower()
    assert not (tmp_path / "install.json").exists()
    assert not (tmp_path / "tools" / "gitleaks").exists()
    assert not list((tmp_path / "cache" / "downloads").glob("gitleaks_*.tar.gz"))
    assert _install(tmp_path, WDS_INSTALL_SIMULATE_GIT="2.43.0").returncode == 0


def test_reprise_apres_echec_partiel_du_sync(tmp_path: Path) -> None:
    env = {"WDS_INSTALL_SIMULATE_GIT": "2.43.0"}
    assert _install(tmp_path, WDS_INSTALL_SIMULATE_FAIL="sync", **env).returncode == 1
    assert not (tmp_path / "install.json").exists()
    assert (tmp_path / "app" / ".git").exists()
    assert _install(tmp_path, **env).returncode == 0
    log = _log(tmp_path)
    assert sum(line.startswith("clone ") for line in log) == 1
    assert "update-clone" in "\n".join(log)


def test_voie_archive_sans_git(tmp_path: Path) -> None:
    out = _install(tmp_path, WDS_INSTALL_METHOD="zip", WDS_INSTALL_SIMULATE_GIT="none")
    assert out.returncode == 0, out.stdout + out.stderr
    log = "\n".join(_log(tmp_path))
    assert "pixi" not in log and "zip-extract" in log and "archive/main.tar.gz" in log
    record = _record(tmp_path)
    assert record["method"] == "zip"
    versions = record["versions"]
    assert isinstance(versions, dict) and versions["app"] == "zip:main" and "git" not in versions
    assert (tmp_path / "app" / "pyproject.toml").exists()


def test_methode_inconnue_refusee(tmp_path: Path) -> None:
    out = _install(tmp_path, WDS_INSTALL_METHOD="ftp")
    assert out.returncode == 1 and "clone et zip" in out.stderr


def test_install_json_futur_non_modifie(tmp_path: Path) -> None:
    future = '{\n  "schema_version": 99\n}\n'
    (tmp_path / "install.json").write_text(future, "utf-8")
    out = _install(tmp_path, WDS_INSTALL_SIMULATE_GIT="2.43.0")
    assert out.returncode == 1 and "plus récente" in out.stderr
    assert (tmp_path / "install.json").read_text("utf-8") == future


def test_proxy_pose_uv_system_certs(tmp_path: Path) -> None:
    out = _install(
        tmp_path, WDS_INSTALL_SIMULATE_GIT="2.43.0", HTTPS_PROXY="http://proxy.invalid:8080"
    )
    assert out.returncode == 0, out.stdout + out.stderr
    assert "Proxy détecté" in out.stdout and "UV_SYSTEM_CERTS=true" in out.stdout


@pytest.mark.skipif(CURL is None, reason="curl absent")
def test_proxy_injoignable_fait_echouer_le_telechargement(tmp_path: Path) -> None:
    # Hors simulation : curl passe par le proxy (port fermé) et échoue sans toucher au réseau.
    env = _env(tmp_path, HTTPS_PROXY="http://127.0.0.1:9", WDS_INSTALL_LIBONLY="1")
    env.pop("WDS_INSTALL_SIMULATE")
    code = (
        f". '{SCRIPT}'; CURRENT_STEP=essai; DATA_DIR='{tmp_path}'; init_network; "
        "fetch https://github.com/Aliquanto3/wavedevsecops/raw/main/README.md "
        f"'{tmp_path}/x/README.md'"
    )
    out = _sh(["-c", code], env)
    assert out.returncode == 1, out.stdout + out.stderr
    assert "Proxy détecté" in out.stdout and "Cause :" in out.stderr
    assert "HTTPS_PROXY" in out.stderr and not (tmp_path / "x" / "README.md").exists()
    assert not list((tmp_path / "x").glob("*.part"))


def _readme_command() -> str:
    readme = (ROOT / "README.md").read_text("utf-8")
    lines = [line.strip() for line in readme.splitlines() if "install.sh | sh" in line]
    assert len(lines) == 1
    return lines[0]


RAW = "https://raw.githubusercontent.com/Aliquanto3/wavedevsecops/main/install.sh"


def test_commande_du_readme_identique_a_l_entete() -> None:
    assert any(_readme_command() in line for line in SCRIPT.read_text("utf-8").splitlines()[:8])
    assert "curl -fsSL" in _readme_command() and RAW in _readme_command()


@pytest.mark.skipif(CURL is None, reason="curl absent")
def test_voie_collee_installe_en_simulation(tmp_path: Path) -> None:
    # Commande du README telle quelle (script lu par un tube : $0 n'est pas un fichier), URL en file://.
    command = _readme_command().replace(RAW, SCRIPT.as_uri())
    env = _env(tmp_path / "data", WDS_INSTALL_SIMULATE_TOOLS_TOML=str(TOOLS))
    env["WDS_INSTALL_SIMULATE_GIT"] = "2.43.0"
    out = _sh(["-c", command], env, cwd=tmp_path)
    assert out.returncode == 0, out.stdout + out.stderr
    assert "Installation terminée" in out.stdout
    log = "\n".join(_log(tmp_path / "data"))
    assert "raw.githubusercontent.com/Aliquanto3/wavedevsecops/main/tools.toml" in log
    versions = _record(tmp_path / "data")["versions"]
    assert isinstance(versions, dict) and versions["git"] == "2.43.0"


@pytest.mark.skipif(CURL is None, reason="curl absent")
def test_voie_collee_echec_message_et_code(tmp_path: Path) -> None:
    command = _readme_command().replace(RAW, SCRIPT.as_uri())
    env = _env(tmp_path / "data", WDS_INSTALL_SIMULATE_TOOLS_TOML=str(TOOLS))
    env.update(WDS_INSTALL_SIMULATE_GIT="none", WDS_INSTALL_SIMULATE_FAIL="download")
    out = _sh(["-c", command], env, cwd=tmp_path)
    assert out.returncode == 1
    assert "Cause :" in out.stderr and "Relancez" in out.stderr
    assert not (tmp_path / "data" / "install.json").exists()


def test_dossier_app_etranger_non_supprime(tmp_path: Path) -> None:
    foreign = tmp_path / "app" / "mes-notes.txt"
    foreign.parent.mkdir()
    foreign.write_text("à garder", "utf-8")
    for method in ("clone", "zip"):
        out = _install(tmp_path, WDS_INSTALL_METHOD=method, WDS_INSTALL_SIMULATE_GIT="2.43.0")
        assert out.returncode == 1 and "ne contient pas l'application" in out.stderr
        assert foreign.read_text("utf-8") == "à garder"
