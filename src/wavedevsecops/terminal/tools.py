"""Outils de la chaîne tapés dans le terminal : ruff et pytest (story 7.2, AD-4, AD-10, AD-12).

L'outil tourne par `toolrun`, dans l'environnement d'exercice de l'espace (`cache/venv/`, hors
ligne). Sa sortie humaine est émise telle quelle, en un bloc `tool-output` étiqueté à son nom.
Les liens fichier:ligne de ce bloc ne viennent jamais du texte : une seconde exécution, en mode
machine, du même outil sur le même arbre dit quels fichiers et quelles lignes comptent
(`toolrun.findings`) ; seuls ces passages deviennent des liens vers la vue Code (AD-10).
"""

from __future__ import annotations

import logging
import re

from wavedevsecops import toolrun
from wavedevsecops.contracts import element_id
from wavedevsecops.engine import OpContext
from wavedevsecops.terminal.allowlist import Allowlist
from wavedevsecops.terminal.parse import ToolCommand
from wavedevsecops.toolrun import findings as machine

log = logging.getLogger("wavedevsecops")

EXIT_INTERRUPTED = 130
EXIT_TIMEOUT = 124
EXIT_UNAVAILABLE = 127

_FILE_LINE = re.compile(r"(?<![\w./\\-])(?P<path>[\w./\\-]+?):(?P<line>\d+)(?!\d)")


def _utf16(text: str, index: int) -> int:
    """Position en unités UTF-16 (celles de `String.prototype.slice` côté front)."""
    prefix = text[:index]
    return index if prefix.isascii() else len(prefix.encode("utf-16-le")) // 2


def link_spans(text: str, found: machine.Findings, repo_files: set[str]) -> list[dict]:
    """Passages `fichier:ligne` du texte que l'exécution machine désigne (AD-10, AD-2)."""
    spans: list[dict] = []
    for match in _FILE_LINE.finditer(text):
        path = match["path"].replace("\\", "/").removeprefix("./")
        if path not in repo_files or not found.covers(path, int(match["line"])):
            continue
        spans.append(
            {
                "start": _utf16(text, match.start()),
                "end": _utf16(text, match.end()),
                "text": match.group(0),
                "element_id": element_id("path", "worktree", path),
            }
        )
    return spans


def _existing(found: machine.Findings, repo) -> set[str]:  # noqa: ANN001 - Path du dépôt
    return {path for path in found.lines if (repo / path).is_file()}


def _prepare_environment(ctx: OpContext, command: ToolCommand, allow: Allowlist) -> bool:
    """Garantit `cache/venv/` ; faux (et message) si l'outil reste inutilisable."""
    venv = toolrun.venv_dir(ctx.layout.root)
    if toolrun.venv_python(venv) is None:
        # Secours : l'ouverture de l'espace crée normalement l'environnement (hors ligne).
        synced = toolrun.sync_environment(
            ctx.layout.repo,
            venv,
            ctx.settings,
            on_start=lambda handle: ctx.on_interrupt(handle.terminate),
        )
        if ctx.interrupted:
            ctx.output(allow.message("interrupted"), "app")
            return False
        if not synced.ok:
            lines = synced.stderr.strip().splitlines()
            reason = synced.error or (lines[-1] if lines else "uv sync a échoué")
            ctx.output(allow.message("tool_env_failed", reason=reason), "app")
            return False
    return True


def run(ctx: OpContext, command: ToolCommand, allow: Allowlist) -> int:
    """Lance l'outil dans `repo/`, affiche sa sortie verbatim puis soumet `evidence_seen`."""
    settings = ctx.settings
    venv = toolrun.venv_dir(ctx.layout.root)
    repo = ctx.layout.repo
    if not _prepare_environment(ctx, command, allow):
        return EXIT_INTERRUPTED if ctx.interrupted else EXIT_UNAVAILABLE
    try:
        handle = toolrun.spawn_tool(
            command.name,
            command.args,
            cwd=repo,
            venv=venv,
            timeout=settings.tool_timeout_s,
            settings=settings,
        )
    except toolrun.ToolUnavailable as exc:
        reason = exc.status.reason or exc.status.state
        ctx.output(allow.message("tool_unavailable", tool=command.name, reason=reason), "app")
        return EXIT_UNAVAILABLE
    except OSError as exc:
        reason = f"le processus n'a pas démarré ({type(exc).__name__})"
        ctx.output(allow.message("tool_unavailable", tool=command.name, reason=reason), "app")
        return EXIT_UNAVAILABLE
    ctx.on_interrupt(handle.terminate)
    result = toolrun.collect(handle)
    text = result.stdout + result.stderr
    killed = handle.timed_out or handle.interrupted or ctx.interrupted
    code = result.returncode

    spans: list[dict] = []
    notice = ""
    if not killed and code not in (None, 0):
        # Constats de l'exécution machine du même outil, sur le même arbre (AD-10).
        found = machine.collect(
            command.name,
            command.args,
            repo=repo,
            venv=venv,
            cache=ctx.layout.cache,
            settings=settings,
            timeout=settings.tool_timeout_s,
        )
        if found.error:
            log.warning("Sortie machine de %s : %s", command.name, found.error)
            notice = allow.message("tool_machine_failed", reason=found.error)
        else:
            spans = link_spans(text, found, _existing(found, repo))
    if text:
        ctx.output(text, "stdout", tool=command.name, spans=spans)
    if notice:
        ctx.output(notice, "app")

    if killed:
        if handle.timed_out:
            ctx.output(allow.message("timeout", seconds=f"{settings.tool_timeout_s:g}"), "app")
            return EXIT_TIMEOUT
        ctx.output(allow.message("interrupted"), "app")
        return EXIT_INTERRUPTED
    if code:
        ctx.output(allow.message("exit_code", code=code), "exit")
    if text:
        # La preuve de la barrière s'est affichée (AD-14) ; le premier passage seul compte.
        ctx.submit_evidence(command.barrier_id)
    return code if code is not None else EXIT_INTERRUPTED
