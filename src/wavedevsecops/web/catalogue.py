"""Catalogue (première version) et ouverture d'un espace de travail (Story 2.3).

- `GET /api/catalogue[?track=<parcours>]` : sans parcours, seulement le choix du parcours
  (`path-picker`) ; avec un parcours, la section « Socle git » dans l'ordre conseillé (FR-9),
  l'état de chaque mode dérivé par `progress` (AD-14) et l'indisponibilité par outil (AD-16) ;
- `POST /api/open` : ouvre l'espace d'un mode (le prépare s'il n'existe pas) et rend son
  `workspace_id` ; refuse un mode indisponible ; le parcours par défaut est le parcours sans IA ;
- `GET /api/workspaces/<workspace_id>` : titre et mode du scénario d'un espace.

Contrat du catalogue (Story 6.1) : voir `6-1-choisir-son-parcours-et-parcourir-le-catalogue.md`.
"""

from __future__ import annotations

import asyncio
import json
import logging
import threading
from concurrent.futures import Future
from typing import Any, Literal

import yaml
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from wavedevsecops import diagnostic, toolrun
from wavedevsecops.config import Settings, get_settings
from wavedevsecops.contracts import AppError
from wavedevsecops.engine import (
    OperationRefused,
    WorkspaceManager,
    WorkspaceNotFound,
    parse_workspace_id,
    workspace_id_for,
)
from wavedevsecops.progress.facts import ProgressStore, ScenarioProgress
from wavedevsecops.scenarios import LoadedScenario, ScenarioError, load_scenario, scenario_files
from wavedevsecops.web.shell import TRACKS, track_options

log = logging.getLogger("wavedevsecops")

DEFAULT_TRACK = "no_ai"
"""Parcours d'ouverture par défaut : le parcours sans IA (le choix de parcours vient en 6.1)."""
SOCLE_SECTION = "socle-git"
SOCLE_TITLE = "Socle git"
SOCLE_SUBTITLE = "Les gestes git de base, dans un dépôt qui ne risque rien."
SOCLE_ORDER: tuple[str, ...] = (
    "add-commit",
    "push-pull",
    "branche",
    "pr-merge",
    "conflit",
    "stash",
    "rebase",
    "recuperation",
)
"""Ordre conseillé du socle git (FR-9), par `scenario_id`. Un identifiant qui n'est pas encore
livré est simplement absent du catalogue ; un scénario déclaré mais absent de cette liste vient
après, par ordre alphabétique."""
PICKER_QUESTION = (
    "Choisissez votre parcours. Les deux suivent la même progression ; "
    "seul le code d'exercice change."
)
STATE_TEXTS = {"todo": "À faire", "in_progress": "En cours", "done": "Terminé"}
UNAVAILABLE_TEXT = "⊘ Indisponible"
DIAGNOSTIC_TEXT = "Voir le diagnostic"
DIAGNOSTIC_PATH = "/diagnostic"


class _ChainModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


LinkKind = Literal["check", "hook", "term"]


class ChainLink(_ChainModel):
    kind: LinkKind
    label: str


class ChainBarrier(_ChainModel):
    id: str
    label: str
    links: list[ChainLink] = []


class ChainTool(_ChainModel):
    """Outil de `tools.toml` : sa disponibilité vient de `toolrun.resolve`, pas du contenu."""

    id: str
    label: str


class ChainStation(_ChainModel):
    number: int
    name: str
    description: str = ""
    delivered: bool = True
    tools: list[ChainTool] = []
    barriers: list[ChainBarrier] = []


class ChainMapTexts(_ChainModel):
    button_text: str
    button_label: str
    title: str
    soon_text: str
    unavailable_text: str
    tools_title: str
    barriers_title: str
    links_title: str
    none_selected: str
    kinds: dict[LinkKind, str]


