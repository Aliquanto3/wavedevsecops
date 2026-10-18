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
from wavedevsecops.contracts import CheckPart, CheckStatus, DiagnosticCheck
from wavedevsecops.events import DIAGNOSTIC_CHECK
from wavedevsecops.registry import Tool, load_registry

Emit = Callable[[str, dict[str, Any]], None]
INSTALLER_ONLY = "install"
REQUIRED_MILESTONE = "v0.1"
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


def required_version(tool: Tool, platform: str | None = None) -> str:
    """« ≥ 2.38 » si le registre fixe un minimum, sinon la version exacte attendue."""
    if tool.min_version:
        return f"≥ {tool.min_version}"
    return tool.provisioned_for(toolrun.family(*([platform] if platform else [])))


def _tool_check(
    tool: Tool,
    status: toolrun.ToolStatus,
    texts: dict[str, Any],
    scenarios: Mapping[str, list[str]] | None = None,
    platform: str | None = None,
) -> DiagnosticCheck:
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
        usage_text=tool.usage,
        required_version=required_version(tool, platform),
        # Un outil en règle ne rend aucun scénario indisponible (AD-16).
        unavailable_scenarios=[] if status.ok else list((scenarios or {}).get(tool.id, [])),
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
    labels = texts["part_statuses"]
    found = read_proxy_environment(environ)
    proxies = [
        f"{name}={mask_proxy(found[name])}"
        for name in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY")
        if name in found
    ]

    def part(label: str, value: str, status: CheckStatus, state: str, todo: str = "") -> CheckPart:
        return CheckPart(
            label_text=label,
            value_text=value,
            status=status,
            status_text=labels[state],
            what_to_do_text=" ".join(str(todo).split()),
        )

    lines: list[str] = []
    todo: list[str] = []
    parts: list[CheckPart] = []
    status: CheckStatus = "info"
    if not proxies:
        lines.append(block["none"])
        parts.append(part(block["label_proxy"], block["none"], "info", "not_detected"))
    else:
        lines.append(block["present"].format(proxies=", ".join(proxies)))
        parts.append(
            part(block["label_proxy"], ", ".join(proxies), "ok", "detected", block["ok_proxy"])
        )
        entries = {e.strip().lower() for e in found.get("NO_PROXY", "").split(",")}
        missing = [name for name in LOOPBACK_NAMES if name not in entries]
        if missing:
            status = "warn"
            lines.append(block["no_proxy_missing"].format(missing=" et ".join(missing)))
            todo.append(block["todo_no_proxy"])
            parts.append(
                part(
                    "NO_PROXY",
                    found.get("NO_PROXY", ""),
                    "warn",
                    "to_complete",
                    block["todo_no_proxy"],
                )
            )
        else:
            lines.append(block["no_proxy_ok"])
            parts.append(part("NO_PROXY", found["NO_PROXY"], "ok", "ok", block["ok_no_proxy"]))
        certs = found.get("UV_SYSTEM_CERTS")
        if certs is None:
            lines.append(block["system_certs_unset"])
            todo.append(block["todo_certs"])
            parts.append(part("UV_SYSTEM_CERTS", "", "info", "not_set", block["todo_certs"]))
        else:
            lines.append(block["system_certs_set"].format(value=certs))
            parts.append(part("UV_SYSTEM_CERTS", certs, "ok", "ok", block["ok_certs"]))
    return DiagnosticCheck(
        check_id="proxy",
        group="proxy",
        label_text=block["label"],
        status=status,
        blocking=False,
        status_text=texts["statuses"][status],
        detail_text=" ".join(lines),
        what_to_do_text=" ".join(" ".join(todo).split()),
        parts=parts,
    )


