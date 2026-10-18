"""Faits du premier passage : ajout seulement, idempotents, états dérivés (AD-14).

`progress.json` porte une liste `facts`. Un fait est identifié par ce qu'il constate :
`(kind, parcours, scenario_id, mode, step_id[, palier])`. Le premier fait d'une identité reste
et n'est jamais remplacé : un Recommencer qui refait l'étape, ou une soumission rejouée après
un arrêt brutal, est ignoré. La clé d'idempotence `(workspace_id, epoch, op_id)` est consignée
dans le fait ; elle désigne l'opération qui l'a produit.

Le moteur écrit `run.json` d'abord, puis soumet les faits (`ProgressStore.submit`) ; au
démarrage il soumet ceux qui manquent. Tout passe par un verrou unique par dossier de données
et une écriture atomique.
"""

from __future__ import annotations

import threading
from datetime import datetime
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from wavedevsecops.progress import FILENAME, _read_json, ensure_progress, write_json_atomic

FactKind = Literal["step_validated", "quiz_first_attempt", "hint_opened", "scenario_completed"]
ScenarioState = Literal["todo", "in_progress", "done"]


class Fact(BaseModel):
    """Un fait du premier passage. Les champs facultatifs dépendent du `kind`."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    kind: FactKind
    track: str
    scenario_id: str
    mode: str
    step_id: str = ""
    """Vide pour `scenario_completed`."""
    workspace_id: str
    epoch: int
    op_id: str
    at: str = ""
    """Horodatage ISO 8601 (renseigné à l'ajout s'il manque)."""
    correct: bool | None = None
    """`quiz_first_attempt` : le premier essai était-il juste ?"""
    tier: int | None = None
    """`hint_opened` : palier de l'indice."""
    delay_ms: int | None = None
    """`hint_opened` : temps écoulé avant la demande."""
    read_ms: int | None = None
    """`hint_opened` : temps de lecture."""

    @property
    def identity(self) -> tuple[Any, ...]:
        base = (self.kind, self.track, self.scenario_id, self.mode)
        if self.kind == "scenario_completed":
            return base
        if self.kind == "hint_opened":
            return (*base, self.step_id, self.tier)
        return (*base, self.step_id)


class ScenarioProgress(BaseModel):
    """États dérivés d'un scénario (jamais écrits dans `progress.json`)."""

    state: ScenarioState = "todo"
    steps_validated: list[str] = Field(default_factory=list)
    quiz_total: int = 0
    quiz_correct: int = 0
    first_try_score: int | None = None
    """Pourcentage de premiers essais justes ; `None` sans quiz ni désignation."""
    hints: int = 0
    """Nombre d'indices ouverts (un par palier et par étape)."""


def derive(
    facts: list[dict[str, Any]], track: str, scenario_id: str, mode: str
) -> ScenarioProgress:
    """« À faire », « En cours » ou « Terminé », score du premier coup et indices."""
    mine = [
        f
        for f in facts
        if (f.get("track"), f.get("scenario_id"), f.get("mode")) == (track, scenario_id, mode)
    ]
    validated = [f["step_id"] for f in mine if f.get("kind") == "step_validated"]
    quizzes = [f for f in mine if f.get("kind") == "quiz_first_attempt"]
    correct = sum(1 for f in quizzes if f.get("correct") is True)
    done = any(f.get("kind") == "scenario_completed" for f in mine)
    return ScenarioProgress(
        state="done" if done else ("in_progress" if mine else "todo"),
        steps_validated=validated,
        quiz_total=len(quizzes),
        quiz_correct=correct,
        first_try_score=round(100 * correct / len(quizzes)) if quizzes else None,
        hints=sum(1 for f in mine if f.get("kind") == "hint_opened"),
    )


def _identity(raw: dict[str, Any]) -> tuple[Any, ...]:
    try:
        return Fact.model_validate(raw).identity
    except ValueError:
        return ("invalid", repr(sorted(raw.items())))


class ProgressStore:
    """Seul écrivain de `progress.json` pour un dossier de données (verrou unique)."""

    _stores: dict[Path, ProgressStore] = {}
    _registry_lock = threading.Lock()

    def __init__(self, data_dir: Path) -> None:
        self.data_dir = data_dir
        self._lock = threading.Lock()

    @classmethod
    def for_dir(cls, data_dir: Path) -> ProgressStore:
        """Un seul magasin, donc un seul verrou, par dossier de données."""
        key = data_dir.resolve()
        with cls._registry_lock:
            found = cls._stores.get(key)
            if found is None:
                found = cls._stores[key] = cls(key)
            return found

    def facts(self) -> list[dict[str, Any]]:
        """Faits enregistrés (copie) ; aucun fichier : liste vide, sans rien créer."""
        with self._lock:
            path = self.data_dir / FILENAME
            if not path.exists():
                return []
            return list(_read_json(path).get("facts") or [])

    def submit(self, facts: list[Fact]) -> list[Fact]:
        """Ajoute les faits nouveaux ; rend ceux qui ont été ajoutés (doublons ignorés).

        Un fichier d'une version future n'est pas modifié (`FutureSchemaError`).
        """
        if not facts:
            return []
        with self._lock:
            data = ensure_progress(self.data_dir, datetime.now().astimezone())
            stored: list[dict[str, Any]] = list(data.get("facts") or [])
            seen = {_identity(f) for f in stored}
            added: list[Fact] = []
            for fact in facts:
                if fact.identity in seen:
                    continue
                seen.add(fact.identity)
                if not fact.at:
                    now = datetime.now().astimezone().isoformat(timespec="seconds")
                    fact = fact.model_copy(update={"at": now})
                added.append(fact)
                stored.append(fact.model_dump(mode="json", exclude_none=True))
            if added:
                write_json_atomic(self.data_dir / FILENAME, {**data, "facts": stored})
            return added

    def progress(self, track: str, scenario_id: str, mode: str) -> ScenarioProgress:
        """États dérivés d'un scénario (une lecture du fichier)."""
        return derive(self.facts(), track, scenario_id, mode)

    def all_progress(self) -> dict[tuple[str, str, str], ScenarioProgress]:
        """États dérivés de chaque `(parcours, scenario_id, mode)` ayant au moins un fait, en une
        lecture et un passage (accueil) ; un scénario absent est « À faire »."""
        groups: dict[tuple[str, str, str], list[dict[str, Any]]] = {}
        for raw in self.facts():
            key = (raw.get("track"), raw.get("scenario_id"), raw.get("mode"))
            if all(isinstance(part, str) for part in key):
                groups.setdefault(key, []).append(raw)  # type: ignore[arg-type]
        return {key: derive(group, *key) for key, group in groups.items()}
