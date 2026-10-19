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
from wavedevsecops.scenarios.order import SOCLE_ORDER, catalogue_rank
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
    (group,) = stations["groups"]
    assert (group["station"], group["text"]) == (1, "Station 1 · Poste local")
    lint, test = group["scenarios"]
    assert (lint["scenario_id"], test["scenario_id"]) == ("defaut-de-lint", "test-casse")
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
