"""Réglages de l'application : un seul objet `Settings`, seul lecteur de l'environnement.

Module feuille (AD-1) : il n'importe rien du projet. Aucun autre module ne lit
`os.environ` ni `os.getenv` (convention « Réglages » du spine) ; ils reçoivent un
`Settings`, ou appellent `get_settings()`.

Chaque champ peut être fixé par une variable d'environnement `WDS_<NOM_DU_CHAMP>`
(par exemple `WDS_DATA_DIR`).
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from functools import cache
from pathlib import Path

from platformdirs import user_data_dir
from pydantic import BaseModel, ConfigDict

ENV_PREFIX = "WDS_"


class Settings(BaseModel):
    """Réglages de WaveDevSecOps. Les stories suivantes y ajoutent leurs champs."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    data_dir: Path | None = None
    """Dossier des données utilisateur ; `None` : dossier par défaut de platformdirs."""

    log_max_bytes: int = 1_000_000
    """Taille d'un fichier de `<data>/logs/app.log` avant rotation."""

    log_backup_count: int = 3
    """Nombre de fichiers de journal conservés après rotation."""

    def resolved_data_dir(self) -> Path:
        """Dossier des données : `data_dir`, sinon celui de platformdirs (AD-5)."""
        if self.data_dir is not None:
            return self.data_dir
        return Path(user_data_dir("WaveDevSecOps", appauthor=False, roaming=False))

    @classmethod
    def from_env(cls, environ: Mapping[str, str] | None = None) -> Settings:
        """Construit les réglages depuis les variables `WDS_*` (par défaut `os.environ`)."""
        source = os.environ if environ is None else environ
        values = {
            name: source[ENV_PREFIX + name.upper()]
            for name in cls.model_fields
            if ENV_PREFIX + name.upper() in source
        }
        return cls.model_validate(values)


@cache
def get_settings() -> Settings:
    """Réglages du processus courant, lus une fois."""
    return Settings.from_env()
