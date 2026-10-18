"""Installeur Windows (Story 1.6) : `install.ps1` exécuté par Windows PowerShell 5.1.

Aucun accès réseau ni installation réelle : le mode simulation (`WDS_INSTALL_SIMULATE=1`)
journalise les actions dans `<data>/install.simulation.log` et fabrique de faux artefacts.
Le téléchargement réel, PortableGit, le proxy et l'absence de droits administrateur ne se
vérifient que sur un poste Windows réel.
"""

from __future__ import annotations

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
SCRIPT = ROOT / "install.ps1"
POWERSHELL = shutil.which("powershell") if sys.platform == "win32" else None

pytestmark = pytest.mark.skipif(POWERSHELL is None, reason="Windows PowerShell absent")


def _env(data: Path, **extra: str) -> dict[str, str]:
    env = {k: v for k, v in os.environ.items() if not k.upper().startswith(("WDS_", "HTTPS_PROXY"))}
    env.update(WDS_DATA_DIR=str(data), WDS_INSTALL_SIMULATE="1", **extra)
    return env


def _run(args: list[str], env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603 - PowerShell du poste, script du dépôt
        [POWERSHELL, "-NoProfile", "-ExecutionPolicy", "Bypass", *args],
        capture_output=True,
        text=True,
        encoding="oem",  # page de code de la console Windows
        errors="replace",
        env=env,
        timeout=120,
        check=False,
        stdin=subprocess.DEVNULL,
    )


def _install(data: Path, **extra: str) -> subprocess.CompletedProcess[str]:
    return _run(["-File", str(SCRIPT)], _env(data, **extra))


def _lib(expression: str, data: Path) -> str:
    """Évalue une expression PowerShell après chargement des fonctions de l'installeur."""
    out = _run(["-Command", f". '{SCRIPT}'; {expression}"], _env(data, WDS_INSTALL_LIBONLY="1"))
    assert out.returncode == 0, out.stderr
    return out.stdout.strip()


def _log(data: Path) -> list[str]:
    return (data / "install.simulation.log").read_text("utf-8-sig").splitlines()


def test_script_utf8_avec_bom() -> None:
    # Windows PowerShell 5.1 lit en ANSI un fichier UTF-8 sans BOM : les accents seraient cassés.
    assert SCRIPT.read_bytes().startswith(b"\xef\xbb\xbf")


def test_versions_git(tmp_path: Path) -> None:
    cases = {
        ("2.43.0.windows.1", "2.38"): "True",
        ("2.38", "2.38"): "True",
        ("2.38.0", "2.38"): "True",
        ("2.37.9", "2.38"): "False",
        ("2.9.0", "2.38"): "False",
        ("2.100.0", "2.38"): "True",
        ("abc", "2.38"): "False",
    }
    for (version, minimum), expected in cases.items():
        assert _lib(f"Test-VersionAtLeast '{version}' '{minimum}'", tmp_path) == expected


def test_registre_lu_comme_python(tmp_path: Path) -> None:
    tools = {t.id: t for t in load_registry(ROOT / "tools.toml").tool}
    out = _lib(
        f"$r = Read-ToolsRegistry '{ROOT / 'tools.toml'}'; "
        "$r['git']['min_version']; Get-ProvisionedVersion $r['git']; "
        "Get-ProvisionedVersion $r['uv']; $r['uv']['min_version']; $r.Count",
        tmp_path,
    ).splitlines()
    assert out[0] == tools["git"].min_version
    assert out[1] == tools["git"].provisioned_version["windows"]
    assert out[2] == tools["uv"].provisioned_version
    assert out[3] == tools["uv"].min_version
    assert int(out[4]) == len(tools)


def test_url_portablegit(tmp_path: Path) -> None:
    url = _lib("Get-PortableGitUrl '2.56.0.windows.2'", tmp_path)
    assert "/download/v2.56.0.windows.2/PortableGit-2.56.0.2-" in url
    assert "/PortableGit-2.56.0-" in _lib("Get-PortableGitUrl '2.56.0.windows.1'", tmp_path)


def test_dossier_de_donnees_comme_l_application() -> None:
    env = {k: v for k, v in os.environ.items() if not k.upper().startswith("WDS_")}
    out = _run(["-Command", f". '{SCRIPT}'; Get-DataDir"], {**env, "WDS_INSTALL_LIBONLY": "1"})
    assert Path(out.stdout.strip()) == Settings().resolved_data_dir()


