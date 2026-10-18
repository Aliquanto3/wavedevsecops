"""Schémas partagés et grammaire `element_id` (AD-2).

`repo` : `RepoState`, l'état git relu après chaque opération ; `views` : projections que le
serveur publie dans `state_projected` (graphe placé, index, invite). Versionnés, en ajout
seulement (AD-17).

Module feuille (AD-1) : n'importe rien du projet ; tout module peut l'importer.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Sequence
from typing import Literal
from urllib.parse import quote, unquote

from pydantic import BaseModel, ConfigDict

from wavedevsecops.contracts.repo import (
    REPO_STATE_VERSION,
    Actor,
    Commit,
    Head,
    IndexEntry,
    InProgress,
    Ref,
    RefKind,
    RepoState,
    StashEntry,
    StatusEntry,
    StatusKind,
)
from wavedevsecops.contracts.views import (
    VIEWS_VERSION,
    GraphEdge,
    GraphNode,
    GraphView,
    PromptView,
    RefLabel,
    StagingItem,
    StagingView,
    Views,
)


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


_SHA40 = re.compile(r"^[0-9a-f]{40}$")
_INT = re.compile(r"^[1-9][0-9]*$")
_LINE = re.compile(r"^[0-9]+$")


def _sha40(value: str) -> bool:
    return bool(_SHA40.match(value))


def _anything(value: str) -> bool:
    return True


def _one_of(*allowed: str) -> Callable[[str], bool]:
    return lambda value: value in allowed


def _sha_or(*allowed: str) -> Callable[[str], bool]:
    return lambda value: value in allowed or _sha40(value)


def _number(value: str) -> bool:
    return bool(_INT.match(value))


def _line(value: str) -> bool:
    return bool(_LINE.match(value))


ELEMENT_FORMS: dict[str, tuple[Callable[[str], bool], ...]] = {
    "commit": (_sha40,),
    "ref": (_anything,),
    "path": (_one_of("head", "index", "worktree"), _anything),
    "diffline": (_sha_or("index", "worktree"), _anything, _one_of("old", "new"), _line),
    "pr": (_number,),
    "check": (_number, _anything, _sha40),
    "review": (_number, _number),
    "sbom": (_anything,),
    "tag": (_anything,),
    "output": (_anything,),
    "outline": (_anything, _line),
    "barrier": (_anything,),
    "env": (_one_of("staging", "prod"),),
}
"""Formes d'AD-2 : un contrôle par segment (le nombre de segments est fixé par le type).

`commit:<sha40>`, `ref:<nom complet>`, `path:<head|index|worktree>:<chemin posix>`,
`diffline:<sha40|index|worktree>:<chemin>:<old|new>:<ligne>`, `pr:<n>`,
`check:<pr>:<job_id>:<head_sha40>`, `review:<pr>:<n>`, `sbom:<paquet>@<version>`,
`tag:<nom>`, `output:<op_id>`, `outline:<op_id>:<ligne>`, `barrier:<id>`,
`env:<staging|prod>`.
"""

ELEMENT_KINDS = frozenset(ELEMENT_FORMS)
"""Types d'`element_id` de la grammaire d'AD-2."""


def _check_form(kind: str, segments: Sequence[str], source: str) -> None:
    form = ELEMENT_FORMS.get(kind)
    if form is None:
        raise ValueError(f"type d'element_id inconnu : {source}")
    if len(segments) != len(form):
        raise ValueError(
            f"element_id « {source} » : {len(form)} segment(s) attendu(s) pour « {kind} »"
        )
    for segment, valid in zip(segments, form, strict=True):
        if not segment or not valid(segment):
            raise ValueError(f"element_id « {source} » : segment invalide « {segment} »")


def element_id(kind: str, *segments: str) -> str:
    """Construit un `element_id` (AD-2) : `kind:seg1:seg2…`, segments encodés en pourcentage.

    `/` et `@` restent lisibles (chemins posix, noms de ref, `paquet@version`) ; `:`, `%`,
    les espaces et tout caractère non ASCII sont encodés (UTF-8). Chaque forme d'AD-2 est
    vérifiée : nombre de segments, SHA complet, zone d'un chemin, numéros.
    """
    values = [str(s) for s in segments]
    _check_form(kind, values, kind)
    return ":".join([kind, *(quote(s, safe="/@") for s in values)])


def parse_element_id(value: str) -> tuple[str, list[str]]:
    """Analyse un `element_id` : `(kind, segments décodés)` ; `ValueError` s'il est invalide.

    Inverse exact de `element_id` : seule la forme canonique est acceptée, si bien que
    deux vues ne peuvent pas nommer différemment le même élément.
    """
    kind, sep, rest = value.partition(":")
    if kind not in ELEMENT_KINDS or not sep or not rest:
        raise ValueError(f"element_id invalide : {value}")
    segments = [unquote(s, errors="strict") for s in rest.split(":")]
    _check_form(kind, segments, value)
    if element_id(kind, *segments) != value:
        raise ValueError(f"element_id non canonique : {value}")
    return kind, segments


__all__ = [
    "ELEMENT_FORMS",
    "ELEMENT_KINDS",
    "REPO_STATE_VERSION",
    "VIEWS_VERSION",
    "Actor",
    "AppError",
    "CheckPart",
    "CheckStatus",
    "Commit",
    "DiagnosticCheck",
    "GraphEdge",
    "GraphNode",
    "GraphView",
    "Head",
    "InProgress",
    "IndexEntry",
    "PromptView",
    "Ref",
    "RefKind",
    "RefLabel",
    "RepoState",
    "StagingItem",
    "StagingView",
    "StashEntry",
    "StatusEntry",
    "StatusKind",
    "Views",
    "element_id",
    "parse_element_id",
]
