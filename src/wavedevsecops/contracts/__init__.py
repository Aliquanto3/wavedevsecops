"""Schémas partagés et grammaire `element_id` (AD-2).

Module feuille (AD-1) : n'importe rien du projet ; tout module peut l'importer.
"""

from __future__ import annotations

from typing import Literal
from urllib.parse import quote, unquote

from pydantic import BaseModel, ConfigDict


class AppError(Exception):
    """Erreur métier typée (convention « Erreurs »).

    Elle porte deux textes en français pour l'apprenant : ce qui s'est passé
    (`cause_text`) et ce qu'il peut faire (`action_text`). Jamais de trace Python montrée.
    """

    def __init__(self, cause_text: str, action_text: str) -> None:
        super().__init__(f"{cause_text} {action_text}")
        self.cause_text = cause_text
        self.action_text = action_text


CheckStatus = Literal["ok", "missing", "too_old", "mismatch", "info", "warn"]


class CheckPart(BaseModel):
    """Ligne détaillée d'une sonde (la section Proxy : valeur masquée, NO_PROXY, certificats)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    label_text: str
    value_text: str = ""
    status: CheckStatus
    status_text: str
    what_to_do_text: str = ""


class DiagnosticCheck(BaseModel):
    """Résultat d'une sonde du diagnostic : charge utile de l'événement `diagnostic_check`.

    Les textes sont écrits par le serveur (convention `_text`).
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    check_id: str
    group: Literal["tool", "git_language", "proxy"]
    label_text: str
    status: CheckStatus
    blocking: bool
    """Vrai si l'état bloque les scénarios qui exigent cet outil (jamais une information)."""
    status_text: str
    detail_text: str
    what_to_do_text: str = ""
    """Texte « Que faire ? » de `content/diagnostic.yaml` ; vide si rien à régler."""
    milestone: str = ""
    version: str = ""
    usage_text: str = ""
    """À quoi sert l'outil (colonne « Usage »)."""
    required_version: str = ""
    """Version requise, écrite par le serveur (« ≥ 2.38 » ou la version exacte)."""
    unavailable_scenarios: list[str] = []
    """Titres des scénarios que cet état rend indisponibles (AD-16) ; vide sans scénario."""
    parts: list[CheckPart] = []
    """Lignes détaillées (section Proxy) ; vide pour un outil."""


ELEMENT_KINDS = frozenset(
    {
        "commit",
        "ref",
        "path",
        "diffline",
        "pr",
        "check",
        "review",
        "sbom",
        "tag",
        "output",
        "outline",
        "barrier",
        "env",
    }
)
"""Types d'`element_id` de la grammaire d'AD-2."""


def element_id(kind: str, *segments: str) -> str:
    """Construit un `element_id` (AD-2) : `kind:seg1:seg2…`, segments encodés en pourcentage.

    `/` reste lisible (chemins posix, noms de ref) ; `:` et `%` sont encodés.
    """
    if kind not in ELEMENT_KINDS:
        raise ValueError(f"type d'element_id inconnu : {kind}")
    if not segments:
        raise ValueError("un element_id a au moins un segment")
    return ":".join([kind, *(quote(str(s), safe="/@") for s in segments)])


def parse_element_id(value: str) -> tuple[str, list[str]]:
    """Analyse un `element_id` : `(kind, segments décodés)`."""
    kind, sep, rest = value.partition(":")
    if kind not in ELEMENT_KINDS or not sep or not rest:
        raise ValueError(f"element_id invalide : {value}")
    return kind, [unquote(s) for s in rest.split(":")]