def test_installation_simulee_avec_git_du_poste(tmp_path: Path) -> None:
    out = _install(tmp_path, WDS_INSTALL_SIMULATE_GIT="2.43.0", WDS_INSTALL_SIMULATE_UV="0.13.1")
    assert out.returncode == 0, out.stdout + out.stderr
    log = "\n".join(_log(tmp_path))
    assert "portablegit" not in log and "uv-install" not in log
    assert "clone -c core.autocrlf=false" in log and "uv sync --frozen" in log
    record = json.loads((tmp_path / "install.json").read_text("utf-8"))
    assert record["schema_version"] == 1
    assert record["installed_at"] and record["duration_s"] >= 0
    assert record["versions"]["git"] == "2.43.0" and record["versions"]["git_source"] == "host"
    assert record["versions"]["uv"] == "0.13.1"
    assert not (tmp_path / "install.json").read_bytes().startswith(b"\xef\xbb\xbf")


@pytest.mark.parametrize("host_git", ["none", "2.30.0"])
def test_git_provisionne_si_absent_ou_trop_ancien(tmp_path: Path, host_git: str) -> None:
    out = _install(tmp_path, WDS_INSTALL_SIMULATE_GIT=host_git)
    assert out.returncode == 0, out.stdout + out.stderr
    log = "\n".join(_log(tmp_path))
    assert "PortableGit-2.56.0.2" in log
    assert f"portablegit -y -gm2 -InstallPath={tmp_path / 'tools' / 'git'}" in log
    assert "uv-install 0.13.1" in log
    record = json.loads((tmp_path / "install.json").read_text("utf-8"))
    assert record["versions"]["git_source"] == "provisioned"
    assert record["versions"]["git"] == "2.56.0.windows.2"


def test_mise_a_jour_conserve_progress(tmp_path: Path) -> None:
    env = {"WDS_INSTALL_SIMULATE_GIT": "2.43.0"}
    assert _install(tmp_path, **env).returncode == 0
    first = json.loads((tmp_path / "install.json").read_text("utf-8"))
    progress = tmp_path / "progress.json"
    content = '{"schema_version": 1, "events": ["gardé"]}'
    progress.write_text(content, "utf-8")
    assert _install(tmp_path, **env).returncode == 0
    assert progress.read_text("utf-8") == content
    second = json.loads((tmp_path / "install.json").read_text("utf-8"))
    assert second["installed_at"] == first["installed_at"]
    assert second["run_count"] == 2 and second["updated_at"] >= first["updated_at"]
    assert "update-clone" in "\n".join(_log(tmp_path))


def test_echec_telechargement_message_francais_et_reprise(tmp_path: Path) -> None:
    out = _install(tmp_path, WDS_INSTALL_SIMULATE_GIT="none", WDS_INSTALL_SIMULATE_FAIL="download")
    assert out.returncode == 1
    text = out.stdout
    assert "Cause :" in text and "HTTPS_PROXY" in text and "UV_SYSTEM_CERTS" in text
    assert "clone" in text and "zip" in text and "Relancez" in text
    assert not (tmp_path / "install.json").exists()
    out = _install(tmp_path, WDS_INSTALL_SIMULATE_GIT="none")
    assert out.returncode == 0, out.stdout
    assert (tmp_path / "install.json").exists()


def test_reprise_apres_echec_partiel_du_sync(tmp_path: Path) -> None:
    env = {"WDS_INSTALL_SIMULATE_GIT": "2.43.0"}
    assert _install(tmp_path, WDS_INSTALL_SIMULATE_FAIL="sync", **env).returncode == 1
    assert not (tmp_path / "install.json").exists()
    assert (tmp_path / "app" / ".git").exists()
    assert _install(tmp_path, **env).returncode == 0
    log = _log(tmp_path)
    assert sum(line.startswith("clone ") for line in log) == 1
    assert "update-clone" in "\n".join(log)


def test_voie_zip(tmp_path: Path) -> None:
    out = _install(tmp_path, WDS_INSTALL_METHOD="zip", WDS_INSTALL_SIMULATE_GIT="none")
    assert out.returncode == 0, out.stdout + out.stderr
    log = "\n".join(_log(tmp_path))
    assert "portablegit" not in log and "zip-extract" in log and "archive/main.zip" in log
    record = json.loads((tmp_path / "install.json").read_text("utf-8"))
    assert record["method"] == "zip" and record["versions"]["app"] == "zip:main"
    assert (tmp_path / "app" / "pyproject.toml").exists()


def test_methode_inconnue_refusee(tmp_path: Path) -> None:
    out = _install(tmp_path, WDS_INSTALL_METHOD="ftp")
    assert out.returncode == 1 and "clone et zip" in out.stdout