class ChainTexts(_ChainModel):
    """Schéma de `content/chain.yaml` (AD-2)."""

    schema_version: Literal[1]
    label: str
    here_text: str
    boundary_text: str
    boundary_after: int
    map: ChainMapTexts | None = None
    stations: list[ChainStation] = Field(min_length=1)

    @model_validator(mode="after")
    def _coherent(self) -> ChainTexts:
        numbers = [s.number for s in self.stations]
        if numbers != list(range(1, len(numbers) + 1)):
            raise ValueError(f"stations numérotées {numbers}, attendu 1 à {len(numbers)}")
        if not 1 <= self.boundary_after < len(numbers):
            raise ValueError(f"boundary_after={self.boundary_after} hors des stations")
        if self.map is not None:
            used = {link.kind for s in self.stations for b in s.barriers for link in b.links}
            missing = sorted(used - set(self.map.kinds))
            if missing:
                raise ValueError(f"map.kinds sans libellé pour {missing}")
        return self


def _validation_text(error: ValidationError) -> str:
    return "; ".join(
        f"{'.'.join(str(part) for part in item['loc']) or 'racine'} : {item['msg']}"
        for item in error.errors()
    )


def load_chain_texts(settings: Settings | None = None) -> ChainTexts | None:
    """Contenu validé de `content/chain.yaml` ; rien s'il manque ou est invalide (journalisé)."""
    path = (settings or get_settings()).content_path() / "chain.yaml"
    try:
        return ChainTexts.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))
    except ValidationError as error:
        log.warning(
            "Chaîne ignorée (%s) : contenu invalide (%s)", path.name, _validation_text(error)
        )
    except (OSError, UnicodeDecodeError, yaml.YAMLError) as error:
        log.warning("Chaîne ignorée (%s) : %s", path.name, error)
    return None


def _map_station(
    station: ChainStation, kinds: dict[str, str], settings: Settings | None
) -> dict[str, Any]:
    return {
        "number": station.number,
        "name": station.name,
        "text": f"Station {station.number} · {station.name}",
        "description": station.description,
        "delivered": station.delivered,
        "tools": [
            # Disponibilité réelle sur le poste (registre `tools.toml`, sonde du diagnostic).
            {"id": t.id, "label": t.label, "available": toolrun.resolve(t.id, settings).ok}
            for t in station.tools
        ],
        "barriers": [
            {
                "id": b.id,
                "label": b.label,
                "links": [
                    {"kind": link.kind, "kind_text": kinds.get(link.kind, ""), "label": link.label}
                    for link in b.links
                ],
            }
            for b in station.barriers
        ],
    }


def chain_body(station: int | None, settings: Settings | None = None) -> dict[str, Any] | None:
    """Bandeau et carte de la chaîne (Stories 9.1 et 9.2), depuis `content/chain.yaml` (AD-2).

    Lit le disque et sonde les outils : à appeler hors de la boucle d'événements.
    """
    if station is None:
        return None
    texts = load_chain_texts(settings)
    if texts is None or not 1 <= station <= len(texts.stations):
        return None
    chain_map = texts.map
    kinds: dict[str, str] = dict(chain_map.kinds) if chain_map else {}
    body: dict[str, Any] = {
        "label": texts.label,
        "current": station,
        "here_text": texts.here_text,
        "boundary_text": texts.boundary_text,
        "boundary_after": texts.boundary_after,
        "stations": [_map_station(s, kinds, settings) for s in texts.stations],
    }
    if chain_map is not None:
        body["map"] = chain_map.model_dump(exclude={"kinds"})
    return body


def _refusal(status: int, reason_text: str) -> JSONResponse:
    return JSONResponse({"reason_text": reason_text}, status_code=status)


def load_catalogue(settings: Settings) -> list[LoadedScenario]:
    """Scénarios lisibles de `content/scenarios/` ; un fichier invalide est ignoré et journalisé."""
    found: list[LoadedScenario] = []
    for path in scenario_files(settings):
        try:
            found.append(load_scenario(path, settings))
        except (ScenarioError, OSError, UnicodeDecodeError) as error:
            log.warning("Scénario ignoré (%s) : %s", path.name, error)
    return found


def default_track(loaded: LoadedScenario) -> str:
    tracks = loaded.scenario.tracks
    return DEFAULT_TRACK if DEFAULT_TRACK in tracks else tracks[0]


def _hint_text(count: int) -> str:
    return f"{count} indice" + ("s" if count > 1 else "")


