"""Résolution et lancement des outils par le registre (AD-12, AD-16).

`toolrun` résout chaque outil par `tools.toml`, jamais en lançant un nom pris dans le PATH
sans l'avoir sondé, et lance les outils avec un environnement hors ligne. Il ne lève pas
d'exception pour un outil absent ou abîmé : il en rend l'état et la raison.
"""

from __future__ import annotations

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
    )
    return env


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
            reason=f"version {installed} au lieu de {expected} (uv sync répare)",
        )
    return ToolStatus(tool.id, "ok", version=installed, source="environment")


def resolve(
    tool_id: str,
    settings: Settings | None = None,
    *,
    platform: str = sys.platform,
) -> ToolStatus:
    """Trouve `tool_id` selon sa résolution dans le registre et vérifie sa version minimale.

    Ne lève jamais pour un outil absent, trop ancien ou qui ne répond pas.
    """
    settings = settings or get_settings()
    try:
        tool = load_registry(settings=settings).get(tool_id)
    except (OSError, ValueError, KeyError) as exc:
        return ToolStatus(tool_id, "missing", reason=f"registre d'outils illisible ({exc})")
    if tool.resolution == "uv-lock":
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
) -> procs.ProcResult:
    """Lance un outil résolu par le registre, avec l'environnement hors ligne."""
    settings = settings or get_settings()
    status = resolve(tool_id, settings)
    if not status.ok or status.path is None:
        return procs.ProcResult(returncode=None, error=status.reason or f"{tool_id} indisponible")
    return procs.run(
        [status.path, *args],
        env=offline_environment(settings) if env is None else env,
        cwd=cwd,
        timeout=timeout,
    )
