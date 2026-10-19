"""Encart « Ce qui l'aurait bloqué » de fin de scénario B (story 5.9, AD-2, AD-7, UX-DR8).

Le scénario déclare ses barrières (`blocked_by`) ; le serveur les résout avec `content/chain.yaml`
(nom, station) et le catalogue (titre du scénario qui la joue), et décide, d'après le jalon
courant (`web/shell.py`), si la station est livrée : livrée, le scénario est un lien ; pas encore,
l'étiquette en tirets « Arrive en vX.Y » remplace le lien. Le front n'écrit aucun de ces textes.
"""

from __future__ import annotations

from typing import Any

from wavedevsecops.config import Settings, get_settings
from wavedevsecops.scenarios import Scenario, ScenarioError, load_scenario, scenario_files
from wavedevsecops.web.catalogue import load_chain_texts
from wavedevsecops.web.shell import CURRENT_MILESTONE, STATION_MILESTONES, station_delivered

TITLE_TEXT = "Ce qui l'aurait bloqué"
SOON_TEXT = "Arrive en {milestone}"


def chain_barriers(settings: Settings | None = None) -> dict[str, int]:
    """Barrière de `content/chain.yaml` -> numéro de sa station (lint de `blocked_by`)."""
    chain = load_chain_texts(settings)
    if chain is None:
        return {}
    return {b.id: s.number for s in chain.stations for b in s.barriers}


def catalogue_scenario_titles(settings: Settings) -> dict[str, str]:
    """Titre de chaque scénario du catalogue (mode A d'abord), par `scenario_id`."""
    titles: dict[str, str] = {}
    for path in scenario_files(settings):
        try:
            scenario = load_scenario(path, settings).scenario
        except ScenarioError, OSError, UnicodeDecodeError:
            continue
        if scenario.catalogue and (scenario.mode == "A" or scenario.scenario_id not in titles):
            titles[scenario.scenario_id] = scenario.title_text
    return titles


def blockers_body(
    scenario: Scenario, settings: Settings | None = None, milestone: str = CURRENT_MILESTONE
) -> dict[str, Any] | None:
    """Encart du scénario terminé ; `None` sans déclaration ou sans chaîne lisible."""
    if not scenario.blocked_by:
        return None
    settings = settings or get_settings()
    chain = load_chain_texts(settings)
    if chain is None:
        return None
    labels = {b.id: (b.label, s.name) for s in chain.stations for b in s.barriers}
    titles = catalogue_scenario_titles(settings)
    items = []
    for blocker in scenario.blocked_by:
        label, station_name = labels.get(blocker.barrier_id, (blocker.barrier_id, ""))
        delivered = station_delivered(blocker.station, milestone)
        title = titles.get(blocker.scenario_id)
        items.append(
            {
                "barrier_id": blocker.barrier_id,
                "label": label,
                "station": blocker.station,
                "station_text": f"Station {blocker.station} · {station_name}",
                "reason_text": blocker.reason_text,
                "delivered": delivered,
                "soon_text": None
                if delivered
                else SOON_TEXT.format(milestone=STATION_MILESTONES.get(blocker.station, "?")),
                "scenario": {"id": blocker.scenario_id, "title_text": title}
                if delivered and title
                else None,
            }
        )
    return {"title_text": TITLE_TEXT, "items": items}
