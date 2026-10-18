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

from pydantic import BaseModel, ConfigDict

ENV_PREFIX = "WDS_"


class Settings(BaseModel):
    """Réglages de WaveDevSecOps. Les stories suivantes y ajoutent leurs champs."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    data_dir: Path | None = None
    """Dossier des données utilisateur ; `None` : dossier par défaut de platformdirs."""

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
