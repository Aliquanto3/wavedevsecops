# ruff: noqa: E501
"""Bandeau de la chaîne (Story 9.1) exécuté sous Node, sur la doublure de DOM de l'espace de travail."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from test_workspace_dom import MINIDOM, NODE, _js

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


MAP_CHAIN = {
    **CHAIN,
    "map": {
        "button_text": "Carte ▾",
        "button_label": "Carte de la chaîne",
        "title": "Carte de la chaîne",
        "soon_text": "Bientôt",
        "unavailable_text": "indisponible",
        "tools_title": "Outils",
        "barriers_title": "Barrières",
        "links_title": "Liée à",
        "none_selected": "Sélectionnez une barrière.",
    },
}
MAP_CHAIN["stations"] = [
    {
        **s,
        "description": f"Description {s['number']}",
        "delivered": s["number"] != 4,
        "tools": []
        if s["number"] == 4
        else [
            {"id": "a", "label": "outil-a", "available": True},
            {"id": "b", "label": "outil-b", "available": s["number"] != 3},
        ],
        "barriers": []
        if s["number"] == 4
        else [
            {
                "id": f"b{s['number']}",
                "label": f"Barrière {s['number']}",
                "links": [
                    {"kind": "hook", "kind_text": "Hook", "label": "pre-commit"},
                    {"kind": "term", "kind_text": "Terme", "label": "Secret"},
                ],
            },
        ],
    }
    for s in CHAIN["stations"]
]


def test_carte_depliee_clavier_souris_echap_focus_et_inert(tmp_path: Path) -> None:
    out = _js(
        tmp_path,
        f"""
const chain = {json.dumps(MAP_CHAIN)};
main.replaceChildren();
mountWorkspace(main, {{ title: "Bac", store, storage, chain }});
const {{ makeEvent }} = await import("{MINIDOM}");
const toggle = $("#chain-map-toggle"), map = $("#chain-map");
const state = () => ({{
  expanded: toggle.getAttribute("aria-expanded"), hidden: map.hidden,
  inert: [$(".scenario-panel"), $(".views")].map((n) => n.hasAttribute("inert")),
  focus: document.activeElement.id || document.activeElement.className,
}});
const r = {{ controls: toggle.getAttribute("aria-controls"), mapId: map.id, closed: state() }};
// Souris : « Carte ▾ » déplie ; le focus va sur la station courante.
toggle.click();
r.openByButton = state();
// Échap ferme et rend le focus au bouton.
press("Escape");
r.afterEscape = state();
// Une station du bandeau déplie la carte et le focus va sur SA zone.
$('[data-station="3"] .chain-station-open').click();
r.openByStation = state();
// Clic sur une autre station alors qu'elle est ouverte : le focus change, la carte reste ouverte.
$('[data-station="1"] .chain-station-open').click();
r.refocus = state();
// Clavier : Entrée sur un bouton se traduit par un clic ; la barrière lie checks, hooks et termes.
const barrier = $('[data-barrier="b2"]');
barrier.click();
r.pressed = $$(".chain-barrier-btn").map((b) => b.getAttribute("aria-pressed"));
r.detail = $$(".chain-link").map((l) => l.textContent);
r.detailTitle = $(".chain-detail-title").textContent;
// Survol.
$('[data-barrier="b1"]').dispatchEvent(makeEvent("mouseenter"));
r.hover = $$(".chain-link").length + ":" + $(".chain-detail-title").textContent;
// « Carte ▾ » referme.
toggle.click();
r.toggledOff = state();
// Contenu : zones, outils en tirets, Station 4 « Bientôt ».
toggle.click();
r.zones = $$(".chain-zone").map((z) => z.querySelector(".chain-zone-title").textContent);
r.soon = $$(".chain-soon").map((s) => [s.textContent, s.className]);
r.dashedTools = $$(".chain-tool.is-dashed").map((t) => t.textContent);
r.station4 = [$('.chain-zone[data-station="4"] .chain-tool'), $('.chain-zone[data-station="4"] .chain-barrier')].map((n) => n === null);
r.current = $$("[aria-current]").map((c) => c.dataset.station);
// Échap dans le menu Affichage n'est pas géré ici ; Échap ferme bien même depuis une barrière.
barrier.focus();
press("Escape");
r.escapeFromNode = state();
console.log(JSON.stringify(r));
""",
    )
    assert out["controls"] == out["mapId"] == "chain-map"
    assert out["closed"]["expanded"] == "false" and out["closed"]["hidden"] is True
    assert out["closed"]["inert"] == [False, False]
    assert not out["closed"]["focus"].startswith("chain-zone")
    assert out["openByButton"] == {
        "expanded": "true",
        "hidden": False,
        "inert": [True, True],
        "focus": "chain-zone-2-title",
    }
    assert out["afterEscape"]["expanded"] == "false" and out["afterEscape"]["hidden"] is True
    assert (
        out["afterEscape"]["inert"] == [False, False]
        and out["afterEscape"]["focus"] == "chain-map-toggle"
    )
    assert (
        out["openByStation"]["focus"] == "chain-zone-3-title"
        and out["openByStation"]["expanded"] == "true"
    )
    assert out["refocus"]["focus"] == "chain-zone-1-title" and out["refocus"]["inert"] == [
        True,
        True,
    ]
    assert out["pressed"] == ["false", "true", "false"]
    assert out["detail"] == ["Hook : pre-commit", "Terme : Secret"]
    assert out["detailTitle"] == "Barrière 2 — Liée à"
    assert out["hover"] == "2:Barrière 1 — Liée à"
    assert out["toggledOff"]["expanded"] == "false" and out["toggledOff"]["inert"] == [False, False]
    assert out["zones"] == [
        s["text"] + ("" if s["number"] != 4 else " Bientôt") for s in MAP_CHAIN["stations"]
    ]
    assert out["soon"] == [["Bientôt", "chain-soon is-dashed"]]
    assert out["dashedTools"] == ["outil-b (indisponible)"]
    assert out["station4"] == [True, True]
    assert out["current"] == ["2"]
    assert (
        out["escapeFromNode"]["expanded"] == "false"
        and out["escapeFromNode"]["focus"] == "chain-map-toggle"
    )


def test_carte_ne_change_ni_le_menu_volets_ni_les_zones_f6(tmp_path: Path) -> None:
    out = _js(
        tmp_path,
        f"""
const chain = {json.dumps(MAP_CHAIN)};
const first = mount();
const bare = {{ menu: $$(".pane-menu-item").map((i) => i.dataset.pane), shown: shown() }};
first.destroy();
$("#pane-menu").remove();
main.replaceChildren();
const view = mountWorkspace(main, {{ title: "Bac", store, storage, chain }});
$("#chain-map-toggle").click();
const open = {{ menu: $$(".pane-menu-item").map((i) => i.dataset.pane), shown: shown() }};
view.destroy();
console.log(JSON.stringify({{ bare, open, inert: $$("[inert]").length }}));
""",
    )
    assert out["open"] == out["bare"] and out["bare"]["menu"]
    # `destroy` rend les vues interactives même carte ouverte.
    assert out["inert"] == 0
