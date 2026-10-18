"""`progress.json` : suivi de l'apprenant, écrit par ce module seul (AD-14).

Le fichier de base porte `schema_version`, l'horodatage d'installation (lu dans `install.json`
s'il existe) et celui du premier lancement. Les faits du premier passage (`facts`, ajout
seulement) et les états dérivés sont dans `progress.facts`.
"""

from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path

from wavedevsecops.contracts import AppError

SCHEMA_VERSION = 1
FILENAME = "progress.json"


class FutureSchemaError(AppError):
    """Fichier de données écrit par une version plus récente de l'application."""


class UnreadableDataError(AppError):
    """Fichier de données illisible ou invalide."""


def write_json_atomic(path: Path, data: dict) -> None:
    """Écriture atomique (temporaire puis renommage), UTF-8, LF, JSON trié."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    text = json.dumps(data, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    with open(tmp, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(tmp, path)


def _read_json(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise UnreadableDataError(
            f"Le fichier {path.name} est illisible.",
            f"Vérifiez-le dans le dossier {path.parent}, ou renommez-le pour repartir de zéro.",
        ) from exc
    if not isinstance(data, dict):
        raise UnreadableDataError(
            f"Le fichier {path.name} n'a pas le format attendu.",
            f"Vérifiez-le dans le dossier {path.parent}, ou renommez-le pour repartir de zéro.",
        )
    return data


def _installed_at(data_dir: Path) -> str | None:
    """Horodatage d'installation écrit par l'installeur ; `None` s'il est absent."""
    install = data_dir / "install.json"
    if not install.exists():
        return None
    value = _read_json(install).get("installed_at")
    return value if isinstance(value, str) else None


def ensure_progress(data_dir: Path, now: datetime) -> dict:
    """Crée `progress.json` au premier lancement ; sinon le charge sans le modifier.

    Un fichier d'une version future n'est jamais modifié : `FutureSchemaError`.
    """
    path = data_dir / FILENAME
    if path.exists():
        data = _read_json(path)
        version = data.get("schema_version")
        if not isinstance(version, int):
            raise UnreadableDataError(
                f"Le fichier {FILENAME} n'indique pas sa version.",
                f"Vérifiez-le dans le dossier {data_dir}, ou renommez-le pour repartir de zéro.",
            )
        if version > SCHEMA_VERSION:
            raise FutureSchemaError(
                f"Le fichier {FILENAME} a été écrit par une version plus récente de "
                "WaveDevSecOps ; il n'a pas été modifié.",
                "Mettez WaveDevSecOps à jour, puis relancez-le.",
            )
        return data
    data = {
        "schema_version": SCHEMA_VERSION,
        "installed_at": _installed_at(data_dir),
        "first_launch_at": now.isoformat(timespec="seconds"),
    }
    write_json_atomic(path, data)
    return data
