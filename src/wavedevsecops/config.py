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
from pydantic import BaseModel, ConfigDict, Field, field_validator

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

    git_timeout_s: float = 30.0
    """Délai maximal d'une commande git interne (setup, lectures de l'empreinte), en secondes."""

    event_buffer: int = Field(default=1000, ge=1)
    """Événements gardés par espace pour la reprise du flux SSE (`Last-Event-ID`, AD-17)."""

    max_active_workspaces: int = Field(default=3, ge=1)
    """Espaces actifs (file, surveillant, runs) au plus ; les autres dorment (AD-1)."""

    max_pending_ops: int = Field(default=32, ge=1)
    """Opérations en attente dans la file d'un espace avant de refuser une intention (409)."""

    watch_quiet_ms: int = Field(default=500, ge=0)
    """Silence après une commande avant que le surveillant de l'arbre reprenne (AD-1)."""

    sse_heartbeat_s: float = Field(default=15.0, gt=0)
    """Intervalle des lignes de maintien du flux SSE, en secondes."""

    engine_stop_timeout_s: float = Field(default=30.0, gt=0)
    """Attente maximale de la fin de l'opération en cours quand un espace s'endort."""

    terminal_timeout_s: float = Field(default=30.0, gt=0)
    """Délai d'une commande tapée dans le terminal ; au-delà, l'arbre est arrêté (AD-4, AD-12)."""

    max_snapshots: int = Field(default=20, ge=2)
    """Instantanés gardés par espace ; le 0 et le dernier le sont toujours (AD-6)."""

    restore_retry_ms: int = Field(default=250, ge=0)
    """Pause avant le 2e essai d'un renommage de restauration (doublée avant le 3e, AD-6)."""

    def gitconfig_path(self) -> Path:
        """`<data>/gitconfig`, désigné par `GIT_CONFIG_GLOBAL` (AD-3, AD-5)."""
        return self.resolved_data_dir() / "gitconfig"

    def workspaces_path(self) -> Path:
        """`<data>/workspaces/` : un espace par parcours, scénario et mode (AD-5)."""
        return self.resolved_data_dir() / "workspaces"

    def scenarios_path(self) -> Path:
        """`content/scenarios/` : un YAML par scénario et par mode (AD-7)."""
        return self.content_path() / "scenarios"

    def osv_path(self) -> Path:
        """`content/osv/` : l'extrait figé de la base de vulnérabilités (AD-11)."""
        return self.content_path() / "osv"

    def osv_url(self, port: int) -> str:
        """URL du point OSV local pour le serveur sur `port` : la seule source (AD-11)."""
        return f"http://127.0.0.1:{port}/osv/v1/query"

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
