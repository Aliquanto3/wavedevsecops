"""Étape de désignation : l'apprenant montre dans les vues l'élément en cause, en un seul essai.

L'étape porte la question, les types d'éléments acceptés (`accept`) et une liste de cases
(`slots`). Chaque case a son ensemble de bonnes réponses (`answers`, des `@alias` du setup) et
un élément principal (`primary`) : les autres sont des équivalents, aussi justes. Le serveur
corrige contre le `RepoState` courant à la réception de `answer_submit` ; l'étape se ferme à
cette première réponse, juste ou fausse (AD-7, AD-14, AD-17).
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from wavedevsecops.contracts import ELEMENT_KINDS, RepoState, parse_element_id
from wavedevsecops.scenarios.steps._base import SNAKE_PATTERN, StepArgs, StepContext, Verdict

ANSWER_INTENT = "answer_submit"
ANSWER_KEY = "answer_step"
"""Clé de `OpContext.data` : `step_id` de l'étape que l'opération vient de corriger."""


def _ref_is_valid(value: str) -> bool:
    """Un `@alias` du setup, ou un `element_id` littéral valide."""
    if value.startswith("@"):
        return len(value) > 1
    try:
        parse_element_id(value)
    except ValueError:
        return False
    return True


class Slot(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    slot_id: str = Field(pattern=SNAKE_PATTERN)
    label_text: str = Field(min_length=1)
    """Intitulé de la case (« Le commit en cause »)."""
    answers: list[str] = Field(min_length=1)
    """Bonnes réponses : `@alias` définis par le setup (ou `element_id` littéraux)."""
    primary: str
    """Élément principal, dans `answers` : celui que la correction annonce comme attendu."""

    @model_validator(mode="after")
    def _coherent(self) -> Slot:
        bad = [a for a in self.answers if not _ref_is_valid(a)]
        if bad:
            raise ValueError(f"réponse(s) invalide(s) : {', '.join(bad)} (@alias ou element_id)")
        if len(set(self.answers)) != len(self.answers):
            raise ValueError("réponse en double dans `answers`")
        if self.primary not in self.answers:
            raise ValueError("`primary` doit figurer dans `answers`")
        return self


class Args(StepArgs):
    type: Literal["designate"]
    question_text: str = Field(min_length=1)
    accept: list[str] = Field(min_length=1)
    """Types d'`element_id` acceptés (`commit`, `ref`, `tag`, `path`…) : tous les éléments de
    ces types sont désignables, pas seulement les bonnes réponses."""
    slots: list[Slot] = Field(min_length=1)

    @model_validator(mode="after")
    def _coherent(self) -> Args:
        unknown = [k for k in self.accept if k not in ELEMENT_KINDS]
        if unknown:
            raise ValueError(f"type(s) d'élément inconnu(s) : {', '.join(unknown)}")
        if len(set(self.accept)) != len(self.accept):
            raise ValueError("type en double dans `accept`")
        ids = [s.slot_id for s in self.slots]
        if len(set(ids)) != len(ids):
            raise ValueError("slot_id en double")
        for slot in self.slots:
            for value in slot.answers:
                if not value.startswith("@") and parse_element_id(value)[0] not in self.accept:
                    raise ValueError(f"« {value} » n'est pas d'un type accepté")
        return self


def panel(step: Args) -> dict[str, Any]:
    """La question, les types acceptés et les cases ; jamais les bonnes réponses (AD-2)."""
    return {
        "designate": {
            "question_text": step.question_text,
            "accept": list(step.accept),
            "slots": [{"slot_id": s.slot_id, "label_text": s.label_text} for s in step.slots],
        }
    }


def check(state: RepoState | None, ctx: StepContext) -> Verdict:
    """Close par la première réponse corrigée ; ne juge pas le dépôt (la correction est faite
    par l'opération `answer_submit`, qui a déposé `ctx.data[ANSWER_KEY]`)."""
    if ctx.intent == ANSWER_INTENT and ctx.data.get(ANSWER_KEY) == ctx.step.step_id:
        return Verdict(status="passed")
    return Verdict(status="pending")
