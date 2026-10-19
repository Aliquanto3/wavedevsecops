"""Préparation d'un espace de travail à partir d'un scénario (AD-5, AD-6, AD-7).

`<data>/workspaces/<parcours>/<scenario_id>.<mode>/` reçoit `repo/`, `origin.git/`,
`hooks/` et `run.json` (seul écrivain : le moteur). L'empreinte de fin de setup est
enregistrée dans `run.json`, et l'instantané 0 est pris dans `snapshots/0/` (AD-6), avant tout
run du pipeline.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from wavedevsecops import toolrun, wsfs
from wavedevsecops.config import Settings, get_settings
from wavedevsecops.contracts import AppError
from wavedevsecops.engine.fingerprint import fingerprint
from wavedevsecops.engine.runfile import RUN_SCHEMA_VERSION
from wavedevsecops.engine.snapshots import take_snapshot
from wavedevsecops.gitio import Git
from wavedevsecops.scenarios import LoadedScenario, run_setup
from wavedevsecops.wsfs import Layout

log = logging.getLogger("wavedevsecops")


class WorkspaceError(AppError):
    """L'espace n'a pas pu être préparé."""


@dataclass(frozen=True)
class PreparedWorkspace:
    layout: Layout
    fingerprint: str
    aliases: dict[str, str]


def resolve_git(settings: Settings | None = None) -> Path:
    """git du registre (AD-16), jamais pris au hasard dans le PATH."""
    status = toolrun.resolve("git", settings)
    if not status.ok or status.path is None:
        raise WorkspaceError(
            f"git est indisponible : {status.reason or status.state}.",
            "Ouvrez le diagnostic pour installer ou mettre à jour git.",
        )
    return status.path


def _prepare_tool_environment(tools: list[str], layout: Layout, settings: Settings) -> None:
    """Crée `cache/venv/` à l'ouverture si le scénario déclare un outil de la chaîne (AD-12).

    Hors ligne, depuis le `uv-cache` préchargé. Un échec n'empêche pas l'ouverture : le terminal
    retente à la première commande de l'outil et dit pourquoi, avec le diagnostic.
    """
    if not toolrun.needs_environment(tools, settings):
        return
    venv = toolrun.venv_dir(layout.root)
    synced = toolrun.sync_environment(layout.repo, venv, settings)
    if not synced.ok:
        log.warning(
            "Environnement d'exercice non créé pour %s : %s",
            layout.root.name,
            synced.error or synced.stderr.strip()[-300:],
        )


def prepare_workspace(
    loaded: LoadedScenario,
    track: str,
    *,
    settings: Settings | None = None,
    git_path: Path | None = None,
    replace: bool = False,
    epoch: int = 0,
) -> PreparedWorkspace:
    """Construit l'espace du scénario pour `track` ; `replace` reconstruit un espace existant.

    `epoch` : celui de l'opération qui reconstruit (« Recommencer », 4.4), écrit dans `run.json`.
    """
    settings = settings or get_settings()
    scenario = loaded.scenario
    if track not in scenario.tracks:
        raise WorkspaceError(
            f"Le scénario « {scenario.key} » ne sert pas le parcours « {track} ».",
            "Choisissez un parcours servi par ce scénario.",
        )
    layout = Layout.for_scenario(
        settings.workspaces_path(), track, scenario.scenario_id, scenario.mode
    )
    if layout.root.exists():
        if not replace:
            raise WorkspaceError(
                f"L'espace « {track}/{scenario.key} » existe déjà.",
                "Reprenez-le, ou recommencez le scénario pour le reconstruire.",
            )
        wsfs.remove_tree(layout.root)
    git = Git.for_workspace(git_path or resolve_git(settings), layout.root, settings)
    try:
        aliases = run_setup(scenario, layout, git, settings.content_path() / "exercise")
        digest = fingerprint(layout, git)
        take_snapshot(layout, git, settings, reason="setup", expected=digest)
    except BaseException:
        wsfs.remove_tree(layout.root)
        raise
    _prepare_tool_environment(scenario.tools, layout, settings)
    wsfs.write_json(layout.run_json, initial_run(loaded, track, digest, aliases, epoch=epoch))
    return PreparedWorkspace(layout, digest, aliases)


def initial_run(
    loaded: LoadedScenario,
    track: str,
    digest: str,
    aliases: dict[str, str],
    *,
    epoch: int = 0,
) -> dict[str, Any]:
    """`run.json` d'un espace à l'étape 1 : setup et « Recommencer » (4.4) l'écrivent pareil."""
    from wavedevsecops.engine import hints  # noqa: PLC0415 - hints importe le moteur

    scenario = loaded.scenario
    first_step = scenario.steps[0].step_id if scenario.steps else None
    return {
        "schema_version": RUN_SCHEMA_VERSION,
        "scenario_id": scenario.scenario_id,
        "mode": scenario.mode,
        "track": track,
        "epoch": epoch,
        "step_id": first_step,
        "hints": hints.start_step({}, first_step, hints.clock()),  # début de la 1re étape
        "content_hash": loaded.content_hash,
        "step_ids": [step.step_id for step in scenario.steps],
        "setup_fingerprint": digest,
        "aliases": aliases,
        "restoring": None,
        "restore_failed": None,
    }
