"""Vocabulaire de la chaîne (story 9.4, AD-2, AD-7).

`content/glossary.yaml` liste les termes ; `GET /api/glossary` les sert au front, avec pour chacun
la barrière de `content/chain.yaml` et le scénario qui la fait jouer. Une barrière sans scénario
livré se dégrade proprement : le terme et la barrière restent affichés, le scénario est « à venir ».
Un fichier absent ou invalide donne un vocabulaire vide, journalisé.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from typing import Any, Literal

import yaml
from fastapi import FastAPI
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from wavedevsecops.config import Settings, get_settings
from wavedevsecops.contracts import AppError
from wavedevsecops.engine import workspace_id_for
from wavedevsecops.progress.facts import ProgressStore
from wavedevsecops.web.catalogue import load_catalogue, load_chain_texts

log = logging.getLogger(__name__)

FILE_NAME = "glossary.yaml"


class _Strict(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class GlossaryUi(_Strict):
    see_text: str
    barrier_title: str
    play_text: str
    soon_text: str
    named_only_text: str
    none_text: str
    close_text: str


class GlossaryTerm(_Strict):
    id: str = Field(pattern=r"^[a-z0-9-]+$")
    term_text: str = Field(min_length=1)
    definition_text: str = Field(min_length=1)
    barrier_id: str = ""
    scenario_id: str = ""
    named_only: bool = False
    trace_text: str = ""
    trace_link_text: str = ""
    """Libellé du lien vers les PR et les checks de l'espace ouvert (story 9.6)."""
    trace_none_text: str = ""
    """Phrase sans espace ouvert : jamais de lien mort, elle invite à ouvrir un scénario."""

    @model_validator(mode="after")
    def _coherent(self) -> GlossaryTerm:
        parts = (self.trace_text, self.trace_link_text, self.trace_none_text)
        if any(parts) and not all(parts):
            raise ValueError(
                f"{self.id} : trace_text, trace_link_text et trace_none_text vont ensemble"
            )
        if self.named_only and (self.barrier_id or self.scenario_id or self.trace_text):
            raise ValueError(f"{self.id} : un terme nommé seulement ne mène à rien")
        if self.scenario_id and not self.barrier_id:
            raise ValueError(f"{self.id} : un scénario suppose une barrière")
        return self


class Glossary(_Strict):
    schema_version: Literal[1]
    ui: GlossaryUi
    terms: list[GlossaryTerm] = Field(min_length=1)

    @model_validator(mode="after")
    def _unique(self) -> Glossary:
        ids = [t.id for t in self.terms]
        duplicates = sorted({i for i in ids if ids.count(i) > 1})
        if duplicates:
            raise ValueError(f"termes en double : {duplicates}")
        return self


def load_glossary(settings: Settings | None = None) -> Glossary | None:
    """Vocabulaire validé ; rien s'il manque ou est invalide (journalisé)."""
    path = (settings or get_settings()).content_path() / FILE_NAME
    try:
        return Glossary.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))
    except ValidationError as error:
        log.warning("Vocabulaire ignoré (%s) : contenu invalide (%s)", path.name, error)
    except (OSError, UnicodeDecodeError, yaml.YAMLError) as error:
        log.warning("Vocabulaire ignoré (%s) : %s", path.name, error)
    return None


def _barriers(settings: Settings) -> dict[str, dict[str, Any]]:
    chain = load_chain_texts(settings)
    if chain is None:
        return {}
    return {
        b.id: {
            "id": b.id,
            "label": b.label,
            "station": s.number,
            "station_text": f"Station {s.number} · {s.name}",
            "delivered": s.delivered,
        }
        for s in chain.stations
        for b in s.barriers
    }


