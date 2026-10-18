"""Modèle commun des arguments d'une op de setup (AD-7)."""

from __future__ import annotations

import re
from typing import ClassVar

from pydantic import BaseModel, ConfigDict, Field

ALIAS_PATTERN = r"^[a-z0-9]+(?:-[a-z0-9]+)*$"
"""Alias en kebab-case (conventions du spine)."""

_BRANCH = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]*$")


class OpArgs(BaseModel):
    """Arguments d'une op : `op` (discriminant) et `as` (alias facultatif)."""

    model_config = ConfigDict(frozen=True, extra="forbid", populate_by_name=True)

    op: str
    as_: str | None = Field(default=None, alias="as", pattern=ALIAS_PATTERN)
    """Alias de l'élément produit, cité ensuite sous la forme `@alias`."""

    reference_fields: ClassVar[tuple[str, ...]] = ()
    """Champs qui acceptent `@alias` ; le chargeur vérifie que l'alias est déjà défini."""

    def references(self) -> list[tuple[str, str]]:
        """`(champ, alias)` de chaque référence `@alias` de l'op."""
        found = []
        for name in self.reference_fields:
            value = getattr(self, name)
            if isinstance(value, str) and value.startswith("@"):
                found.append((name, value[1:]))
        return found


def check_revision(value: str) -> str:
    """Révision de départ : refus d'une valeur vide ou commençant par `-` (option de git)."""
    if not value.strip() or value.startswith("-"):
        raise ValueError(f"révision invalide : « {value} »")
    return value


def check_branch(value: str) -> str:
    """Nom de branche simple, ou `@alias` : refus des espaces, `..`, `/` final, `.lock`."""
    if value.startswith("@"):
        return value
    if (
        not _BRANCH.match(value)
        or ".." in value
        or "//" in value
        or value.endswith(("/", ".", ".lock"))
    ):
        raise ValueError(f"nom de branche invalide : « {value} »")
    return value
