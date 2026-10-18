"""Modèle pydantic d'un scénario (AD-7), `schema_version` 1.

Un scénario déclare son identité, ses parcours, ses outils, son gabarit de départ, son
`setup` (liste d'ops du registre) et ses étapes. Les champs que les stories suivantes
ajoutent (protection et règles de PR, réactions du collègue, types d'étape) s'ajoutent ici
sans changer les scénarios existants.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from wavedevsecops.scenarios.ops import op_union
from wavedevsecops.scenarios.steps import step_union

SCHEMA_VERSION = 1
KEBAB_PATTERN = r"^[a-z0-9]+(?:-[a-z0-9]+)*$"
SNAKE_PATTERN = r"^[a-z][a-z0-9]*(?:_[a-z0-9]+)*$"

Track = Literal["llm", "no_ai"]
"""Parcours servis : celui avec l'IA et celui sans IA (gabarits `content/exercise/<parcours>/`)."""
Mode = Literal["A", "B"]

SetupOp = op_union()


FORBIDDEN_STEP_INTENT = "run_exercise_code"
"""Intention réservée à l'apprenant (AD-13) : aucune étape ne peut la déclarer."""


def _mentions(value: object, needle: str) -> bool:
    """Vrai si `needle` figure, comme clé ou comme texte, n'importe où dans `value`."""
    if isinstance(value, str):
        return needle in value
    if isinstance(value, dict):
        return any(_mentions(k, needle) or _mentions(v, needle) for k, v in value.items())
    if isinstance(value, (list, tuple)):
        return any(_mentions(item, needle) for item in value)
    return False


StepSpec = step_union()
"""Une étape : un type du registre `scenarios/steps/`, discriminé par `type` (AD-7)."""


class Scenario(BaseModel):
    """Un scénario `content/scenarios/<scenario_id>.<mode>.yaml`."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: Literal[1]
    scenario_id: str = Field(pattern=KEBAB_PATTERN)
    mode: Mode
    title_text: str = Field(min_length=1)
    section: str | None = None
    catalogue: bool = True
    """Faux : scénario interne (gabarit d'exercice, empreinte de référence), jamais proposé à
    l'apprenant dans le catalogue."""
    station: int | None = Field(default=None, ge=0, le=4)
    tracks: list[Track] = Field(min_length=1)
    """Parcours servis ; un espace par parcours (AD-5)."""
    tools: list[str] = Field(default_factory=list)
    """Outils requis, identifiants du registre `tools.toml` (AD-16)."""
    template: Literal["empty"] = "empty"
    """Gabarit de départ du dépôt ; `empty` : dépôt vide. Les gabarits d'exercice arrivent
    avec leurs stories."""
    setup: list[SetupOp] = Field(default_factory=list)  # type: ignore[valid-type]
    steps: list[StepSpec] = Field(default_factory=list)  # type: ignore[valid-type]

    @property
    def key(self) -> str:
        """`<scenario_id>.<mode>` : nom du fichier et de l'espace."""
        return f"{self.scenario_id}.{self.mode}"

    def semantic_errors(
        self, tool_ids: set[str] | None = None, explain_keys: set[str] | None = None
    ) -> list[tuple[tuple, str]]:
        """Règles entre champs : `(chemin du champ, message)` pour chaque écart."""
        errors: list[tuple[tuple, str]] = []
        seen_tracks: set[str] = set()
        for index, track in enumerate(self.tracks):
            if track in seen_tracks:
                errors.append((("tracks", index), f"parcours « {track} » en double"))
            seen_tracks.add(track)
        if tool_ids is not None:
            for index, tool in enumerate(self.tools):
                if tool not in tool_ids:
                    errors.append((("tools", index), f"outil inconnu du registre : « {tool} »"))
        defined: set[str] = set()
        for index, op in enumerate(self.setup):
            for field, alias in op.references():
                if alias not in defined:
                    errors.append(
                        (
                            ("setup", index, field),
                            f"l'alias « @{alias} » n'est défini par aucune op précédente",
                        )
                    )
            if op.as_ is not None:
                if op.as_ in defined:
                    errors.append((("setup", index, "as"), f"alias « {op.as_} » en double"))
                defined.add(op.as_)
        step_ids: set[str] = set()
        for index, step in enumerate(self.steps):
            if _mentions(step.model_dump(), FORBIDDEN_STEP_INTENT):
                errors.append(
                    (
                        ("steps", index),
                        f"une étape ne peut pas déclarer « {FORBIDDEN_STEP_INTENT} » : seul "
                        "l'apprenant lance le code d'exercice, après confirmation (AD-13)",
                    )
                )
            if step.step_id in step_ids:
                errors.append(
                    (("steps", index, "step_id"), f"step_id « {step.step_id} » en double")
                )
            step_ids.add(step.step_id)
            for field, alias in step.references():
                if alias not in defined:
                    errors.append(
                        (
                            ("steps", index, *field),
                            f"l'alias « @{alias} » n'est défini par aucune op du setup",
                        )
                    )
            if (
                step.explain_ref
                and explain_keys is not None
                and step.explain_ref not in explain_keys
            ):
                errors.append(
                    (
                        ("steps", index, "explain_ref"),
                        f"clé d'explication inconnue : « {step.explain_ref} »",
                    )
                )
        return errors

    def authoring_warnings(self) -> list[tuple[tuple, str]]:
        """Avertissements du lint de contenu à l'auteur : le scénario reste valide."""
        return [
            (("steps", index, *field), message)
            for index, step in enumerate(self.steps)
            for field, message in step.authoring_warnings()
        ]
