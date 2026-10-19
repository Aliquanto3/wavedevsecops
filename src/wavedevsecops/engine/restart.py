"""Recommencer un scénario sans perdre son score (FR-10, AD-6, AD-14, AD-20) : `restart {}`.

L'opération s'exécute dans la file, en état `restoring` (surveillant arrêté, `epoch` incrémenté).
Dans l'ordre :

1. `hints.settle` : la lecture du dernier indice devient un fait avant que `run.json` soit refait ;
2. `run.json` repart de l'étape 1 (paliers, essais, réponses, quiz et `restore_failed` à zéro) ;
3. l'espace revient à l'instantané 0, vérifié contre son empreinte (AD-6) ; si l'instantané est
   absent, si la restauration échoue ou si le `content_hash` du scénario a changé, l'espace est
   supprimé puis reconstruit par son setup, et son empreinte comparée à celle de
   `content/fingerprints.json` ;
4. le fait `scenario_restarted` s'ajoute à `progress.json` : les faits du premier passage (score
   du premier coup, indices) ne sont ni modifiés ni retirés.

Si la reconstruction échoue aussi, l'erreur est publiée (`app_error`) et l'espace garde
`restore_failed` : « Recommencer » reste la seule action d'écriture admise.
"""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from wavedevsecops.contracts import AppError
from wavedevsecops.engine import hints
from wavedevsecops.engine.fingerprint import load_references, reference_key
from wavedevsecops.engine.intents import INTENTS, Intent, register_intent
from wavedevsecops.engine.manager import parse_workspace_id
from wavedevsecops.engine.operations import (
    RESTART_INTENT,
    OpContext,
    Operation,
    WorkspaceEngine,
)
from wavedevsecops.engine.runfile import load_run, save_run
from wavedevsecops.engine.snapshots import Sleep, get_snapshot, restore_snapshot
from wavedevsecops.engine.workspace import initial_run, prepare_workspace, resolve_git
from wavedevsecops.gitio import Git
from wavedevsecops.scenarios import LoadedScenario, ScenarioError, load_scenario

log = logging.getLogger("wavedevsecops")

RESTARTING_TEXT = "Remise à zéro du scénario en cours."
FAILED_ACTION = "Voir le diagnostic, puis recommencez le scénario."
MISMATCH_TEXT = (
    "L'espace reconstruit ne correspond pas à l'état de référence du scénario : il n'est pas "
    "fiable."
)
RESTARTED_FACT = "scenario_restarted"


class Restart(BaseModel):
    pass


def _load(ctx: OpContext, scenario_id: str, mode: str) -> LoadedScenario:
    path = ctx.settings.scenarios_path() / f"{scenario_id}.{mode}.yaml"
    try:
        return load_scenario(path, ctx.settings)
    except (ScenarioError, OSError, UnicodeDecodeError):
        log.exception("Scénario de %s illisible pendant Recommencer", ctx.workspace_id)
        raise AppError(
            "Le scénario de cet espace n'est plus disponible ou son contenu est illisible.",
            FAILED_ACTION,
        ) from None


def _by_snapshot(
    ctx: OpContext, git: Git, loaded: LoadedScenario, track: str, run: dict[str, Any], sleep: Sleep
) -> bool:
    """Revient à l'instantané 0 ; faux (sans rien lever) s'il faut reconstruire à la place.

    `run.json` est refait avant la copie : un arrêt en plein milieu est repris par la reprise de
    restauration (4.3) sur un `run.json` déjà remis à zéro.
    """
    snapshot = get_snapshot(ctx.layout, 0)
    if snapshot is None or run.get("content_hash") != loaded.content_hash:
        return False
    aliases = run.get("aliases") if isinstance(run.get("aliases"), dict) else {}
    save_run(ctx.layout, initial_run(loaded, track, snapshot.fingerprint, aliases, epoch=ctx.epoch))
    try:
        restore_snapshot(ctx.layout, git, ctx.settings, 0, epoch=ctx.epoch, sleep=sleep)
    except Exception:  # noqa: BLE001 - RestoreFailed ou erreur imprévue : on reconstruit
        log.warning("Instantané 0 non rétabli dans %s : reconstruction", ctx.workspace_id)
        return False
    return True


def _rebuild(ctx: OpContext, git_path: Path, loaded: LoadedScenario, track: str) -> None:
    """Supprime l'espace, le reconstruit par son setup et compare son empreinte à la référence."""
    prepared = prepare_workspace(
        loaded, track, settings=ctx.settings, git_path=git_path, replace=True
    )
    key = reference_key(track, loaded.scenario.key)
    try:
        expected = load_references(ctx.settings).get(key)
    except (OSError, ValueError, UnicodeDecodeError):
        log.exception("fingerprints.json illisible")
        expected = None
    if expected is not None and prepared.fingerprint != expected:
        run = load_run(ctx.layout)
        save_run(
            ctx.layout,
            {**run, "restore_failed": {"snapshot_id": None, "reason_text": MISMATCH_TEXT}},
        )
        raise AppError(MISMATCH_TEXT, FAILED_ACTION)


def restart_operation(git_path: Path, *, sleep: Sleep = time.sleep) -> Operation:
    """Opération « Recommencer » (état `restoring`) : admise même après `restore_failed`."""

    def body(ctx: OpContext) -> int:
        hints.settle(ctx)  # le palier en lecture devient un fait avant de refaire run.json
        # L'identité de l'espace vient de son identifiant : un `run.json` illisible se reconstruit.
        track, scenario_id, mode = parse_workspace_id(ctx.workspace_id)
        try:
            run: dict[str, Any] = load_run(ctx.layout)
        except AppError:
            run = {}
        loaded = _load(ctx, scenario_id, mode)
        git = Git.for_workspace(git_path, ctx.layout.root, ctx.settings)
        if not _by_snapshot(ctx, git, loaded, track, run, sleep):
            try:
                _rebuild(ctx, git_path, loaded, track)
            except AppError as error:
                raise AppError(error.cause_text, FAILED_ACTION) from error
        ctx.set_rest_state("idle")
        ctx.submit_facts(
            [
                {
                    "kind": RESTARTED_FACT,
                    "track": track,
                    "scenario_id": loaded.scenario.scenario_id,
                    "mode": loaded.scenario.mode,
                }
            ]
        )
        return 0

    return Operation(
        RESTART_INTENT,
        body,
        state="restoring",
        validate=False,
        reason_text=RESTARTING_TEXT,
    )


def build_restart(engine: WorkspaceEngine, body: Restart) -> Operation:
    return restart_operation(engine.git_path or resolve_git(engine.settings))


def register_intents() -> None:
    """Enregistre `restart` (idempotent)."""
    if RESTART_INTENT not in INTENTS:
        register_intent(Intent(RESTART_INTENT, Restart, build_restart))
