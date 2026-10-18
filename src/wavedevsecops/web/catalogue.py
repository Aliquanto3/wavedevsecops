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
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response

from wavedevsecops.config import Settings
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
        if scenario.section not in (None, SOCLE_SECTION):
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
    def find(scenario_id: str, mode: str) -> LoadedScenario | None:
        for loaded in load_catalogue(settings):
            if loaded.scenario.scenario_id == scenario_id and loaded.scenario.mode == mode:
                return loaded
        return None

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
            """Vrai si l'espace est en préparation, faux s'il existait déjà."""
            if manager.layout(workspace_id).root.is_dir():
                manager.get(workspace_id)
                return False
            manager.create(loaded, track)
            return True

        try:
            preparing = await asyncio.to_thread(open_it)
        except OperationRefused as refused:
            return _refusal(409, refused.reason_text)
        except AppError as error:
            return _refusal(409, f"{error.cause_text} {error.action_text}")
        return JSONResponse(
            {
                "workspace_id": workspace_id,
                "title": loaded.scenario.title_text,
                "preparing": preparing,
            },
            status_code=202 if preparing else 200,
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
        return JSONResponse(
            {
                "workspace_id": workspace_id,
                "scenario_id": scenario_id,
                "mode": mode,
                "track": track,
                "title": loaded.scenario.title_text,
            }
        )
