"""Étape de quiz à exécution réelle : l'apprenant choisit une commande, qui s'exécute pour de vrai.

Chaque choix porte la commande proposée et, pour une mauvaise réponse, ce que son effet
enseigne (`effect_text`). L'étape ne juge pas le dépôt : elle lit le choix porté par
l'opération `quiz_choice` (`ctx.data["quiz_choice"]`). Une bonne réponse la valide ; une
mauvaise la laisse ouverte, avec l'explication de son effet (FR-15).
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from wavedevsecops.contracts import RepoState
from wavedevsecops.scenarios.steps._base import SNAKE_PATTERN, StepArgs, StepContext, Verdict

QUIZ_INTENT = "quiz_choice"
CHOICE_KEY = "quiz_choice"
"""Clé de `OpContext.data` portant le `choice_id` choisi."""
NO_EFFECT_WARNING = "une mauvaise réponse sans explication de son effet"
MISSING_EFFECT_TEXT = "Cette commande n'était pas la bonne : son effet est visible dans les vues."


class Choice(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    choice_id: str = Field(pattern=SNAKE_PATTERN)
    command_text: str = Field(min_length=1, max_length=500)
    """Ligne tapée dans le terminal, avec `git` en tête (par exemple `git reset --hard HEAD~1`)."""
    correct: bool = False
    effect_text: str = ""
    """Pour une mauvaise réponse : l'effet de la commande et pourquoi ce n'était pas elle."""


class Args(StepArgs):
    type: Literal["quiz"]
    choices: list[Choice] = Field(min_length=2)

    @model_validator(mode="after")
    def _one_correct(self) -> Args:
        ids = [c.choice_id for c in self.choices]
        if len(set(ids)) != len(ids):
            raise ValueError("choice_id en double dans les choix du quiz")
        if sum(c.correct for c in self.choices) != 1:
            raise ValueError("un quiz a exactement une bonne réponse")
        return self

    def authoring_warnings(self) -> list[tuple[tuple[str | int, ...], str]]:
        return [
            (("choices", index, "effect_text"), NO_EFFECT_WARNING)
            for index, choice in enumerate(self.choices)
            if not choice.correct and not choice.effect_text
        ]


def panel(step: Args) -> dict[str, Any]:
    """Les commandes proposées au panneau, jamais la bonne réponse (le serveur juge)."""
    return {
        "quiz": {
            "choices": [
                {"choice_id": c.choice_id, "command_text": c.command_text} for c in step.choices
            ]
        }
    }


def check(state: RepoState | None, ctx: StepContext) -> Verdict:
    """Bonne réponse : `passed` ; mauvaise : `failed` avec son explication ; sinon `pending`."""
    if ctx.intent != QUIZ_INTENT:
        return Verdict(status="pending")
    choice = next((c for c in ctx.step.choices if c.choice_id == ctx.data.get(CHOICE_KEY)), None)
    if choice is None:
        return Verdict(status="pending")
    if choice.correct:
        return Verdict(status="passed")
    return Verdict(status="failed", reason_text=choice.effect_text or MISSING_EFFECT_TEXT)
