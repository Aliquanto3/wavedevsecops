"""Diagnostic du poste : sondes des outils requis, langue de git, proxy (FR-19, AD-16).

Lit `tools.toml` (outils) et `content/diagnostic.yaml` (textes « Que faire ? »). Une sonde
qui échoue ou dépasse son délai marque l'outil absent ou trop ancien avec sa raison, sans
exception visible. Chaque résultat peut être émis en `diagnostic_check` via `emit`.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import yaml

from wavedevsecops import gitio, toolrun
from wavedevsecops.config import Settings, get_settings, read_proxy_environment
from wavedevsecops.contracts import CheckStatus, DiagnosticCheck
from wavedevsecops.events import DIAGNOSTIC_CHECK
from wavedevsecops.registry import Tool, load_registry

Emit = Callable[[str, dict[str, Any]], None]
INSTALLER_ONLY = "install"
LOOPBACK_NAMES = ("127.0.0.1", "localhost")


def load_texts(settings: Settings | None = None) -> dict[str, Any]:
    """Textes de `content/diagnostic.yaml`."""
    path = (settings or get_settings()).content_path() / "diagnostic.yaml"
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def mask_proxy(url: str) -> str:
    """`http://user:secret@proxy.corp:3128/x` -> `http://***@proxy.corp:3128` (secret masqué)."""
    candidate = url if "://" in url else f"http://{url}"
    try:
        parts = urlsplit(candidate)
        host, port = parts.hostname or "", parts.port
    except ValueError:
        return "***"
    if not host:
        return "***"
    scheme = parts.scheme if "://" in url else ""
    credentials = "***@" if parts.username or parts.password else ""
    return f"{scheme + '://' if scheme else ''}{credentials}{host}{f':{port}' if port else ''}"


def _tool_check(tool: Tool, status: toolrun.ToolStatus, texts: dict[str, Any]) -> DiagnosticCheck:
    entry = texts["tools"].get(tool.id) or {}
    label = entry.get("label", tool.id)
    todo_source = entry.get("todo") or texts["tools"]["_python_package"]["todo"]
    if status.ok:
        source_text = texts["sources"][status.source or "environment"]
        detail = texts["tool_detail"]["ok"].format(
            label=label, version=status.version, source_text=source_text
        )
        todo = ""
    else:
        detail = texts["tool_detail"]["problem"].format(label=label, reason=status.reason)
        todo = " ".join(str(todo_source.get(status.state, "")).split())
    return DiagnosticCheck(
        check_id=f"tool.{tool.id}",
        group="tool",
        label_text=label,
        status=status.state,
        blocking=not status.ok,
        status_text=texts["statuses"][status.state],
        detail_text=detail,
        what_to_do_text=todo,
        milestone=tool.milestone,
        version=status.version,
    )


def check_git_language(git: Path, settings: Settings, texts: dict[str, Any]) -> DiagnosticCheck:
    """Ligne informative, jamais bloquante : « git parle français » ou « … anglais »."""
    block = texts["git_language"]
    lang = gitio.probe_language(git, settings).lang
    return DiagnosticCheck(
        check_id="git_language",
        group="git_language",
        label_text=block["label"],
        status="info",
        blocking=False,
        status_text=texts["statuses"]["info"],
        detail_text=block[lang],
        what_to_do_text=" ".join(str(block[f"todo_{lang}"]).split()),
    )


def check_proxy(environ: Mapping[str, str] | None, texts: dict[str, Any]) -> DiagnosticCheck:
    """Proxy en partie masqué, `NO_PROXY` pour le loopback et `UV_SYSTEM_CERTS`."""
    block = texts["proxy"]
    found = read_proxy_environment(environ)
    proxies = [
        f"{name}={mask_proxy(found[name])}"
        for name in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY")
        if name in found
    ]
    lines: list[str] = []
    todo: list[str] = []
    status: CheckStatus = "info"
    if not proxies:
        lines.append(block["none"])
    else:
        lines.append(block["present"].format(proxies=", ".join(proxies)))
        entries = {e.strip().lower() for e in found.get("NO_PROXY", "").split(",")}
        missing = [name for name in LOOPBACK_NAMES if name not in entries]
        if missing:
            status = "warn"
            lines.append(block["no_proxy_missing"].format(missing=" et ".join(missing)))
            todo.append(block["todo_no_proxy"])
        else:
            lines.append(block["no_proxy_ok"])
        certs = found.get("UV_SYSTEM_CERTS")
        if certs is None:
            lines.append(block["system_certs_unset"])
            todo.append(block["todo_certs"])
        else:
            lines.append(block["system_certs_set"].format(value=certs))
    return DiagnosticCheck(
        check_id="proxy",
        group="proxy",
        label_text=block["label"],
        status=status,
        blocking=False,
        status_text=texts["statuses"][status],
        detail_text=" ".join(lines),
        what_to_do_text=" ".join(" ".join(todo).split()),
    )


def run_diagnostic(
    settings: Settings | None = None,
    *,
    emit: Emit | None = None,
    environ: Mapping[str, str] | None = None,
    platform: str | None = None,
) -> list[DiagnosticCheck]:
    """Sonde chaque outil du registre, la langue de git et le proxy.

    Ne lève pas d'exception pour une sonde en échec (absent, trop ancien, délai dépassé).
    """
    settings = settings or get_settings()
    texts = load_texts(settings)
    options = {} if platform is None else {"platform": platform}
    checks: list[DiagnosticCheck] = []
    git_path: Path | None = None
    for tool in load_registry(settings=settings).tool:
        if tool.milestone == INSTALLER_ONLY:
            continue
        status = toolrun.resolve(tool.id, settings, **options)
        if tool.id == "git" and status.ok:
            git_path = status.path
        checks.append(_tool_check(tool, status, texts))
    if git_path is not None:
        checks.append(check_git_language(git_path, settings, texts))
    checks.append(check_proxy(environ, texts))
    if emit is not None:
        for check in checks:
            emit(DIAGNOSTIC_CHECK, check.model_dump())
    return checks
