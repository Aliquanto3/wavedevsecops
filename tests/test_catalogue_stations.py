# ruff: noqa: E501
"""Section « Stations » du catalogue (Story 9.3) : contenu serveur et rendu sous Node."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from test_catalogue import _resolve_without
from test_catalogue_dom import CATALOGUE, NODE, _js

from wavedevsecops import toolrun
from wavedevsecops.config import Settings
from wavedevsecops.scenarios.order import SOCLE_ORDER, STATION_ORDER, catalogue_rank
from wavedevsecops.web.catalogue import catalogue_body


def test_section_stations_rangee_par_station(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(toolrun, "resolve", _resolve_without("ruff"))
    body = catalogue_body(Settings(data_dir=tmp_path / "data"), "no_ai")
    assert [s["key"] for s in body["sections"]] == ["socle-git", "stations"]
    # Le socle ne contient pas les scénarios de station.
    socle = body["sections"][0]["scenarios"]
    assert {"defaut-de-lint", "test-casse"}.isdisjoint(s["scenario_id"] for s in socle)
    stations = body["sections"][1]
    assert stations["title"] == "Stations"
    # Un groupe par station livrée, dans l'ordre des stations ; chaque story de station en
    # ajoute un sans réécrire ce test.
    groups = stations["groups"]
    numbers = [g["station"] for g in groups]
    assert numbers == sorted(set(numbers)) and numbers[0] == 1
    group = groups[0]
    assert (group["station"], group["text"]) == (1, "Station 1 · Poste local")
    lint, test, secret = group["scenarios"]
    assert [s["scenario_id"] for s in (lint, test, secret)] == list(STATION_ORDER[:3])
    # À l'intérieur de chaque station, l'ordre conseillé de STATION_ORDER.
    for g in groups:
        ids = [s["scenario_id"] for s in g["scenarios"]]
        assert ids == sorted(ids, key=STATION_ORDER.index), g["station"]
    # Station 3 (story 8.1) : l'analyse de sécurité du code.
    (security,) = [g for g in groups if g["station"] == 3]
    assert security["text"] == "Station 3 · Sécurité et qualité"
    assert "code-vulnerable" in [s["scenario_id"] for s in security["scenarios"]]
    assert lint["description"].startswith("Lancez ruff") and test["description"]
    # Un outil absent rend la carte indisponible, avec l'outil nommé.
    (lint_mode,) = lint["modes"]
    assert lint_mode["available"] is False
    assert lint_mode["unavailable"]["needs_text"] == "Nécessite ruff"
    assert test["modes"][0]["available"] is True


def test_section_stations_absente_sans_scenario_de_station(tmp_path: Path) -> None:
    content = tmp_path / "content"
    (content / "scenarios").mkdir(parents=True)
    body = catalogue_body(Settings(data_dir=tmp_path / "data", content_dir=content), "no_ai")
    assert [s["key"] for s in body["sections"]] == ["socle-git"]


def test_rang_des_stations_apres_le_socle() -> None:
    ids = ["test-casse", "bac-a-sable-libre", "defaut-de-lint", SOCLE_ORDER[0]]
    assert sorted(ids, key=catalogue_rank) == [
        SOCLE_ORDER[0],
        "bac-a-sable-libre",
        "defaut-de-lint",
        "test-casse",
    ]


STATIONS = {
    "key": "stations",
    "title": "Stations",
    "subtitle": "Une barrière à la fois.",
    "groups": [
        {
            "station": 1,
            "text": "Station 1 · Poste local",
            "scenarios": [
                {
                    "scenario_id": "defaut-de-lint",
                    "title": "Trouver un défaut de lint",
                    "description": "Lancez ruff.",
                    "modes": [
                        {"mode": "A", "track": "llm", "workspace_id": "llm.defaut-de-lint.A", "state": "in_progress", "state_text": "En cours", "detail_text": "1 indice", "available": True},
                    ],
                },
                {
                    "scenario_id": "test-casse",
                    "title": "Trouver un test cassé",
                    "description": "Lancez pytest.",
                    "modes": [
                        {
                            "mode": "A", "track": "llm", "workspace_id": "llm.test-casse.A", "state": "todo", "state_text": "À faire", "detail_text": "", "available": False,
                            "unavailable": {"text": "⊘ Indisponible", "needs_text": "Nécessite pytest", "diagnostic_text": "Voir le diagnostic", "diagnostic_path": "/diagnostic"},
                        }
                    ],
                },
            ],
        }
    ],
}


@pytest.mark.skipif(NODE is None, reason="Node absent : comportement JS non exécuté")
def test_section_stations_sous_titre_cartes_et_ligne_d_etat(tmp_path: Path) -> None:
    catalogue = {**CATALOGUE, "sections": [*CATALOGUE["sections"], STATIONS]}
    out = _js(
        tmp_path,
        f"""
