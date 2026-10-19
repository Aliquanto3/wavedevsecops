"""Encart « Ce qui l'aurait bloqué » de fin de scénario B (story 5.9, AD-2, AD-7, UX-DR8).

Le scénario déclare ses barrières (`blocked_by`) ; le serveur les résout avec `content/chain.yaml`
(nom, station, livraison) et le catalogue (titre du scénario qui la joue). Une seule source dit si
une station est livrée : `delivered` de `chain.yaml`, comme le bandeau et la carte. Livrée, le
scénario est un lien ; pas encore, l'étiquette en tirets « Arrive en <milestone> » (jalon déclaré
par la station dans `chain.yaml`, « Bientôt » à défaut) remplace le lien. Le front n'écrit aucun
de ces textes.
"""

from __future__ import annotations

import logging
from typing import Any

from wavedevsecops.config import Settings, get_settings
from wavedevsecops.scenarios import Scenario, ScenarioError, load_scenario, scenario_files
from wavedevsecops.web.catalogue import load_chain_texts

log = logging.getLogger(__name__)

TITLE_TEXT = "Ce qui l'aurait bloqué"
SOON_TEXT = "Arrive en {milestone}"
SOON_FALLBACK_TEXT = "Bientôt"


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
        except (ScenarioError, OSError, UnicodeDecodeError) as error:
            log.warning("Scénario ignoré pour l'encart des barrières (%s) : %s", path.name, error)
            continue
        if scenario.catalogue and (scenario.mode == "A" or scenario.scenario_id not in titles):
            titles[scenario.scenario_id] = scenario.title_text
    return titles


def blockers_body(scenario: Scenario, settings: Settings | None = None) -> dict[str, Any] | None:
    """Encart du scénario terminé ; `None` sans déclaration ou sans chaîne lisible."""
    if not scenario.blocked_by:
        return None
    settings = settings or get_settings()
    chain = load_chain_texts(settings)
    if chain is None:
        return None
    stations = {s.number: s for s in chain.stations}
    labels = {b.id: b.label for s in chain.stations for b in s.barriers}
    titles = catalogue_scenario_titles(settings)
    items = []
    for blocker in scenario.blocked_by:
        station = stations.get(blocker.station)
        delivered = station is not None and station.delivered
        title = titles.get(blocker.scenario_id)
        if delivered and title is None:
            log.warning(
                "Encart de %s : scénario « %s » absent du catalogue, barrière sans lien",
                scenario.key,
                blocker.scenario_id,
            )
        if delivered:
            soon_text = None
        elif station is not None and station.milestone:
            soon_text = SOON_TEXT.format(milestone=station.milestone)
        else:
            soon_text = chain.map.soon_text if chain.map else SOON_FALLBACK_TEXT
        items.append(
            {
                "barrier_id": blocker.barrier_id,
                "label": labels.get(blocker.barrier_id, blocker.barrier_id),
                "station": blocker.station,
                "station_text": f"Station {blocker.station} · {station.name if station else ''}",
                "reason_text": blocker.reason_text,
                "delivered": delivered,
                "soon_text": soon_text,
                "scenario": {"id": blocker.scenario_id, "title_text": title}
                if delivered and title
                else None,
            }
        )
    return {"title_text": TITLE_TEXT, "items": items}
