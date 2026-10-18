# ruff: noqa: E501
"""Catalogue et choix du parcours (Story 6.1) exécutés sous Node, sur la doublure de DOM.

Le rendu réel (pilules, disques, disposition) se vérifie dans un navigateur ; ici : textes,
rôles ARIA, cartes indisponibles sans bouton, changement de parcours et mémorisation.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from test_shell_js import NODE, _run
from test_workspace_dom import MINIDOM

pytestmark = pytest.mark.skipif(NODE is None, reason="Node absent : comportement JS non exécuté")

TRACKS = [
    {"key": "llm", "label": "Parcours LLM", "text": "Avec assistant."},
    {"key": "no_ai", "label": "Parcours sans IA", "text": "À la main."},
]
QUESTION = "Choisissez votre parcours. Les deux suivent la même progression ; seul le code d'exercice change."

PRELUDE = f"""
import {{ installDom, memoryStorage, makeEvent }} from "{MINIDOM}";
const {{ document, main }} = installDom();
const {{ renderCatalogue, openMode, loadCatalogue }} = await import("@JS@/catalogue.js");
const {{ getTrack, setTrack, renderPathMenu }} = await import("@JS@/track.js");
const $ = (s) => document.querySelector(s);
const $$ = (s) => [...document.querySelectorAll(s)];
const tracks = {json.dumps(TRACKS)};
const picker = {{ question: {json.dumps(QUESTION)} }};
"""


def _js(tmp_path: Path, body: str) -> dict:
    return json.loads(_run(tmp_path, f"{PRELUDE}\n{body}"))


def test_premier_passage_seul_le_choix_du_parcours(tmp_path: Path) -> None:
    out = _js(
        tmp_path,
        """
const picked = [];
renderCatalogue(main, { track: null, tracks, picker, sections: [] }, () => {}, (t) => picked.push(t));
$$(".path-pill")[1].dispatchEvent(makeEvent("click"));
console.log(JSON.stringify({
  question: $(".path-picker-question").textContent,
  group: $(".path-picker").getAttribute("role"),
  pills: $$(".path-pill").map((p) => [p.textContent, p.getAttribute("role"), p.getAttribute("aria-checked")]),
  sentences: $$(".path-picker-text").map((p) => p.textContent),
  sections: $$(".catalogue-section").length,
  picked,
}));
""",
    )
    assert out["question"] == QUESTION
    assert out["group"] == "radiogroup"
    assert out["pills"] == [
        ["Parcours LLM", "radio", "false"],
        ["Parcours sans IA", "radio", "false"],
    ]
    assert out["sentences"] == ["Avec assistant.", "À la main."]
    assert out["sections"] == 0
    assert out["picked"] == ["no_ai"]


CATALOGUE = {
    "track": "llm",
    "tracks": TRACKS,
    "picker": {"question": QUESTION},
    "sections": [
        {
            "key": "socle-git",
            "title": "Socle git",
            "subtitle": "Les gestes git.",
            "scenarios": [
                {
                    "scenario_id": "add-commit",
                    "title": "Add et commit",
                    "number": 1,
                    "modes": [
                        {"mode": "A", "track": "llm", "workspace_id": "llm.add-commit.A", "state": "in_progress", "state_text": "En cours", "detail_text": "3 sur 4 du premier coup · 1 indice", "available": True},
                        {"mode": "B", "track": "llm", "workspace_id": "llm.add-commit.B", "state": "todo", "state_text": "À faire", "detail_text": "", "available": True},
                    ],
                },
                {
                    "scenario_id": "branche",
                    "title": "Branche",
                    "number": 2,
                    "modes": [
                        {
                            "mode": "A", "track": "llm", "workspace_id": "llm.branche.A", "state": "todo", "state_text": "À faire", "detail_text": "", "available": False,
                            "unavailable": {"text": "⊘ Indisponible", "needs_text": "Nécessite gitleaks", "diagnostic_text": "Voir le diagnostic", "diagnostic_path": "/diagnostic"},
                        }
                    ],
                },
            ],
        }
    ],
}


def test_cartes_ordonnees_etats_et_carte_indisponible(tmp_path: Path) -> None:
    out = _js(
        tmp_path,
        f"""
