"""Moteur (AD-1, AD-6) : files d'opérations, `epoch`, préparation des espaces, empreinte.

Story 2.1 : setup d'un espace et empreinte. Story 2.2 : file d'opérations par espace
(`operations`), registre des intentions (`intents`), espaces actifs et veille (`manager`),
surveillant de l'arbre (`watcher`), `run.json` versionné (`runfile`). Story 4.3 :
instantanés et restauration exacte (`snapshots`).
"""

from wavedevsecops.engine.fingerprint import (
    canonical_records,
    compute_references,
    fingerprint,
    load_references,
    reference_key,
    write_references,
)
from wavedevsecops.engine.intents import (
    INTENTS,
    Intent,
    InvalidIntent,
    UnknownIntent,
    build_operation,
    register_intent,
    unregister_intent,
)
from wavedevsecops.engine.manager import (
    WorkspaceManager,
    WorkspaceNotFound,
    parse_workspace_id,
    workspace_id_for,
)
from wavedevsecops.engine.operations import (
    OpContext,
    Operation,
    OperationRefused,
    OpResult,
    Projection,
    StaleOperation,
    StepOutcome,
    WorkspaceEngine,
)
from wavedevsecops.engine.runfile import RUN_SCHEMA_VERSION, RunFileError, load_run, save_run
from wavedevsecops.engine.steps import StepRunner
from wavedevsecops.engine.snapshots import (
    RestoreFailed,
    Snapshot,
    SnapshotError,
    get_snapshot,
    latest_snapshot,
    list_snapshots,
    prune_snapshots,
    restore_operation,
    restore_snapshot,
    resume_restore,
    take_snapshot,
)
from wavedevsecops.engine.workspace import (
    PreparedWorkspace,
    WorkspaceError,
    prepare_workspace,
    resolve_git,
)

__all__ = [
    "INTENTS",
    "RUN_SCHEMA_VERSION",
    "Intent",
    "InvalidIntent",
    "OpContext",
    "OpResult",
    "Operation",
    "OperationRefused",
    "PreparedWorkspace",
    "Projection",
    "RunFileError",
    "StaleOperation",
    "StepOutcome",
    "StepRunner",
    "UnknownIntent",
    "WorkspaceEngine",
    "WorkspaceManager",
    "WorkspaceNotFound",
    "WorkspaceError",
    "canonical_records",
    "compute_references",
    "fingerprint",
    "build_operation",
    "load_references",
    "load_run",
    "parse_workspace_id",
    "register_intent",
    "save_run",
    "unregister_intent",
    "workspace_id_for",
    "prepare_workspace",
    "reference_key",
    "resolve_git",
    "write_references",
    "RestoreFailed",
    "Snapshot",
    "SnapshotError",
    "get_snapshot",
    "latest_snapshot",
    "list_snapshots",
    "prune_snapshots",
    "restore_operation",
    "restore_snapshot",
    "resume_restore",
    "take_snapshot",
]
