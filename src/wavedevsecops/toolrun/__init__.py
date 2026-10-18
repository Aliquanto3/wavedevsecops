"""Résolution et lancement des outils par le registre (AD-12, AD-16).

`toolrun` résout chaque outil par `tools.toml`, jamais en lançant un nom pris dans le PATH
sans l'avoir sondé, et lance les outils avec un environnement hors ligne. Il ne lève pas
d'exception pour un outil absent ou abîmé : il en rend l'état et la raison.
"""

from __future__ import annotations

import re
import shutil
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from importlib import metadata
from pathlib import Path
from typing import Literal

from wavedevsecops import procs
from wavedevsecops.config import Settings, get_settings, inherited_environment
from wavedevsecops.registry import (
    Family,
    Tool,
    at_least,
    extract_version,
    load_registry,
)

State = Literal["ok", "missing", "too_old", "mismatch"]
Source = Literal["host", "provisioned", "environment"]

PROXY_NAMES = ("http_proxy", "https_proxy", "all_proxy")
LOOPBACK_NO_PROXY = "127.0.0.1,localhost"
NETGUARD_VARIABLE = "WDS_NETGUARD"
NETGUARD_MODULE = "_wds_netguard"

# Garde réseau posée dans chaque environnement d'exercice (AD-12, AD-13) : un `.pth` l'importe
# au démarrage de tout Python du venv (outils, tests du gabarit). Quand `WDS_NETGUARD=1` (posé
# par `offline_environment`), un hook d'audit refuse toute connexion hors loopback, même sans
# proxy. `llmrun` lancera le code d'exercice sans cette variable : lui seul peut sortir.
NETGUARD_SOURCE = '''"""Garde réseau de WaveDevSecOps : connexion hors loopback refusée (AD-12)."""
import os
import sys

_LOOPBACK = ("localhost", "::1", "0:0:0:0:0:0:0:1")


def _wds_netguard(event, args):
    if event != "socket.connect" or len(args) < 2 or not isinstance(args[1], tuple):
        return
    host = str(args[1][0]).lower().removeprefix("::ffff:")
    if host.startswith("127.") or host in _LOOPBACK:
        return
    raise PermissionError(
        "WaveDevSecOps : connexion vers " + host + " refusée, l'exercice tourne hors ligne"
    )


if os.environ.get("WDS_NETGUARD") == "1":
    sys.addaudithook(_wds_netguard)
'''


@dataclass(frozen=True)
class ToolStatus:
    """État d'un outil requis : trouvé et assez récent, ou raison de son absence."""

    tool_id: str
    state: State
    version: str = ""
    path: Path | None = None
    source: Source | None = None
    reason: str = ""

    @property
    def ok(self) -> bool:
        return self.state == "ok"


def family(platform: str = sys.platform) -> Family:
    return "windows" if platform == "win32" else "posix"


def probe_environment() -> dict[str, str]:
    """Environnement d'une sonde de version : sortie stable, aucun proxy, aucune saisie."""
    env = {k: v for k, v in inherited_environment().items() if k.lower() not in PROXY_NAMES}
    env.update(LC_ALL="C", LANGUAGE="", GIT_TERMINAL_PROMPT="0", NO_COLOR="1")
    return env


def offline_environment(settings: Settings | None = None) -> dict[str, str]:
    """Environnement hors ligne des outils lancés par l'application (AD-12)."""
    settings = settings or get_settings()
    data = settings.resolved_data_dir()
    cache = data / "cache"
    env = {k: v for k, v in inherited_environment().items() if k.lower() not in PROXY_NAMES}
    env.update(
        UV_OFFLINE="1",
        UV_CACHE_DIR=str(data / "uv-cache"),
        UV_PYTHON_DOWNLOADS="never",
        UV_PYTHON_PREFERENCE="only-managed",
        PIP_NO_INDEX="1",
        NO_PROXY=LOOPBACK_NO_PROXY,
        no_proxy=LOOPBACK_NO_PROXY,
        PYTHONUTF8="1",
        PYTHONDONTWRITEBYTECODE="1",
        RUFF_CACHE_DIR=str(cache / "ruff"),
        COVERAGE_FILE=str(cache / "coverage"),
        PRE_COMMIT_HOME=str(cache / "pre-commit"),
        PYTEST_ADDOPTS="-p no:cacheprovider",
        UV_PYTHON_INSTALL_DIR=str(python_install_dir(settings)),
        UV_NO_PROGRESS="1",
    )
    env[NETGUARD_VARIABLE] = "1"
    return env


