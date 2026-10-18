"""Préparation d'un espace de travail à partir d'un scénario (AD-5, AD-6, AD-7).

`<data>/workspaces/<parcours>/<scenario_id>.<mode>/` reçoit `repo/`, `origin.git/`,
`hooks/` et `run.json` (seul écrivain : le moteur). L'empreinte de fin de setup est
enregistrée dans `run.json`, et l'instantané 0 est pris dans `snapshots/0/` (AD-6), avant tout
run du pipeline.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from wavedevsecops import toolrun, wsfs
from wavedevsecops.config import Settings, get_settings
from wavedevsecops.contracts import AppError
from wavedevsecops.engine.fingerprint import fingerprint
from wavedevsecops.engine.runfile import RUN_SCHEMA_VERSION
from wavedevsecops.engine.snapshots import take_snapshot
from wavedevsecops.gitio import Git
from wavedevsecops.scenarios import LoadedScenario, run_setup
from wavedevsecops.wsfs import Layout


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


def prepare_workspace(
    loaded: LoadedScenario,
    track: str,
    *,
    settings: Settings | None = None,
    git_path: Path | None = None,
    replace: bool = False,
) -> PreparedWorkspace:
    """Construit l'espace du scénario pour `track` ; `replace` reconstruit un espace existant."""
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
    wsfs.write_json(
        layout.run_json,
        {
            "schema_version": RUN_SCHEMA_VERSION,
            "scenario_id": scenario.scenario_id,
            "mode": scenario.mode,
            "track": track,
            "epoch": 0,
            "step_id": scenario.steps[0].step_id if scenario.steps else None,
            "content_hash": loaded.content_hash,
            "setup_fingerprint": digest,
            "aliases": aliases,
            "restoring": None,
            "restore_failed": None,
        },
    )
    return PreparedWorkspace(layout, digest, aliases)
