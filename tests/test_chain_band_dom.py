# ruff: noqa: E501
"""Bandeau de la chaîne (Story 9.1) exécuté sous Node, sur la doublure de DOM de l'espace de travail."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from test_workspace_dom import NODE, _js

pytestmark = pytest.mark.skipif(NODE is None, reason="Node absent : comportement JS non exécuté")

CHAIN = {
    "label": "Chaîne de livraison",
    "current": 2,
    "here_text": "Vous êtes ici",
    "boundary_text": "CI | CD",
    "boundary_after": 3,
    "stations": [
        {"number": 1, "name": "Poste local", "text": "Station 1 · Poste local"},
        {"number": 2, "name": "PR et CI", "text": "Station 2 · PR et CI"},
        {"number": 3, "name": "Sécurité et qualité", "text": "Station 3 · Sécurité et qualité"},
        {"number": 4, "name": "Livraison", "text": "Station 4 · Livraison"},
    ],
}


def test_bandeau_station_courante_frontiere_et_aucune_vue_masquee(tmp_path: Path) -> None:
    out = _js(
        tmp_path,
        f"""
const chain = {json.dumps(CHAIN)};
const first = mount();
const bare = {{ band: $$(".chain-band").length, shown: shown(), cls: $(".workspace").className,
  menu: $$(".pane-menu-item").map((i) => i.dataset.pane), zones: $$("[data-zone]").map((z) => z.dataset.zone) }};
first.destroy();
// `destroy` ne retire pas le menu Volets de l'en-tête (montage unique par page) : on le retire ici.
$("#pane-menu").remove();
main.replaceChildren();
mountWorkspace(main, {{ title: "Bac à sable libre", store, storage, chain }});
const items = [...$(".chain-stations").children];
console.log(JSON.stringify({{
  bare,
  mainChildren: [...main.children].map((c) => c.className),
  order: [...$(".workspace").children].map((c) => c.className),
  label: $(".chain-band").getAttribute("aria-label"),
  items: items.map((i) => i.textContent),
  hidden: items.map((i) => i.getAttribute("aria-hidden")),
  describedby: items.map((i) => i.getAttribute("aria-describedby")),
  boundaryId: $(".chain-boundary").id,
  current: $$("[aria-current]").map((c) => [c.dataset.station, c.getAttribute("aria-current"), c.className]),
  pill: $$(".chain-here").map((p) => p.textContent),
  bandInsideViews: $(".views").querySelectorAll(".chain-band").length,
  shown: shown(),
  menu: $$(".pane-menu-item").map((i) => i.dataset.pane),
  workspaceClass: $(".workspace").className,
  zones: $$("[data-zone]").map((z) => z.dataset.zone),
}}));
""",
    )
    assert out["bare"]["band"] == 0 and "has-chain-band" not in out["bare"]["cls"]
    # Le bandeau est la première rangée de la grille de l'espace, avant le panneau et les vues.
    assert out["mainChildren"] == [out["workspaceClass"]]
    assert out["order"][0] == "chain-band" and len(out["order"]) == 3
    assert out["label"] == "Chaîne de livraison"
    assert out["items"] == [
        "Station 1 · Poste local",
        "Station 2 · PR et CI Vous êtes ici",
        "Station 3 · Sécurité et qualité",
        "CI | CD",
        "Station 4 · Livraison",
    ]
    # La frontière n'est pas comptée comme une station ; elle décrit la Station 4.
    assert out["hidden"] == [None, None, None, "true", None]
    assert out["describedby"] == [None, None, None, None, out["boundaryId"]]
    assert out["boundaryId"] == "chain-boundary"
    assert out["current"] == [["2", "step", "chain-station is-current"]]
    assert out["pill"] == ["Vous êtes ici"]
    # Aucune vue masquée ni déplacée ; menu Volets et zones F6 identiques au montage sans bandeau.
    assert out["bandInsideViews"] == 0
    assert out["shown"] == out["bare"]["shown"] and out["shown"]
    assert out["menu"] == out["bare"]["menu"] and out["menu"]
    assert out["zones"] == out["bare"]["zones"] and out["zones"]
    assert "has-chain-band" in out["workspaceClass"]


def test_sans_station_pas_de_bandeau(tmp_path: Path) -> None:
    out = _js(
        tmp_path,
        """
main.replaceChildren();
mountWorkspace(main, { title: "Bac", store, storage, chain: null });
console.log(JSON.stringify({ bands: $$(".chain-band").length, first: main.children[0].className, inner: main.children[0].children[0].className }));
""",
    )
    assert out == {"bands": 0, "first": "workspace", "inner": "scenario-panel"}
