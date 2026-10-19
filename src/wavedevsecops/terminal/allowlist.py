"""Liste blanche du terminal (AD-4) : un seul fichier de données, `content/terminal-allowlist.yaml`.

La garde (`parse`) et le texte des refus lisent ce même fichier : la liste citée à l'apprenant
est exactement celle qui est appliquée. La story 2.5 y ajoute les commandes de fichiers sous
`files`, sans toucher à la garde.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator

from wavedevsecops.config import Settings, get_settings

FILE_NAME = "terminal-allowlist.yaml"


class ReadRule(BaseModel):
    """Conditions (toutes) pour qu'une commande compte comme lecture."""

    model_config = ConfigDict(extra="forbid")

    options_within: list[str] | None = None
    positionals_max: int | None = None
    first_positional_in: list[str] | None = None


class GitSubcommand(BaseModel):
    model_config = ConfigDict(extra="forbid")

    read: bool | ReadRule = False
    options: list[str] = []
    value_options: list[str] = []
    choices: list[str] = []
    refused_arguments: list[str] = []
    number_option: bool = False
    needs_message: bool = False
    needs_message_with: list[str] = []
    touches_origin: bool = False
    remote_argument: bool = False
    remote_names_from: int | None = None
    """Positionnels, à partir de cet indice, qui doivent nommer des remotes existants."""
    positionals_max: int | None = None
    writable_keys: list[str] = []

    @model_validator(mode="after")
    def _values_are_options(self) -> GitSubcommand:
        unknown = set(self.value_options) - set(self.options)
        if unknown:
            raise ValueError(f"value_options hors de options : {sorted(unknown)}")
        return self


class FileCommandSpec(BaseModel):
    """Commande de fichiers (story 2.5), exécutée en Python sur `wsfs`."""

    model_config = ConfigDict(extra="forbid")

    read: bool = False
    """Vrai : lecture, admise pendant un quiz."""
    options: list[str] = []
    min_args: int = 0
    max_args: int | None = None
    globs: bool = False
    """Vrai : `*` et `?` sont résolus dans le bac à sable (rm, mv, cp seulement)."""
    redirect: bool = False
    """Vrai : `> f` ou `>> f` en fin de ligne (echo) ; sans redirection, c'est une lecture."""
    text: bool = False
    """Vrai : les arguments sont du texte (echo), pas des chemins ni des options."""


class ToolSpec(BaseModel):
    """Outil de la chaîne tapé dans le terminal (story 7.2) : accepté seulement si le scénario
    le déclare (`tools`), lancé par `toolrun` dans l'environnement d'exercice."""

    model_config = ConfigDict(extra="forbid")

    barrier_id: str
    """Barrière (`content/chain.yaml`) dont la sortie de l'outil est la preuve (AD-14)."""
    subcommands: list[str] = []
    """Premier mot obligatoire (`ruff check`) ; vide : l'outil n'en a pas (`pytest`)."""
    options: list[str] = []
    value_options: list[str] = []
    """Options qui prennent une valeur (collée, après `=` ou dans l'argument suivant)."""
    write_options: list[str] = []
    """Options qui modifient l'arbre de travail (`--fix`) : refusées en `quiz_altered`."""
    paths: bool = True
    """Vrai : les positionnels sont des chemins du dépôt (jamais absolus ni hors du dépôt)."""

    @model_validator(mode="after")
    def _consistent(self) -> ToolSpec:
        unknown = (set(self.value_options) | set(self.write_options)) - set(self.options)
        if unknown:
            raise ValueError(f"options hors de options : {sorted(unknown)}")
        return self


class Allowlist(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: int
    messages: dict[str, str]
    forbidden_options: list[str]
    files: dict[str, FileCommandSpec] = Field(default_factory=dict)
    tools: dict[str, ToolSpec] = Field(default_factory=dict)
    git: dict[str, GitSubcommand]

    def message(self, key: str, **values: object) -> str:
        return self.messages[key].format(**values).strip()

    def accepted(self) -> str:
        """Phrase qui cite la liste acceptée, tirée du fichier."""
        text = self.message("accepted", subcommands=", ".join(self.git))
        if self.files:
            text += " " + self.message("accepted_files", commands=", ".join(self.files))
        if self.tools:
            text += " " + self.message("accepted_tools", tools=", ".join(self.tools))
        return text

    def accepted_options(self, sub: str) -> str:
        options = [o for o in self.git[sub].options if o != "--"]
        return self.message("accepted_options", sub=sub, options=", ".join(options))


def load_allowlist(path: Path) -> Allowlist:
    return Allowlist.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))


@lru_cache(maxsize=8)
def _load(path: Path) -> Allowlist:
    return load_allowlist(path)


def get_allowlist(settings: Settings | None = None) -> Allowlist:
    """Liste blanche du lancement (lue une fois par fichier)."""
    settings = settings or get_settings()
    return _load(settings.content_path() / FILE_NAME)
