"""`run.json` d'un espace : un seul écrivain (le moteur), versionné (AD-5, AD-20).

Au chargement, les migrations numérotées s'appliquent en ajout seulement ; un fichier d'une
version future n'est pas modifié et donne une erreur claire.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

from wavedevsecops import wsfs
from wavedevsecops.contracts import AppError
from wavedevsecops.wsfs import Layout

RUN_SCHEMA_VERSION = 1

MIGRATIONS: dict[int, Callable[[dict[str, Any]], dict[str, Any]]] = {}
"""`MIGRATIONS[n]` fait passer un `run.json` de la version `n` à `n + 1`."""


class RunFileError(AppError):
    """`run.json` absent, illisible ou d'une version future."""


def load_run(layout: Layout) -> dict[str, Any]:
    """Lit `run.json` et le met à la version courante (en mémoire)."""
    path = layout.run_json
    try:
        data = json.loads(path.read_bytes().decode("utf-8"))
    except OSError, UnicodeDecodeError, json.JSONDecodeError:
        raise RunFileError(
            "Le fichier d'état de cet espace (run.json) est absent ou illisible.",
            "Recommencez le scénario pour reconstruire l'espace.",
        ) from None
    version = data.get("schema_version") if isinstance(data, dict) else None
    if not isinstance(version, int) or version < 1:
        raise RunFileError(
            "Le fichier d'état de cet espace (run.json) n'a pas de version valide.",
            "Recommencez le scénario pour reconstruire l'espace.",
        )
    if version > RUN_SCHEMA_VERSION:
        raise RunFileError(
            "Cet espace a été créé par une version plus récente de WaveDevSecOps.",
            "Mettez WaveDevSecOps à jour pour le rouvrir.",
        )
    while version < RUN_SCHEMA_VERSION:
        data = MIGRATIONS[version](data)
        version += 1
        data["schema_version"] = version
    return data


def save_run(layout: Layout, data: dict[str, Any]) -> None:
    """Écrit `run.json` (atomique, JSON trié, LF) à la version courante."""
    wsfs.write_json(layout.run_json, {**data, "schema_version": RUN_SCHEMA_VERSION})