def python_install_dir(settings: Settings | None = None) -> Path:
    """Interpréteurs Python gérés par uv, préchargés avec le cache par l'installeur (AD-12)."""
    return (settings or get_settings()).resolved_data_dir() / "uv-cache" / "python"


def venv_dir(workspace_root: Path) -> Path:
    """Environnement d'exercice d'un espace : `cache/venv/`, hors instantanés (AD-5, AD-12)."""
    return workspace_root / "cache" / "venv"


def _host_candidate(tool: Tool, platform: str, timeout: float) -> tuple[Path | None, str]:
    """Exécutable du PATH pour `tool`, ou (None, raison). Sous macOS : `xcode-select` d'abord."""
    found = shutil.which(tool.id)
    if found is None:
        return None, f"{tool.id} est introuvable sur le poste"
    path = Path(found)
    if platform == "darwin" and tool.id == "git" and path.as_posix() == "/usr/bin/git":
        # /usr/bin/git ouvre la fenêtre d'installation des outils Xcode s'ils manquent (AD-15).
        check = procs.run(["xcode-select", "-p"], env=probe_environment(), timeout=timeout)
        if not check.ok:
            return None, "les outils en ligne de commande Xcode ne sont pas installés"
    return path, ""


def _provisioned_candidates(tool: Tool, settings: Settings, platform: str) -> list[Path]:
    root = settings.resolved_data_dir() / "tools"
    return [root / rel for rel in tool.paths.get(family(platform), [])]


def _probe(tool: Tool, path: Path, timeout: float) -> tuple[tuple[int, ...] | None, str]:
    result = procs.run([path, *tool.probe], env=probe_environment(), timeout=timeout)
    if result.error:
        return None, f"impossible de lancer {path.name} ({result.error})"
    if result.timed_out:
        return None, f"{path.name} n'a pas répondu en {timeout:g} s"
    version = extract_version(tool, result.stdout + "\n" + result.stderr)
    if version is None:
        return None, f"la version de {path.name} est illisible"
    return version, ""


def site_packages(venv: Path, platform: str = sys.platform) -> Path | None:
    """Dossier `site-packages` d'un environnement virtuel, ou None s'il n'existe pas."""
    if family(platform) == "windows":
        found = venv / "Lib" / "site-packages"
        return found if found.is_dir() else None
    return next((p for p in sorted(venv.glob("lib/python*/site-packages")) if p.is_dir()), None)