def test_install_json_futur_non_modifie(tmp_path: Path) -> None:
    future = '{"schema_version": 99}'
    (tmp_path / "install.json").write_text(future, "utf-8")
    out = _install(tmp_path, WDS_INSTALL_SIMULATE_GIT="2.43.0")
    assert out.returncode == 1 and "plus récente" in out.stdout
    assert (tmp_path / "install.json").read_text("utf-8") == future


def test_proxy_pose_uv_system_certs(tmp_path: Path) -> None:
    out = _install(
        tmp_path, WDS_INSTALL_SIMULATE_GIT="2.43.0", HTTPS_PROXY="http://proxy.invalid:8080"
    )
    assert out.returncode == 0, out.stdout
    assert "Proxy détecté" in out.stdout and "UV_SYSTEM_CERTS=true" in out.stdout


def _readme_command() -> str:
    readme = (ROOT / "README.md").read_text("utf-8")
    lines = [line for line in readme.splitlines() if "DownloadData(" in line]
    assert len(lines) == 1
    return lines[0].strip()


def _paste(data: Path, after: str = "", **extra: str) -> subprocess.CompletedProcess[str]:
    """Exécute la commande du README telle quelle (voie `iex`), le script lu en `file://`."""
    raw = "https://raw.githubusercontent.com/Aliquanto3/wavedevsecops/main/install.ps1"
    command = _readme_command().replace(raw, SCRIPT.as_uri())
    env = _env(data, WDS_INSTALL_SIMULATE_TOOLS_TOML=str(ROOT / "tools.toml"), **extra)
    return _run(["-Command", f"$ErrorActionPreference = 'Continue'; {command}; {after}"], env)


def test_commande_du_readme_identique_a_l_entete() -> None:
    assert _readme_command() in SCRIPT.read_text("utf-8-sig").splitlines()[3]
    assert "$env:HTTPS_PROXY" in _readme_command()


def test_voie_iex_installe_en_simulation(tmp_path: Path) -> None:
    out = _paste(tmp_path, "'EAP=' + $ErrorActionPreference", WDS_INSTALL_SIMULATE_GIT="2.43.0")
    assert out.returncode == 0, out.stdout + out.stderr
    assert "Installation terminée" in out.stdout
    assert "raw.githubusercontent.com/Aliquanto3/wavedevsecops/main/tools.toml" in "\n".join(
        _log(tmp_path)
    )
    assert json.loads((tmp_path / "install.json").read_text("utf-8"))["versions"]["git"] == "2.43.0"
    assert "EAP=Continue" in out.stdout  # la console garde sa préférence d'erreur


def test_voie_iex_echec_ne_ferme_pas_la_console(tmp_path: Path) -> None:
    out = _paste(
        tmp_path,
        "'APRES=' + $LASTEXITCODE",
        WDS_INSTALL_SIMULATE_GIT="none",
        WDS_INSTALL_SIMULATE_FAIL="download",
    )
    assert "Cause :" in out.stdout and "Relancez" in out.stdout
    assert "APRES=1" in out.stdout
    assert not (tmp_path / "install.json").exists()


def test_installeur_uv_lu_par_iex_avec_proxy(tmp_path: Path) -> None:
    # L'installeur d'astral est simulé par un script local à bloc param, comme le vrai.
    marker = tmp_path / "marker.txt"
    fake = tmp_path / "uv install.ps1"
    fake.write_text(
        "param([switch]$NoModifyPath)\n"
        "$a = [Net.WebRequest]::DefaultWebProxy.Address.ToString()\n"
        f"[IO.File]::WriteAllText('{marker}', $a)\n",
        "utf-8",
    )
    proxy = "http://proxy.invalid:8080"
    out = _lib(
        f"$c = Get-UvInstallerCommand '{fake}' '{proxy}'; "
        "$e = [Convert]::ToBase64String([Text.Encoding]::Unicode.GetBytes($c)); "
        "Invoke-Native 'powershell.exe' @('-NoProfile', '-EncodedCommand', $e) $null; "
        "if ($c -match '-File') { 'FILE' }",
        tmp_path,
    )
    assert out.splitlines()[-1] == "0"
    assert marker.read_text("utf-8").startswith(proxy)


def test_dossier_app_etranger_non_supprime(tmp_path: Path) -> None:
    foreign = tmp_path / "app" / "mes-notes.txt"
    foreign.parent.mkdir()
    foreign.write_text("à garder", "utf-8")
    for method in ("clone", "zip"):
        out = _install(tmp_path, WDS_INSTALL_METHOD=method, WDS_INSTALL_SIMULATE_GIT="2.43.0")
        assert out.returncode == 1 and "ne contient pas l'application" in out.stdout
        assert foreign.read_text("utf-8") == "à garder"
