# ruff: noqa: E501
"""Bilan de fin de scénario (Story 4.7) exécuté sous Node, sur la doublure de DOM : `score-summary`,
ses trois actions, le bouton inactif sans scénario suivant, la relecture de l'état à la fin du
scénario. Les textes viennent du serveur ; le rendu réel se vérifie dans un navigateur."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from test_shell_js import NODE, _run

pytestmark = pytest.mark.skipif(NODE is None, reason="Node absent : comportement JS non exécuté")

MINIDOM = (Path(__file__).resolve().parent / "js" / "minidom.mjs").as_uri()

PRELUDE = f"""
import {{ installDom, memoryStorage }} from "{MINIDOM}";
const {{ document, main }} = installDom({{ width: 1920, height: 1080 }});
await import("@JS@/views.js");
const {{ mountWorkspace }} = await import("@JS@/workspace.js");
const {{ createStore }} = await import("@JS@/store.js");
const $ = (s) => document.querySelector(s);
const $$ = (s) => [...document.querySelectorAll(s)];
const SUMMARY = {{
  quiz_correct: 3, quiz_total: 4, hints: 1, score_text: "3 sur 4 du premier coup",
  hints_text: "1 indice", text: "3 sur 4 du premier coup · 1 indice",
  next: {{ scenario_id: "zeta", mode: "A", track: "no_ai", title_text: "Suite" }},
  next_none_text: "Aucun autre scénario n'est disponible pour l'instant.",
}};
const PANEL = (summary) => ({{
  title_text: "Fin", mode: "A", mode_text: "Mode A.", current_step_id: "", summary,
  steps: [
    {{ step_id: "un", title_text: "Un", instruction_text: "Faites.", state: "done",
       explanation_text: "Fait.", explain_ref: "" }},
  ],
}});
const posts = [];
const assigned = [];
globalThis.window.location = {{ assign: (p) => assigned.push(p) }};
globalThis.fetch = async (url, init) => {{
  posts.push([url, JSON.parse(init.body)]);
  if (url === "/api/open") {{
    return {{ ok: true, status: 202, json: async () => ({{ workspace_id: "no_ai.zeta.A" }}) }};
  }}
  return {{ ok: true, status: 202, json: async () => ({{}}) }};
}};
let seq = 5;
const event = (store, kind, payload) =>
  store.applyEvent({{ kind, boot_id: "b", seq: ++seq, epoch: 0, payload }});
const mount = (summary) => {{
  const store = createStore();
  store.applySnapshot({{ workspace_id: "llm.fin.A", boot_id: "b", seq, epoch: 0, state: "idle",
    reason_text: "", fingerprint: "", views: {{}}, step_panel: PANEL(summary) }});
  main.replaceChildren();
  mountWorkspace(main, {{ title: "Fin", store, storage: memoryStorage() }});
  return store;
}};
const text = (s) => ($(s) ? $(s).textContent : null);
const tick = () => new Promise((r) => setTimeout(r, 0));
"""


def _js(tmp_path: Path, body: str) -> dict:
    return json.loads(_run(tmp_path, f"{PRELUDE}\n{body}"))


def test_bilan_texte_actions_et_vues_consultables(tmp_path: Path) -> None:
    out = _js(
        tmp_path,
        """
mount(SUMMARY);
const buttons = $$(".score-summary button").map((b) => b.textContent);
console.log(JSON.stringify({ score: text(".score-summary-score"), hints: text(".score-summary-hints"),
  title: text(".score-summary-title"), buttons, status: text(".scenario-status"),
  nextDisabled: $('[data-action="next"]').getAttribute("aria-disabled"),
  explained: Boolean($(".step-explanation")), inert: Boolean($(".views-grid").inert) }));
""",
    )
    assert out["score"] == "3 sur 4 du premier coup"
    assert out["hints"] == "1 indice"
    assert out["title"] == "Scénario terminé"
    assert out["buttons"] == ["Scénario suivant", "Catalogue", "Recommencer"]
    assert "Scénario terminé. 3 sur 4 du premier coup · 1 indice." in out["status"]
    assert out["nextDisabled"] is None
    assert out["explained"] is True
    assert out["inert"] is False


def test_actions_suivant_catalogue_recommencer(tmp_path: Path) -> None:
    out = _js(
        tmp_path,
        """
mount(SUMMARY);
$('[data-action="restart"]').click();
await tick();
$('[data-action="catalogue"]').click();
$('[data-action="next"]').click();
await tick();
await tick();
console.log(JSON.stringify({ posts, assigned }));
""",
    )
    assert out["posts"] == [
        ["/api/ws/llm.fin.A/restart", {}],
        ["/api/open", {"scenario_id": "zeta", "mode": "A", "track": "no_ai"}],
    ]
    assert out["assigned"] == ["/", "/espace/no_ai.zeta.A"]


def test_sans_scenario_suivant_le_bouton_dit_pourquoi(tmp_path: Path) -> None:
    out = _js(
        tmp_path,
        """
mount({ ...SUMMARY, next: null });
const next = $('[data-action="next"]');
next.click();
await tick();
const why = $(".score-summary-why");
console.log(JSON.stringify({ disabled: next.getAttribute("aria-disabled"),
  linked: next.getAttribute("aria-describedby") === why.id, why: why.textContent,
  posts, assigned }));
""",
    )
    assert out["disabled"] == "true"
    assert out["linked"] is True
    assert out["why"] == "Aucun autre scénario n'est disponible pour l'instant."
    assert out["posts"] == [] and out["assigned"] == []


def test_zero_indice_et_pas_de_bilan_en_cours_de_scenario(tmp_path: Path) -> None:
    out = _js(
        tmp_path,
        """
mount({ ...SUMMARY, hints: 0, hints_text: "0 indice", text: "3 sur 4 du premier coup · 0 indice" });
const zero = text(".score-summary-hints");
mount(null);
console.log(JSON.stringify({ zero, none: $(".score-summary") === null }));
""",
    )
    assert out["zero"] == "0 indice"
    assert out["none"] is True


def test_fin_du_scenario_relit_l_etat(tmp_path: Path) -> None:
    out = _js(
        tmp_path,
        """
const store = mount(null);
const other = event(store, "progress_updated", { track: "llm", scenario_id: "fin", mode: "A", facts: ["step_validated"], step_ids: ["un"] });
const done = event(store, "progress_updated", { track: "llm", scenario_id: "fin", mode: "A", facts: ["step_validated", "scenario_completed"], step_ids: ["un"] });
console.log(JSON.stringify({ other, done }));
""",
    )
    assert out == {"other": "applied", "done": "resync"}
