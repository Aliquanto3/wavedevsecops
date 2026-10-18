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
from pydantic import BaseModel, ConfigDict, field_validator

ENV_PREFIX = "WDS_"
APP_NAME = "WaveDevSecOps"
PROXY_VARIABLES = ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "NO_PROXY", "UV_SYSTEM_CERTS")


def project_root() -> Path:
    """Racine du dépôt (clone ou zip) : là où vivent `tools.toml` et `content/`."""
    return Path(__file__).resolve().parents[2]


class Settings(BaseModel):
    """Réglages de WaveDevSecOps. Les stories suivantes y ajoutent leurs champs."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    data_dir: Path | None = None
    """Dossier des données utilisateur ; `None` : dossier par défaut de platformdirs."""

    @field_validator("data_dir", mode="before")
    @classmethod
    def _empty_data_dir(cls, value: object) -> object:
        """`WDS_DATA_DIR=""` vaut « non fixé », pas le répertoire courant."""
        return None if isinstance(value, str) and not value.strip() else value

    log_max_bytes: int = 1_000_000
    """Taille d'un fichier de `<data>/logs/app.log` avant rotation."""

    log_backup_count: int = 3
    """Nombre de fichiers de journal conservés après rotation."""

    def resolved_data_dir(self) -> Path:
        """Dossier des données : `data_dir`, sinon celui de platformdirs (AD-5)."""
        if self.data_dir is not None:
            return self.data_dir
        return Path(user_data_dir(APP_NAME, appauthor=False, roaming=False))

    tools_file: Path | None = None
    """Registre d'outils (AD-16) ; `None` : `tools.toml` à la racine du dépôt."""

    content_dir: Path | None = None
    """Dossier `content/` ; `None` : `content/` à la racine du dépôt."""

    probe_timeout_s: float = 10.0
    """Délai maximal d'une sonde d'outil (version, locale, `xcode-select`), en secondes."""

    def tools_path(self) -> Path:
        return self.tools_file if self.tools_file is not None else project_root() / "tools.toml"

    def content_path(self) -> Path:
        return self.content_dir if self.content_dir is not None else project_root() / "content"

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


def read_proxy_environment(environ: Mapping[str, str] | None = None) -> dict[str, str]:
    """Variables de proxy posées (casse ignorée), sous leur nom en majuscules."""
    source = os.environ if environ is None else environ
    found: dict[str, str] = {}
    for name, value in source.items():
        upper = name.upper()
        if upper not in PROXY_VARIABLES or not value.strip():
            continue
        if upper == "NO_PROXY" and upper in found:
            # `NO_PROXY` et `no_proxy` peuvent différer : les outils lisent l'une ou l'autre,
            # on garde donc l'union de leurs entrées plutôt que la première rencontrée.
            known = [e.strip() for e in found[upper].split(",")]
            extra = [e.strip() for e in value.split(",") if e.strip() not in known]
            found[upper] = ",".join(known + extra)
        else:
            found.setdefault(upper, value.strip())
    return found


def inherited_environment(environ: Mapping[str, str] | None = None) -> dict[str, str]:
    """Copie de l'environnement du processus, point de départ de celui d'un outil."""
    return dict(os.environ if environ is None else environ)