const opened = [];
renderCatalogue(main, {json.dumps(CATALOGUE)}, async (s, m) => {{ opened.push([s.scenario_id, m.mode]); }});
const cards = $$(".scenario-card");
const first = cards[0].querySelectorAll(".scenario-mode");
$$("button[data-mode]")[0].dispatchEvent(makeEvent("click"));
console.log(JSON.stringify({{
  title: $(".catalogue-title").textContent,
  discs: $$(".scenario-disc").map((d) => d.textContent),
  titles: $$(".scenario-card-title").map((t) => t.textContent),
  columns: first.map((c) => c.querySelector(".scenario-mode-name").textContent),
  states: first.map((c) => [c.querySelector(".scenario-mode-state").textContent, (c.querySelector(".scenario-mode-detail") || {{}}).textContent || null]),
  buttons: $$("button[data-mode]").map((b) => b.getAttribute("aria-label")),
  off: {{
    text: cards[1].querySelector(".scenario-mode-state").textContent,
    detail: cards[1].querySelector(".scenario-mode-detail").textContent,
    link: cards[1].querySelector("a").getAttribute("href"),
    buttons: cards[1].querySelectorAll("button").length,
    cls: cards[1].querySelector(".scenario-mode").className,
  }},
  pressed: $$(".path-pill").map((p) => p.getAttribute("aria-checked")),
  opened,
}}));
""",
    )
    assert out["title"] == "Socle git"
    assert out["discs"] == ["1", "2"]
    assert out["titles"] == ["Add et commit", "Branche"]
    assert out["columns"] == ["Mode A", "Mode B"]
    assert out["states"] == [
        ["En cours", "3 sur 4 du premier coup · 1 indice"],
        ["À faire", None],
    ]
    assert out["buttons"] == [
        "Ouvrir Add et commit en mode A",
        "Ouvrir Add et commit en mode B",
    ]
    assert out["off"] == {
        "text": "⊘ Indisponible",
        "detail": "Nécessite gitleaks · Voir le diagnostic",
        "link": "/diagnostic",
        "buttons": 0,
        "cls": "scenario-mode is-unavailable",
    }
    assert out["pressed"] == ["true", "false"]
    assert out["opened"] == [["add-commit", "A"]]


def test_path_menu_memorisation_et_changement(tmp_path: Path) -> None:
    out = _js(
        tmp_path,
        """
const storage = memoryStorage();
const first = getTrack(storage);
setTrack("no_ai", storage);
const menu = document.createElement("select");
menu.hidden = true;
const changed = [];
renderPathMenu(menu, tracks, null, (t) => changed.push(t));
const bare = [...menu.children].map((o) => [o.value, o.textContent, o.disabled === true]);
renderPathMenu(menu, tracks, "llm", (t) => changed.push(t));
menu.value = "no_ai";
menu.onchange();
menu.value = "llm";
menu.onchange();
const broken = { getItem() { throw new Error("refusé"); }, setItem() { throw new Error("refusé"); } };
let survived = true;
try { setTrack("llm", broken); } catch (e) { survived = false; }
const opens = [];
const fetchImpl = async (url, init) => { opens.push([url, JSON.parse(init.body)]); return { ok: true, json: async () => ({ workspace_id: "x" }) }; };
await openMode({ scenario_id: "add-commit" }, { mode: "A", track: "llm" }, { fetchImpl, track: "no_ai" });
const urls = [];
await loadCatalogue({ fetchImpl: async (u) => { urls.push(u); return { ok: true, json: async () => ({}) }; }, track: "no_ai" });
await loadCatalogue({ fetchImpl: async (u) => { urls.push(u); return { ok: true, json: async () => ({}) }; } });
console.log(JSON.stringify({ first, stored: getTrack(storage), bare, labels: [...menu.children].map((o) => o.textContent), hidden: menu.hidden, changed, survived, brokenRead: getTrack(broken), opens, urls }));
""",
    )
    assert out["first"] is None and out["stored"] == "no_ai"
    assert out["bare"][0] == ["", "Choisir un parcours", True]
    assert out["labels"] == ["Parcours LLM", "Parcours sans IA"]
    assert out["hidden"] is False
    assert out["changed"] == ["no_ai"]  # le parcours déjà courant ne déclenche rien
    assert out["survived"] is True and out["brokenRead"] is None
    assert out["opens"][0][1] == {"scenario_id": "add-commit", "mode": "A", "track": "no_ai"}
    assert out["urls"] == ["/api/catalogue?track=no_ai", "/api/catalogue"]


def test_erreur_du_catalogue_porte_le_statut_et_le_motif(tmp_path: Path) -> None:
    # main.js ne revient au choix du parcours que sur 422 ; sinon il affiche `reasonText`.
    out = _js(
        tmp_path,
        """
const fail = (status, body) => async () => ({ ok: false, status, json: async () => body });
const seen = [];
for (const [status, body] of [[500, { reason_text: "Le fichier progress.json est illisible. Renommez-le." }], [422, {}]]) {
  try { await loadCatalogue({ fetchImpl: fail(status, body), track: "llm" }); }
  catch (err) { seen.push([err.status, err.reasonText]); }
}
try { await loadCatalogue({ fetchImpl: async () => ({ ok: false, status: 502, json: async () => { throw new Error("html"); } }) }); }
catch (err) { seen.push([err.status, err.reasonText]); }
console.log(JSON.stringify(seen));
""",
    )
    assert out == [
        [500, "Le fichier progress.json est illisible. Renommez-le."],
        [422, ""],
        [502, ""],
    ]