def detail_text(progress: ScenarioProgress) -> str:
    """« n sur m du premier coup · k indice(s) » ; rien tant que le scénario n'est pas commencé."""
    if progress.state == "todo":
        return ""
    parts = []
    if progress.quiz_total:
        parts.append(f"{progress.quiz_correct} sur {progress.quiz_total} du premier coup")
    parts.append(_hint_text(progress.hints))
    return " · ".join(parts)


def _missing_tool(
    tools: list[str], settings: Settings, cache: dict[str, bool], labels: dict[str, str]
) -> tuple[str, str] | None:
    """Premier outil requis absent ou trop ancien : `(identifiant, libellé)` (AD-16)."""
    for tool_id in tools:
        if tool_id not in cache:
            cache[tool_id] = toolrun.resolve(tool_id, settings).ok
        if not cache[tool_id]:
            return tool_id, labels.get(tool_id, tool_id)
    return None


def _socle_rank(scenario_id: str) -> tuple[int, str]:
    if scenario_id in SOCLE_ORDER:
        return SOCLE_ORDER.index(scenario_id), scenario_id
    return len(SOCLE_ORDER), scenario_id


def catalogue_body(settings: Settings, track: str | None = None) -> dict[str, Any]:
    """Catalogue du `track` choisi ; sans parcours, seulement le choix du parcours.

    Lit le disque et sonde les outils : à appeler hors de la boucle d'événements.
    """
    body: dict[str, Any] = {
        "default_track": DEFAULT_TRACK,
        "track": track,
        "tracks": track_options(),
        "picker": {"question": PICKER_QUESTION},
        "sections": [],
    }
    if track is None:
        return body
    progress = ProgressStore.for_dir(settings.resolved_data_dir()).all_progress()
    try:
        tool_texts = diagnostic.load_texts(settings).get("tools", {})
    except (OSError, UnicodeDecodeError, yaml.YAMLError, AttributeError) as error:
        log.warning("Libellés d'outils illisibles (%s) : identifiants utilisés", error)
        tool_texts = {}
    labels = {k: v.get("label", k) for k, v in tool_texts.items() if isinstance(v, dict)}
    probed: dict[str, bool] = {}
    grouped: dict[str, dict[str, Any]] = {}
    for loaded in load_catalogue(settings):
        scenario = loaded.scenario
        if not scenario.catalogue or scenario.section not in (None, SOCLE_SECTION):
            continue
        if track not in scenario.tracks:
            continue
        entry = grouped.setdefault(
            scenario.scenario_id,
            {"scenario_id": scenario.scenario_id, "title": scenario.title_text, "modes": []},
        )
        done = progress.get((track, scenario.scenario_id, scenario.mode))
        state = done.state if done else "todo"
        missing = _missing_tool(list(scenario.tools), settings, probed, labels)
        mode: dict[str, Any] = {
            "mode": scenario.mode,
            "tracks": list(scenario.tracks),
            "track": track,
            "workspace_id": workspace_id_for(track, scenario.key),
            "state": state,
            "state_text": STATE_TEXTS[state],
            "detail_text": detail_text(done) if done else "",
            "available": missing is None,
        }
        if missing is not None:
            mode["unavailable"] = {
                "tool_id": missing[0],
                "tool_label": missing[1],
                "text": UNAVAILABLE_TEXT,
                "needs_text": f"Nécessite {missing[1]}",
                "diagnostic_text": DIAGNOSTIC_TEXT,
                "diagnostic_path": DIAGNOSTIC_PATH,
            }
        entry["modes"].append(mode)
    scenarios = sorted(grouped.values(), key=lambda s: _socle_rank(s["scenario_id"]))
    for number, entry in enumerate(scenarios, start=1):
        entry["number"] = number
        entry["modes"].sort(key=lambda m: m["mode"])
    body["sections"] = [
        {
            "key": SOCLE_SECTION,
            "title": SOCLE_TITLE,
            "subtitle": SOCLE_SUBTITLE,
            "scenarios": scenarios,
        }
    ]
    return body