def _normalize(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def installed_version(venv: Path, package: str, platform: str = sys.platform) -> str | None:
    """Version de `package` installée dans `venv`, lue dans son `.dist-info` sans le lancer."""
    site = site_packages(venv, platform)
    if site is None:
        return None
    wanted = _normalize(package)
    for info in site.glob("*.dist-info"):
        name, _, version = info.name.removesuffix(".dist-info").rpartition("-")
        if name and _normalize(name) == wanted:
            return version
    return None


def _venv_executable(venv: Path, tool_id: str, platform: str) -> Path | None:
    if family(platform) == "windows":
        candidate = venv / "Scripts" / f"{tool_id}.exe"
    else:
        candidate = venv / "bin" / tool_id
    return candidate if candidate.is_file() else None


def _resolve_in_venv(tool: Tool, venv: Path, platform: str) -> ToolStatus:
    """Outil de la chaîne dans l'environnement d'exercice, comparé au `uv.lock` (AD-16)."""
    expected = tool.provisioned_for(family(platform))
    installed = installed_version(venv, tool.id, platform)
    if installed is None:
        return ToolStatus(
            tool.id,
            "missing",
            reason=f"{tool.id} n'est pas dans l'environnement de l'exercice (uv sync)",
        )
    if installed != expected:
        return ToolStatus(
            tool.id,
            "mismatch",
            version=installed,
            source="environment",
            reason=f"environnement abîmé : version {installed} au lieu de {expected} (uv sync)",
        )
    path = _venv_executable(venv, tool.id, platform)
    return ToolStatus(tool.id, "ok", version=installed, path=path, source="environment")


def _resolve_python_package(tool: Tool) -> ToolStatus:
    expected = tool.provisioned_for("posix")
    try:
        installed = metadata.version(tool.id)
    except metadata.PackageNotFoundError:
        return ToolStatus(tool.id, "missing", reason=f"{tool.id} n'est pas installé (uv sync)")
    if installed != expected:
        return ToolStatus(
            tool.id,
            "mismatch",
            version=installed,
            source="environment",
            reason=f"environnement abîmé : version {installed} au lieu de {expected} (uv sync)",
        )
    return ToolStatus(tool.id, "ok", version=installed, source="environment")


def resolve(
    tool_id: str,
    settings: Settings | None = None,
    *,
    platform: str = sys.platform,
    venv: Path | None = None,
) -> ToolStatus:
    """Trouve `tool_id` selon sa résolution dans le registre et vérifie sa version minimale.

    Un outil de la chaîne (`uv-lock`) est cherché dans `venv` (l'environnement d'exercice),
    sinon dans l'environnement de l'application. Ne lève jamais pour un outil absent, trop
    ancien ou qui ne répond pas.
    """
    settings = settings or get_settings()
    try:
        tool = load_registry(settings=settings).get(tool_id)
    except (OSError, ValueError, KeyError) as exc:
        return ToolStatus(tool_id, "missing", reason=f"registre d'outils illisible ({exc})")
    if tool.resolution == "uv-lock":
        if venv is not None:
            return _resolve_in_venv(tool, venv, platform)
        return _resolve_python_package(tool)

    timeout = settings.probe_timeout_s
    candidates: list[tuple[Path, Source]] = []
    reasons: list[str] = []
    if tool.resolution in {"host", "host-or-provisioned"}:
        host, why = _host_candidate(tool, platform, timeout)
        if host is None:
            reasons.append(why)
        else:
            candidates.append((host, "host"))
    if tool.resolution in {"provisioned", "host-or-provisioned"}:
        existing = [p for p in _provisioned_candidates(tool, settings, platform) if p.is_file()]
        candidates += [(p, "provisioned") for p in existing]
        if not existing:
            reasons.append(f"{tool.id} n'est pas installé dans le dossier tools/ de l'application")

    too_old: ToolStatus | None = None
    for path, source in candidates:
        version, why = _probe(tool, path, timeout)
        if version is None:
            reasons.append(why)
            continue
        text = ".".join(str(part) for part in version)
        if tool.min_version and not at_least(version, tool.min_version):
            too_old = too_old or ToolStatus(
                tool.id,
                "too_old",
                version=text,
                path=path,
                source=source,
                reason=f"version {text}, {tool.min_version} ou plus est requise",
            )
            continue
        return ToolStatus(tool.id, "ok", version=text, path=path, source=source)
    return too_old or ToolStatus(tool.id, "missing", reason=" ; ".join(reasons))


def run_tool(
    tool_id: str,
    args: Sequence[str],
    *,
    cwd: Path | None = None,
    timeout: float = 60.0,
    env: Mapping[str, str] | None = None,
    settings: Settings | None = None,
    venv: Path | None = None,
) -> procs.ProcResult:
    """Lance un outil résolu par le registre, avec l'environnement hors ligne.

    Les outils de la chaîne sont lancés depuis `venv`, l'environnement d'exercice.
    """
    settings = settings or get_settings()
    status = resolve(tool_id, settings, venv=venv)
    if not status.ok or status.path is None:
        return procs.ProcResult(returncode=None, error=status.reason or f"{tool_id} indisponible")
    return procs.run(
        [status.path, *args],
        env=offline_environment(settings) if env is None else env,
        cwd=cwd,
        timeout=timeout,
    )


def install_network_guard(venv: Path, platform: str = sys.platform) -> bool:
    """Pose la garde réseau dans `venv` (module et `.pth`) ; False si `site-packages` manque."""
    site = site_packages(venv, platform)
    if site is None:
        return False
    (site / f"{NETGUARD_MODULE}.py").write_text(NETGUARD_SOURCE, encoding="utf-8")
    (site / f"{NETGUARD_MODULE}.pth").write_text(f"import {NETGUARD_MODULE}\n", encoding="utf-8")
    return True


def sync_environment(
    project: Path,
    venv: Path,
    settings: Settings | None = None,
    *,
    timeout: float = 600.0,
) -> procs.ProcResult:
    """Crée ou met à jour `venv` par `uv sync --offline --frozen` depuis le `uv.lock` de `project`.

    Aucun accès réseau : tout vient du `uv-cache` préchargé à l'installation (AD-12), uv étant
    résolu par le registre. La garde réseau est posée dans l'environnement créé.
    """
    settings = settings or get_settings()
    uv = resolve("uv", settings)
    if not uv.ok or uv.path is None:
        return procs.ProcResult(returncode=None, error=uv.reason or "uv indisponible")
    env = offline_environment(settings)
    env["UV_PROJECT_ENVIRONMENT"] = str(venv)
    argv = [uv.path, "sync", "--offline", "--frozen", "--project", str(project)]
    result = procs.run(argv, env=env, cwd=project, timeout=timeout)
    if result.ok and not install_network_guard(venv):
        return procs.ProcResult(
            returncode=None,
            stdout=result.stdout,
            stderr=result.stderr,
            error=f"environnement incomplet : site-packages introuvable dans {venv}",
        )
    return result