def open_station_workspace(
    settings: Settings, workspace_exists: Callable[[str], bool]
) -> str | None:
    """Espace du dernier scénario de station ouvert, s'il existe encore sur disque.

    Seul un scénario de station qui passe par le pipeline (`pipeline: true`) a des PR et des checks
    à montrer ; un scénario du socle, un scénario de station sans pipeline (poste local, push
    direct), un espace disparu ou un `progress.json` illisible ne donnent pas de lien (jamais de
    lien mort, et la page Vocabulaire reste servie).
    """
    try:
        last = ProgressStore.for_dir(settings.resolved_data_dir()).last_opened()
        if last is None:
            return None
        track, scenario_id, mode = last
        for loaded in load_catalogue(settings):
            scenario = loaded.scenario
            if scenario.catalogue and scenario.scenario_id == scenario_id and scenario.mode == mode:
                if not (scenario.station and scenario.pipeline):
                    return None
                workspace_id = workspace_id_for(track, scenario.key)
                return workspace_id if workspace_exists(workspace_id) else None
    except AppError as exc:  # progress.json illisible, parcours ou identifiant invalide
        log.warning("glossaire : espace ouvert introuvable (%s)", exc)
    return None


TRACE_PANE = "remote"
"""Vue que le lien « traçabilité » montre à l'ouverture de l'espace (paramètre `vue`)."""


def _trace(term: GlossaryTerm, open_workspace: str | None) -> dict[str, Any] | None:
    if not term.trace_text:
        return None
    if open_workspace:
        # `?vue=remote` : l'espace s'ouvre sur la vue Distant + PR (ses PR et ses checks).
        href = f"/espace/{open_workspace}?vue={TRACE_PANE}"
        return {"link": {"href": href, "text": term.trace_link_text}}
    return {"link": None, "none_text": term.trace_none_text}


def glossary_body(
    settings: Settings | None = None, open_workspace: str | None = None
) -> dict[str, Any]:
    """Termes, barrière et scénario résolus ; sans fichier valide, une liste vide.

    `open_workspace` : espace de station ouvert ; il donne au terme de traçabilité son lien."""
    settings = settings or get_settings()
    glossary = load_glossary(settings)
    if glossary is None:
        return {"schema_version": 1, "ui": None, "terms": []}
    barriers = _barriers(settings)
    titles: dict[str, str] = {}
    if any(t.scenario_id for t in glossary.terms):
        for loaded in load_catalogue(settings):
            scenario = loaded.scenario
            if scenario.catalogue:
                titles.setdefault(scenario.scenario_id, scenario.title_text)
    terms = []
    for term in glossary.terms:
        barrier = barriers.get(term.barrier_id) if term.barrier_id else None
        if term.barrier_id and barrier is None:
            log.warning("Terme %s : barrière %s inconnue de la chaîne", term.id, term.barrier_id)
        title = titles.get(term.scenario_id) if barrier else None
        if term.scenario_id and titles and term.scenario_id not in titles:
            log.warning("Terme %s : scénario %s absent du catalogue", term.id, term.scenario_id)
        terms.append(
            {
                "id": term.id,
                "term_text": term.term_text,
                "definition_text": term.definition_text,
                "named_only": term.named_only,
                "trace_text": term.trace_text,
                "trace": _trace(term, open_workspace),
                "barrier": barrier,
                "scenario": (
                    {
                        "id": term.scenario_id,
                        "title_text": title,
                        "play_text": glossary.ui.play_text.format(name=title),
                    }
                    if title
                    else None
                ),
            }
        )
    return {"schema_version": 1, "ui": glossary.ui.model_dump(), "terms": terms}


def install_glossary_routes(app: FastAPI, settings: Settings, manager: Any = None) -> None:
    def exists(workspace_id: str) -> bool:
        return manager is not None and manager.layout(workspace_id).root.is_dir()

    def build() -> dict[str, Any]:
        return glossary_body(settings, open_station_workspace(settings, exists))

    @app.get("/api/glossary")
    async def glossary() -> Response:
        body = await asyncio.to_thread(build)
        return JSONResponse(body, headers={"Cache-Control": "no-store"})