def install_catalogue_routes(app: FastAPI, manager: WorkspaceManager, settings: Settings) -> None:
    open_lock = threading.Lock()
    preparing: dict[str, Future[Any]] = {}  # setup en cours, par espace

    def find(scenario_id: str, mode: str) -> LoadedScenario | None:
        for loaded in load_catalogue(settings):
            scenario = loaded.scenario
            if scenario.catalogue and scenario.scenario_id == scenario_id and scenario.mode == mode:
                return loaded
        return None

    def known(workspace_id: str) -> bool:
        """Vrai si l'espace existe sur disque ou si son `setup` est en cours."""
        with open_lock:
            pending = preparing.get(workspace_id)
            if pending is not None and not pending.done():
                return True
        return manager.layout(workspace_id).root.is_dir()

    @app.get("/api/catalogue")
    async def catalogue(track: str | None = None) -> Response:
        if track is not None and track not in {key for key, _, _ in TRACKS}:
            return _refusal(422, "Ce parcours n'existe pas. Choisissez-en un dans la liste.")
        return JSONResponse(await asyncio.to_thread(catalogue_body, settings, track))

    @app.post("/api/open")
    async def open_workspace(request: Request) -> Response:
        try:
            body = json.loads((await request.body()).decode("utf-8") or "{}")
            scenario_id, mode = str(body["scenario_id"]), str(body["mode"])
        except UnicodeDecodeError, json.JSONDecodeError, KeyError, TypeError:
            return _refusal(422, "La demande d'ouverture est illisible. Rechargez la page.")
        loaded = await asyncio.to_thread(find, scenario_id, mode)
        if loaded is None:
            return _refusal(404, "Ce scénario n'existe pas. Revenez au catalogue.")
        track = body.get("track") or default_track(loaded)
        if track not in loaded.scenario.tracks:
            return _refusal(422, "Ce scénario n'est pas proposé dans ce parcours.")
        missing = await asyncio.to_thread(
            _missing_tool, list(loaded.scenario.tools), settings, {}, {}
        )
        if missing is not None:
            return _refusal(
                409,
                f"Ce scénario nécessite {missing[0]}, qui manque sur ce poste. "
                "Ouvrez le diagnostic pour voir quoi faire.",
            )
        workspace_id = workspace_id_for(track, loaded.scenario.key)

        def open_it() -> bool:
            """Vrai si l'espace est en préparation, faux s'il existait déjà.

            Vérifier puis créer se fait sous verrou, et un `setup` encore en cours compte comme
            une préparation : un double clic ne lance qu'un `setup`.
            """
            with open_lock:
                pending = preparing.get(workspace_id)
                if pending is not None and not pending.done():
                    return True
                preparing.pop(workspace_id, None)
                if manager.layout(workspace_id).root.is_dir():
                    manager.get(workspace_id)
                    return False
                _engine, future = manager.create(loaded, track)
                preparing[workspace_id] = future
                return True

        try:
            is_preparing = await asyncio.to_thread(open_it)
        except OperationRefused as refused:
            return _refusal(409, refused.reason_text)
        except AppError as error:
            return _refusal(409, f"{error.cause_text} {error.action_text}")
        return JSONResponse(
            {
                "workspace_id": workspace_id,
                "title": loaded.scenario.title_text,
                "preparing": is_preparing,
            },
            status_code=202 if is_preparing else 200,
        )

    @app.get("/api/workspaces/{workspace_id}")
    async def workspace_info(workspace_id: str) -> Response:
        try:
            track, scenario_id, mode = parse_workspace_id(workspace_id)
        except WorkspaceNotFound as missing:
            return _refusal(404, f"{missing.cause_text} {missing.action_text}")
        loaded = await asyncio.to_thread(find, scenario_id, mode)
        if loaded is None:
            return _refusal(404, "Ce scénario n'existe pas. Revenez au catalogue.")
        if not await asyncio.to_thread(known, workspace_id):
            return _refusal(404, "Cet espace n'a pas encore été ouvert. Revenez au catalogue.")
        chain = await asyncio.to_thread(chain_body, loaded.scenario.station, settings)
        return JSONResponse(
            {
                "workspace_id": workspace_id,
                "scenario_id": scenario_id,
                "mode": mode,
                "track": track,
                "title": loaded.scenario.title_text,
                "chain": chain,
            }
        )
