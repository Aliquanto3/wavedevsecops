"""Modèle commun d'une étape et de son verdict (AD-7)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from wavedevsecops.contracts import RepoState

SNAKE_PATTERN = r"^[a-z][a-z0-9]*(?:_[a-z0-9]+)*$"

VerdictStatus = Literal["passed", "pending", "failed", "unexpected"]
"""`passed` : l'étape est réussie ; `pending` : rien à dire (l'état n'a pas bougé) ; `failed` :
un état prévu par l'étape, mais pas encore celui qu'elle attend ; `unexpected` : un état ni
attendu ni prévu."""


class Observed(BaseModel):
    """Ce que l'étape voit : un texte et, s'il y en a un, l'élément du dépôt qu'il désigne."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    text: str
    element_id: str = ""


class Verdict(BaseModel):
    """Résultat de `check` : le serveur écrit les textes (AD-2)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    status: VerdictStatus
    reason_text: str = ""
    """Pour `failed` : la raison prévue par l'étape ou ce qu'il manque."""
    expected_text: str = ""
    """Ce que l'étape attend (pour `failed` et `unexpected`)."""
    observed: list[Observed] = []
    """Ce que l'étape voit, avec les liens vers les éléments."""


class StepArgs(BaseModel):
    """Champs communs des types d'étape ; chaque type ajoute les siens."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    step_id: str = Field(pattern=SNAKE_PATTERN)
    """Identifiant stable et unique dans le scénario : la progression le cite (AD-7)."""
    type: str
    title_text: str = Field(min_length=1)
    instruction_text: str = Field(min_length=1)
    explanation_text: str = Field(min_length=1)
    explain_ref: str = ""
    """Clé du catalogue d'explications liée à l'étape ; vide si aucune."""
    unexpected_text: str = ""
    """Explication d'un état inattendu propre à l'étape ; vide : texte général."""

    def references(self) -> list[tuple[tuple[str | int, ...], str]]:
        """`(chemin du champ, alias)` de chaque valeur `@alias` de l'étape, hors textes."""
        found: list[tuple[tuple[str | int, ...], str]] = []

        def walk(value: Any, path: tuple[str | int, ...]) -> None:
            if isinstance(value, dict):
                for key, item in value.items():
                    if not str(key).endswith("_text"):
                        walk(item, (*path, key))
            elif isinstance(value, list):
                for index, item in enumerate(value):
                    walk(item, (*path, index))
            elif isinstance(value, str) and value.startswith("@") and len(value) > 1:
                found.append((path, value[1:]))

        walk(self.model_dump(mode="python"), ())
        return found

    def authoring_warnings(self) -> list[tuple[tuple[str | int, ...], str]]:
        """`(chemin du champ, message)` des avertissements à l'auteur : pas des erreurs, le
        scénario reste chargé. Chaque type ajoute les siens."""
        return []


@dataclass
class StepContext:
    """Ce que `check` voit de l'étape et de l'opération qui la fait juger.

    Les types qui ne jugent pas le dépôt (quiz, désignation) lisent `intent` et `data` : ils
    reçoivent `state=None` quand la vue `repo` est illisible, et le moteur ne change pas."""

    step: Any
    aliases: dict[str, str] = field(default_factory=dict)
    """`alias -> element_id` du setup (`run.json`)."""
    previous: RepoState | None = None
    """État projeté avant l'opération ; `None` pour la première."""
    intent: str = ""
    """Intention de l'opération jugée (`terminal_line`, `external_change`, une réponse…)."""
    data: dict[str, Any] = field(default_factory=dict)
    """Valeurs portées par l'opération (`OpContext.data`) : la réponse d'un quiz, l'élément
    désigné… ; lecture seule."""
    views: dict[str, Any] = field(default_factory=dict)
    """Toutes les vues projetées après l'opération (pas seulement `repo`)."""