const opened = [];
renderCatalogue(main, {json.dumps(catalogue)}, async (s, m) => {{ opened.push([s.scenario_id, m.mode]); }});
const cards = $$(".station-card");
$$(".station-card button[data-mode]")[0].dispatchEvent(makeEvent("click"));
console.log(JSON.stringify({{
  sections: $$(".catalogue-title").map((t) => t.textContent),
  subtitles: $$(".station-title").map((t) => t.textContent),
  titles: cards.map((c) => c.querySelector(".scenario-card-title").textContent),
  descriptions: cards.map((c) => c.querySelector(".station-card-description").textContent),
  states: cards.map((c) => c.querySelectorAll(".scenario-mode-state").length),
  first: cards[0].querySelector(".scenario-mode-state").textContent,
  off: cards[1].querySelector(".scenario-mode-state").textContent,
  link: cards[1].querySelector("a").getAttribute("href"),
  offButtons: cards[1].querySelectorAll("button").length,
  discs: $$(".scenario-disc").length,
  opened,
}}));
""",
    )
    assert out["sections"] == ["Socle git", "Stations"]
    assert out["subtitles"] == ["Station 1 · Poste local"]
    assert out["titles"] == ["Trouver un défaut de lint", "Trouver un test cassé"]
    assert out["descriptions"] == ["Lancez ruff.", "Lancez pytest."]
    assert out["states"] == [1, 1]
    assert out["first"] == "En cours · 1 indice"
    assert out["off"] == "⊘ Indisponible · Nécessite pytest · Voir le diagnostic"
    assert (out["link"], out["offButtons"], out["discs"]) == ("/diagnostic", 0, 2)
    assert out["opened"] == [["defaut-de-lint", "A"]]


def test_scenarios_de_station_livres_figurent_dans_l_ordre_conseille() -> None:
    """Garde contre la dérive de `STATION_ORDER` (revue 9.3) : un scénario de station absent de
    la liste prendrait le rang des scénarios hors ordre du socle, avant les stations connues, et
    fausserait « Scénario suivant » et l'ordre du rapport."""
    from wavedevsecops.scenarios.order import STATION_ORDER, STATIONS_SECTION
    from wavedevsecops.web.catalogue import load_catalogue

    content = Path(__file__).resolve().parents[1] / "content"
    stations = {
        loaded.scenario.scenario_id
        for loaded in load_catalogue(Settings(content_dir=content))
        if loaded.scenario.catalogue and loaded.scenario.section == STATIONS_SECTION
    }
    assert stations and stations <= set(STATION_ORDER)


@pytest.mark.skipif(NODE is None, reason="Node absent : comportement JS non exécuté")
def test_carte_de_station_reprendre_et_recommencer(tmp_path: Path) -> None:
    """Reprendre et Recommencer (Story 6.4) valent aussi pour une carte de station (revue 9.3)."""
    resume = {"can_resume": True, "step_number": 2, "step_total": 4, "text": "Étape 2 sur 4", "button_text": "Reprendre"}
    blocked = {"can_resume": False, "step_number": 0, "step_total": 4, "blocked_text": "Ce scénario ne peut pas reprendre là où vous l'aviez laissé.", "restart_text": "Recommencer"}
    group = json.loads(json.dumps(STATIONS["groups"][0]))
    group["scenarios"][0]["modes"][0]["resume"] = resume
    group["scenarios"][1]["modes"][0].update(available=True, resume=blocked)
    del group["scenarios"][1]["modes"][0]["unavailable"]
    catalogue = {**CATALOGUE, "sections": [*CATALOGUE["sections"], {**STATIONS, "groups": [group]}]}
    out = _js(
        tmp_path,
        f"""
const opened = [];
renderCatalogue(main, {json.dumps(catalogue)}, async (s, m, how) => {{ opened.push([s.scenario_id, how]); }});
const cards = $$(".station-card");
const labels = (c) => c.querySelectorAll("button").map((b) => [b.textContent, b.getAttribute("aria-label")]);
const first = labels(cards[0]);
cards[0].querySelector('button[data-action="resume"]').dispatchEvent(makeEvent("click"));
const step = cards[0].querySelector(".scenario-mode-step").textContent;
const blockedButtons = labels(cards[1]);
cards[1].querySelector('button[data-action="restart-ask"]').dispatchEvent(makeEvent("click"));
cards[1].querySelector('button[data-action="restart-confirm"]').dispatchEvent(makeEvent("click"));
await new Promise((r) => setTimeout(r, 0));
console.log(JSON.stringify({{ first, step, blockedButtons, opened }}));
""",
    )
    assert out["first"] == [
        ["Reprendre", "Reprendre Trouver un défaut de lint en mode A"],
        ["Ouvrir", "Ouvrir Trouver un défaut de lint en mode A"],
    ]
    assert out["step"] == "Étape 2 sur 4"
    assert out["blockedButtons"] == [["Recommencer", "Recommencer Trouver un test cassé en mode A"]]
    assert out["opened"] == [["defaut-de-lint", {"resume": True}], ["test-casse", {"restart": True}]]