def run_diagnostic(
    settings: Settings | None = None,
    *,
    emit: Emit | None = None,
    environ: Mapping[str, str] | None = None,
    platform: str | None = None,
    scenarios: Mapping[str, list[str]] | None = None,
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
        if tool.id == "git" and status.path is not None:
            # Trouvé, même trop ancien : la langue de git reste une information utile.
            git_path = status.path
        checks.append(_tool_check(tool, status, texts, scenarios, platform))
    if git_path is not None:
        checks.append(check_git_language(git_path, settings, texts))
    checks.append(check_proxy(environ, texts))
    if emit is not None:
        for check in checks:
            emit(DIAGNOSTIC_CHECK, check.model_dump())
    return checks


def group_by_milestone(items: list[tuple[str, str]], ui: dict[str, Any]) -> list[dict[str, Any]]:
    """Regroupe `(check_id, jalon)` par jalon, dans l'ordre d'apparition, avec leur titre."""
    groups: list[dict[str, Any]] = []
    for check_id, milestone in items:
        group = next((g for g in groups if g["key"] == milestone), None)
        if group is None:
            template = ui["group_required" if milestone == REQUIRED_MILESTONE else "group_chain"]
            group = {
                "key": milestone,
                "title_text": template.format(milestone=milestone),
                "check_ids": [],
            }
            groups.append(group)
        group["check_ids"].append(check_id)
    return groups


def build_report(checks: list[DiagnosticCheck], texts: dict[str, Any]) -> dict[str, Any]:
    """Rapport affiché par la page : lignes, groupes, synthèse, pastille et encart git (AD-2).

    Le front dessine ce que dit le serveur : aucun texte ni décompte ne se calcule côté page.
    """
    ui = texts["ui"]
    tools = [c for c in checks if c.group == "tool"]
    count = sum(1 for c in tools if c.blocking)
    proxy_todo = any(c.group == "proxy" and c.status == "warn" for c in checks)
    if count == 0 and not proxy_todo:
        summary = ui["summary_prefix"] + ui["summary_ok"].format(total=len(tools))
    else:
        if count == 0:
            head = ui["summary_tools_none"].format(total=len(tools))
        else:
            key = "summary_tools_one" if count == 1 else "summary_tools_many"
            head = ui[key].format(count=count, total=len(tools))
        summary = ui["summary_prefix"] + head + (ui["summary_proxy"] if proxy_todo else "") + "."
    groups = group_by_milestone([(c.check_id, c.milestone) for c in tools], ui)
    git = next((c for c in tools if c.check_id == "tool.git"), None)
    git_notice = None
    if git is not None and git.blocking:
        git_notice = {
            "title_text": ui["git_notice_title"],
            "cause_text": git.detail_text,
            "action_text": git.what_to_do_text,
        }
    return {
        "checks": [c.model_dump() for c in checks],
        "groups": groups,
        "summary_text": summary,
        "problem_count": count,
        "badge_text": (
            "" if not count else ui["badge_one" if count == 1 else "badge_many"].format(count=count)
        ),
        "git_notice": git_notice,
    }


def plan(settings: Settings | None = None) -> dict[str, Any]:
    """Lignes à afficher « En cours » avant la fin de la recherche, et textes de la page."""
    settings = settings or get_settings()
    texts = load_texts(settings)
    rows = []
    for tool in load_registry(settings=settings).tool:
        if tool.milestone == INSTALLER_ONLY:
            continue
        label = (texts["tools"].get(tool.id) or {}).get("label", tool.id)
        rows.append(
            {
                "check_id": f"tool.{tool.id}",
                "label_text": label,
                "usage_text": tool.usage,
                "milestone": tool.milestone,
                "required_version": required_version(tool),
            }
        )
    groups = group_by_milestone([(r["check_id"], r["milestone"]) for r in rows], texts["ui"])
    return {"rows": rows, "groups": groups, "ui": texts["ui"]}


def console_lines(checks: list[DiagnosticCheck], texts: dict[str, Any]) -> list[str]:
    """Le même diagnostic en lignes de texte, pour la console de lancement."""
    ui = texts["ui"]
    lines = [ui["console_title"]]
    for check in checks:
        if check.group == "tool":
            found = check.version or ui["console_absent"]
            lines.append(f"  {check.label_text} : {check.status_text} ({found})")
        else:
            lines.append(f"  {check.label_text} : {check.detail_text}")
        if check.what_to_do_text:
            lines.append(f"    {ui['console_todo']} {check.what_to_do_text}")
    return lines
