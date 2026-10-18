"""Moteur (AD-1, AD-6) : préparation des espaces et empreinte canonique.

Story 2.1 : setup d'un espace et empreinte. La file d'opérations, l'`epoch` et les
instantanés arrivent avec les stories suivantes de l'Epic 2.
"""

from wavedevsecops.engine.fingerprint import (
    canonical_records,
    compute_references,
    fingerprint,
    load_references,
    reference_key,
    write_references,
)
from wavedevsecops.engine.workspace import (
    PreparedWorkspace,
    WorkspaceError,
    prepare_workspace,
    resolve_git,
)

__all__ = [
    "PreparedWorkspace",
    "WorkspaceError",
    "canonical_records",
    "compute_references",
    "fingerprint",
    "load_references",
    "prepare_workspace",
    "reference_key",
    "resolve_git",
    "write_references",
]
