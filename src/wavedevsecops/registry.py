"""Registre d'outils (AD-16) : lecture de `tools.toml`, seule source des outils requis.

Module bas niveau : il n'importe que `config`. Le diagnostic, `toolrun`, les scénarios et
les installeurs lisent ce registre ; aucun ne redéclare un outil ou une version.
"""

from __future__ import annotations

import re
import tomllib
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from wavedevsecops.config import Settings, get_settings

Resolution = Literal["host-or-provisioned", "host", "provisioned", "uv-lock"]
Family = Literal["windows", "posix"]


class Tool(BaseModel):
    """Un outil du registre."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str
    usage: str
    milestone: str
    resolution: Resolution
    min_version: str = ""
    provisioned_version: str | dict[Family, str]
    paths: dict[Family, list[str]] = Field(default_factory=dict)
    probe: list[str] = Field(default_factory=list)
    version_regex: str = r"(\d+(?:\.\d+)+)"
    network: bool
    network_switch: str = ""

    @model_validator(mode="after")
    def _coherent(self) -> Tool:
        if self.resolution != "uv-lock" and not self.probe:
            raise ValueError(f"{self.id} : une sonde de version est requise")
        if self.resolution in {"host-or-provisioned", "provisioned"} and not self.paths:
            raise ValueError(f"{self.id} : `paths` est requis pour une résolution dans tools/")
        if self.network and not self.network_switch:
            raise ValueError(f"{self.id} : un outil qui sort déclare le réglage qui le coupe")
        try:
            re.compile(self.version_regex)
        except re.error as exc:
            raise ValueError(f"{self.id} : expression de version invalide ({exc})") from exc
        return self

    def provisioned_for(self, family: Family) -> str:
        value = self.provisioned_version
        return value if isinstance(value, str) else value[family]


class Registry(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    tool: list[Tool]

    @model_validator(mode="after")
    def _unique_ids(self) -> Registry:
        ids = [t.id for t in self.tool]
        if len(ids) != len(set(ids)):
            raise ValueError("identifiants d'outils en double")
        return self

    def get(self, tool_id: str) -> Tool:
        for tool in self.tool:
            if tool.id == tool_id:
                return tool
        raise KeyError(f"outil inconnu du registre : {tool_id}")


def load_registry(path: Path | None = None, settings: Settings | None = None) -> Registry:
    """Lit et valide `tools.toml` (`ValueError` ou `OSError` si le fichier est abîmé)."""
    target = path or (settings or get_settings()).tools_path()
    return Registry.model_validate(tomllib.loads(target.read_text(encoding="utf-8")))


_NUMBER = re.compile(r"\d+(?:\.\d+)*")


def parse_version(text: str) -> tuple[int, ...] | None:
    """Premier numéro de version d'un texte (`2.55.0.windows.1` -> (2, 55, 0)), sinon None."""
    match = _NUMBER.search(text)
    return tuple(int(part) for part in match.group(0).split(".")) if match else None


def at_least(found: tuple[int, ...], minimum: str) -> bool:
    """Vrai si `found` atteint `minimum` (les composantes manquantes valent 0)."""
    wanted = parse_version(minimum) or ()
    width = max(len(found), len(wanted))
    return found + (0,) * (width - len(found)) >= wanted + (0,) * (width - len(wanted))


def extract_version(tool: Tool, output: str) -> tuple[int, ...] | None:
    """Numéro de version trouvé dans la sortie de la sonde de `tool`, sinon None."""
    match = re.search(tool.version_regex, output)
    if match is None:
        return None
    return parse_version(match.group(1) if match.groups() else match.group(0))
