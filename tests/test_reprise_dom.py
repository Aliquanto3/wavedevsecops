# ruff: noqa: E501
"""« Reprendre » du catalogue (Story 6.4) exécuté sous Node, sur la doublure de DOM."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from test_catalogue_dom import QUESTION, TRACKS, _js
from test_shell_js import NODE

pytestmark = pytest.mark.skipif(NODE is None, reason="Node absent : comportement JS non exécuté")

RESUME = {
    "can_resume": True,
    "step_number": 2,
    "step_total": 5,
    "text": "Étape 2 sur 5",
    "button_text": "Reprendre",
}
BLOCKED = {
    "can_resume": False,
    "step_number": 0,
    "step_total": 5,
    "blocked_text": "Ce scénario ne peut pas reprendre là où vous l'aviez laissé.",
    "restart_text": "Recommencer",
}
BASE = {
    "mode": "A",
    "tracks": ["no_ai"],
    "track": "no_ai",
    "state": "in_progress",
    "state_text": "En cours",
    "detail_text": "",
    "available": True,
}


def _card(sid: str, title: str, number: int, **extra) -> dict:
    return {
        "scenario_id": sid,
        "title": title,
        "number": number,
        "modes": [{**BASE, "workspace_id": f"no_ai.{sid}.A", **extra}],
    }


CATALOGUE = {
    "track": "no_ai",
    "tracks": TRACKS,
    "picker": {"question": QUESTION},
    "sections": [
        {
            "key": "socle-git",
            "title": "Socle git",
            "subtitle": "",
            "scenarios": [
                _card("add-commit", "Add et commit", 1, resume=RESUME),
                _card("branche", "Branche", 2, resume=BLOCKED),
                _card("stash", "Stash", 3),
            ],
        }
    ],
}


def test_reprendre_etape_encart_et_corps_de_la_demande(tmp_path: Path) -> None:
    """« Étape n sur N » et « Reprendre » à côté d'« Ouvrir » ; mode bloqué : encart et
    « Recommencer » seul ; `resume` et `restart` partent dans le corps de `/api/open`."""
    out = _js(
        tmp_path,
        f"""
const calls = [];
renderCatalogue(main, {json.dumps(CATALOGUE)}, async (s, m, how) => {{ calls.push([s.scenario_id, how || null]); }});
const cards = $$(".scenario-card");
const labels = (i) => [...cards[i].querySelectorAll("button")].map((b) => [b.textContent, b.getAttribute("data-action")]);
cards[0].querySelector('button[data-action="resume"]').dispatchEvent(makeEvent("click"));
cards[1].querySelector('button[data-action="restart-ask"]').dispatchEvent(makeEvent("click"));
await new Promise((r) => setTimeout(r, 0));
const confirmText = cards[1].querySelector(".restart-confirm-text").textContent;
const callsBeforeConfirm = calls.length;
cards[1].querySelector('button[data-action="restart-cancel"]').dispatchEvent(makeEvent("click"));
const afterCancel = labels(1);
cards[1].querySelector('button[data-action="restart-ask"]').dispatchEvent(makeEvent("click"));
cards[1].querySelector('button[data-action="restart-confirm"]').dispatchEvent(makeEvent("click"));
await new Promise((r) => setTimeout(r, 0));
const bodies = [];
const fetchImpl = async (u, init) => {{ bodies.push(JSON.parse(init.body)); return {{ ok: true, json: async () => ({{}}) }}; }};
await openMode({{ scenario_id: "add-commit" }}, {{ mode: "A" }}, {{ fetchImpl, track: "no_ai", resume: true }});
await openMode({{ scenario_id: "add-commit" }}, {{ mode: "A" }}, {{ fetchImpl, track: "no_ai", restart: true }});
await openMode({{ scenario_id: "add-commit" }}, {{ mode: "A" }}, {{ fetchImpl, track: "no_ai" }});
console.log(JSON.stringify({{
  step: cards[0].querySelector(".scenario-mode-step").textContent,
  b0: labels(0), b1: labels(1), b2: labels(2),
  aria: cards[0].querySelector('button[data-action="resume"]').getAttribute("aria-label"),
  encart: [cards[1].querySelector(".scenario-mode-blocked").textContent, cards[1].querySelector(".scenario-mode-blocked").getAttribute("role")],
  noStep: cards[1].querySelector(".scenario-mode-step") === null,
  calls, bodies, confirmText, callsBeforeConfirm, afterCancel,
}}));
""",
    )
    assert out["step"] == "Étape 2 sur 5"
    assert out["b0"] == [["Reprendre", "resume"], ["Ouvrir en mode A", "open"]]
    assert out["aria"] == "Reprendre Add et commit en mode A"
    assert out["encart"] == [
        "Ce scénario ne peut pas reprendre là où vous l'aviez laissé.",
        "status",
    ]
    # « Recommencer » demande la confirmation en ligne de la 4.4 avant toute remise à zéro.
    assert out["callsBeforeConfirm"] == 1
    assert out["confirmText"].startswith("Remettre le scénario à son état initial ?")
    assert out["afterCancel"] == [["Recommencer", "restart-ask"]] and out["noStep"] is True
    assert out["b1"] == [["Annuler", "restart-cancel"], ["Remettre à zéro", "restart-confirm"]]
    assert out["b2"] == [["Ouvrir en mode A", "open"]]
    assert out["calls"] == [["add-commit", {"resume": True}], ["branche", {"restart": True}]]
    assert out["bodies"][0]["resume"] is True and "restart" not in out["bodies"][0]
    assert out["bodies"][1]["restart"] is True
    assert "resume" not in out["bodies"][2] and "restart" not in out["bodies"][2]
