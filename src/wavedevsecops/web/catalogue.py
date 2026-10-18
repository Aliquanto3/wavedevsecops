"""Catalogue (première version) et ouverture d'un espace de travail (Story 2.3).

- `GET /api/catalogue` : la section « Socle git », avec les scénarios déclarés dans
  `content/scenarios/` (titre, modes, parcours) ;
- `POST /api/open` : ouvre l'espace d'un mode (le prépare s'il n'existe pas) et rend son
  `workspace_id` ; le parcours par défaut est le parcours sans IA ;
- `GET /api/workspaces/<workspace_id>` : titre et mode du scénario d'un espace.

La Story 6.1 étend cet écran (choix du parcours, états, cartes indisponibles).
"""

from __future__ import annotations

import asyncio
import json
import logging
import threading
from concurrent.futures import Future
from typing import Any

import yaml
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response

from wavedevsecops.config import Settings, get_settings
from wavedevsecops.contracts import AppError
from wavedevsecops.engine import (
    OperationRefused,
    WorkspaceManager,
    WorkspaceNotFound,
    parse_workspace_id,
    workspace_id_for,
)
from wavedevsecops.scenarios import LoadedScenario, ScenarioError, load_scenario, scenario_files

log = logging.getLogger("wavedevsecops")

DEFAULT_TRACK = "no_ai"
"""Parcours d'ouverture par défaut : le parcours sans IA (le choix de parcours vient en 6.1)."""
SOCLE_SECTION = "socle-git"
SOCLE_TITLE = "Socle git"
SOCLE_SUBTITLE = "Les gestes git de base, dans un dépôt qui ne risque rien."


def load_chain_texts(settings: Settings | None = None) -> dict[str, Any] | None:
    """Textes de `content/chain.yaml` ; rien si le fichier manque ou est illisible (journalisé)."""
    path = (settings or get_settings()).content_path() / "chain.yaml"
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict) or not isinstance(data.get("stations"), list):
            raise ValueError("clé `stations` absente")
        return data
    except (OSError, UnicodeDecodeError, ValueError, yaml.YAMLError) as error:
        log.warning("Chaîne ignorée (%s) : %s", path.name, error)
        return None


def _map_station(station: dict[str, Any], kinds: dict[str, str]) -> dict[str, Any]:
    return {
        "number": station["number"],
        "name": station["name"],
        "text": f"Station {station['number']} · {station['name']}",
        "description": station.get("description", ""),
        "delivered": bool(station.get("delivered", True)),
        "tools": [
            {"id": t["id"], "label": t["label"], "available": bool(t.get("available", True))}
            for t in station.get("tools") or []
        ],
        "barriers": [
            {
                "id": b["id"],
                "label": b["label"],
                "links": [
                    {
                        "kind": link["kind"],
                        "kind_text": kinds.get(link["kind"], ""),
                        "label": link["label"],
                    }
                    for link in b.get("links") or []
                ],
            }
            for b in station.get("barriers") or []
        ],
    }


def chain_body(station: int | None, settings: Settings | None = None) -> dict[str, Any] | None:
    """Bandeau et carte de la chaîne (Stories 9.1 et 9.2), depuis `content/chain.yaml` (AD-2)."""
    texts = load_chain_texts(settings)
    if texts is None:
        return None
    stations = texts["stations"]
    if station is None or not 1 <= station <= len(stations):
        return None
    chain_map = texts.get("map") or {}
    kinds = chain_map.get("kinds") or {}
    return {
        "label": texts["label"],
        "current": station,
        "here_text": texts["here_text"],
        "boundary_text": texts["boundary_text"],
        "boundary_after": texts["boundary_after"],
        "stations": [_map_station(s, kinds) for s in stations],
        "map": {k: v for k, v in chain_map.items() if k != "kinds"},
    }


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


def catalogue_body(settings: Settings) -> dict[str, Any]:
    grouped: dict[str, dict[str, Any]] = {}
    for loaded in load_catalogue(settings):
        scenario = loaded.scenario
        if not scenario.catalogue or scenario.section not in (None, SOCLE_SECTION):
            continue
        entry = grouped.setdefault(
            scenario.scenario_id,
            {"scenario_id": scenario.scenario_id, "title": scenario.title_text, "modes": []},
        )
        track = default_track(loaded)
        entry["modes"].append(
            {
                "mode": scenario.mode,
                "tracks": list(scenario.tracks),
                "track": track,
                "workspace_id": workspace_id_for(track, scenario.key),
            }
        )
    scenarios = sorted(grouped.values(), key=lambda s: s["scenario_id"])
    for entry in scenarios:
        entry["modes"].sort(key=lambda m: m["mode"])
    return {
        "default_track": DEFAULT_TRACK,
        "sections": [
            {
                "key": SOCLE_SECTION,
                "title": SOCLE_TITLE,
                "subtitle": SOCLE_SUBTITLE,
                "scenarios": scenarios,
            }
        ],
    }


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
    async def catalogue() -> Response:
        return JSONResponse(await asyncio.to_thread(catalogue_body, settings))

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
        return JSONResponse(
            {
                "workspace_id": workspace_id,
                "scenario_id": scenario_id,
                "mode": mode,
                "track": track,
                "title": loaded.scenario.title_text,
                "chain": chain_body(loaded.scenario.station, settings),
            }
        )
