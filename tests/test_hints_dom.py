# ruff: noqa: E501
"""Indices par paliers (Story 4.6) sous Node, sur la doublure de DOM : onglets `hint-tabs` (rôles,
cadenas, `aria-disabled`, focus), ouverture par le clic, « Ouvrir un indice » de l'encart
« État inattendu », annonce du déblocage et relecture du panneau. Le serveur décide de tout
(AD-2) ; le rendu réel et le lecteur d'écran se vérifient dans un navigateur."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from test_shell_js import NODE, _run

pytestmark = pytest.mark.skipif(NODE is None, reason="Node absent : comportement JS non exécuté")

MINIDOM = (Path(__file__).resolve().parent / "js" / "minidom.mjs").as_uri()

PRELUDE = f"""
import {{ installDom, memoryStorage, makeEvent }} from "{MINIDOM}";
const {{ document, main }} = installDom({{ width: 1920, height: 1080 }});
await import("@JS@/views.js");
const {{ mountWorkspace }} = await import("@JS@/workspace.js");
const {{ createStore, connectWorkspace }} = await import("@JS@/store.js");
const $ = (s) => document.querySelector(s);
const $$ = (s) => [...document.querySelectorAll(s)];
const tiers = (states, extra = {{}}) => [
  {{ tier: 1, label_text: "Piste", state: states[0], ...(states[0] === "open" ? {{ text: "Pensez à `git switch`." }} : {{}}) }},
  {{ tier: 2, label_text: "Commande partielle", state: states[1],
     ...(states[1] === "open" ? {{ text: "git switch -c ___" }} : {{}}),
     ...(states[1] === "locked" ? {{ condition_text: "Ouvrez d'abord la piste." }} : {{}}) }},
  {{ tier: 3, label_text: "Solution", state: states[2],
     ...(states[2] === "open" ? {{ text: "git switch -c feature" }} : {{}}),
     ...(states[2] === "locked" ? {{ condition_text: extra.condition || "Ouvrez d'abord la commande partielle." }} : {{}}) }},
];
const panelOf = (states, extra = {{}}) => ({{
  title_text: "Indices", mode: "A", mode_text: "Mode A.", current_step_id: "creer", has_hints: true,
  quiz_altered: null, restore_failed: null,
  steps: [
    {{ step_id: "creer", title_text: "Créer la branche", instruction_text: "Créez `feature`.",
       state: "current", explanation_text: "", explain_ref: "",
       hints: {{ tiers: tiers(states, extra), solution_unlock_ms: extra.unlock ?? null,
                 unlocked_text: "La solution est disponible." }} }},
    {{ step_id: "suite", title_text: "Suite", instruction_text: "Continuez.",
       state: "todo", explanation_text: "", explain_ref: "" }},
  ],
}});
const posts = [];
globalThis.fetch = async (url, init) => {{
  posts.push([url, JSON.parse(init.body)]);
  return {{ ok: true, status: 202, json: async () => ({{}}) }};
}};
let seq = 5;
const event = (store, kind, payload) =>
  store.applyEvent({{ kind, boot_id: "b", seq: ++seq, epoch: 0, payload }});
const store = createStore();
store.applySnapshot({{ workspace_id: "llm.indices.A", boot_id: "b", seq, epoch: 0, state: "idle",
  reason_text: "", fingerprint: "", views: {{}}, step_panel: panelOf(["available", "locked", "locked"]) }});
mountWorkspace(main, {{ title: "Indices", store, storage: memoryStorage() }});
const text = (s) => ($(s) ? $(s).textContent : null);
const tick = () => new Promise((r) => setTimeout(r, 0));
const tabInfo = () => $$(".hint-tab").map((t) => [
  t.getAttribute("data-state"), t.getAttribute("aria-selected"), t.getAttribute("aria-disabled"), t.textContent]);
"""


def _js(tmp_path: Path, body: str) -> dict:
    return json.loads(_run(tmp_path, f"{PRELUDE}\n{body}"))


def test_onglets_roles_cadenas_et_conditions(tmp_path: Path) -> None:
    out = _js(
        tmp_path,
        """
const list = $(".hint-tablist");
console.log(JSON.stringify({
  role: list.getAttribute("role"), tabs: $$(".hint-tab").map((t) => t.getAttribute("role")),
  info: tabInfo(), panelRole: $(".hint-panel").getAttribute("role"),
  controls: $(".hint-tab").getAttribute("aria-controls") === $(".hint-panel").getAttribute("id"),
  counter: /\\d+ indice|compteur/i.test(text(".scenario-body")),
}));
""",
    )
    assert out["role"] == "tablist"
    assert out["tabs"] == ["tab", "tab", "tab"]
    assert out["panelRole"] == "tabpanel" and out["controls"] is True
    first, second, third = out["info"]
    assert first[0] == "available" and first[2] is None and first[3].endswith("Ouvrir")
    # Verrouillé : cadenas, condition en clair, aria-disabled, mais focalisable (pas `disabled`).
    assert second[0] == "locked" and second[2] == "true"
    assert "\U0001f512" in second[3] and "Ouvrez d'abord la piste." in second[3]
    assert third[2] == "true" and "Ouvrez d'abord la commande partielle." in third[3]
    assert out["counter"] is False


def test_clic_ouvre_un_palier_et_un_onglet_verrouille_ne_fait_rien(tmp_path: Path) -> None:
    out = _js(
        tmp_path,
        """
const tabs = () => $$(".hint-tab");
tabs()[1].click();
tabs()[2].click();
await tick();
const locked = posts.length;
tabs()[0].click();
await tick();
// Le serveur confirme : le panneau relu montre la piste ouverte.
store.setStepPanel(panelOf(["open", "available", "locked"]));
console.log(JSON.stringify({ locked, posts, info: tabInfo(), text: text(".hint-text"),
  focusable: tabs()[1].getAttribute("disabled") }));
""",
    )
    assert out["locked"] == 0
    assert out["posts"] == [["/api/ws/llm.indices.A/hint_open", {"tier": 1}]]
    assert out["info"][0][:2] == ["open", "true"]
    assert out["info"][1][0] == "available"
    assert out["text"] == "Pensez à git switch."
    assert out["focusable"] is None


def test_commande_partielle_blancs_et_solution_en_texte_selectionnable(tmp_path: Path) -> None:
    out = _js(
        tmp_path,
        """
store.setStepPanel(panelOf(["open", "open", "open"]));
const tabs = () => $$(".hint-tab");
const partial = (tabs()[1].click(), text(".hint-text"));
const solution = (tabs()[2].click(), text(".hint-text"));
console.log(JSON.stringify({ partial, solution, buttons: $$(".hint-panel button").length,
  copy: /Copier|Exécuter/.test(text(".hint-tabs")) }));
""",
    )
    assert out["partial"] == "git switch -c ___"
    assert out["solution"] == "git switch -c feature"
    assert out["buttons"] == 0 and out["copy"] is False


def test_fleches_deplacent_le_focus_y_compris_sur_un_onglet_verrouille(tmp_path: Path) -> None:
    out = _js(
        tmp_path,
        """
const tabs = () => $$(".hint-tab");
tabs()[0].focus();
const press = (key) => document.activeElement.dispatchEvent(makeEvent("keydown", { key, bubbles: true }));
press("ArrowRight");
const second = document.activeElement.getAttribute("data-tier");
press("ArrowRight");
const third = document.activeElement.getAttribute("data-tier");
press("ArrowRight");
const wrap = document.activeElement.getAttribute("data-tier");
press("End");
console.log(JSON.stringify({ second, third, wrap, end: document.activeElement.getAttribute("data-tier") }));
""",
    )
    assert (out["second"], out["third"], out["wrap"], out["end"]) == ("2", "3", "1", "3")


def test_ouvrir_un_indice_dans_l_encart_etat_inattendu(tmp_path: Path) -> None:
    out = _js(
        tmp_path,
        """
event(store, "step_verdict", { step_id: "creer", passed: false, status: "unexpected",
  reason_text: "", expected_text: "Une branche `feature`.", observed: [] });
const btn = () => $('[data-action="open-hint"]');
const label = btn().textContent;
btn().click();
await tick();
store.setStepPanel(panelOf(["open", "available", "locked"]));
const second = btn().textContent;
btn().click();
await tick();
store.setStepPanel(panelOf(["open", "open", "locked"], { condition: "Disponible après un essai ou un moment de lecture." }));
const waiting = btn();
const reason = waiting.nextElementSibling ? waiting.nextElementSibling.textContent : null;
const disabled = waiting.getAttribute("aria-disabled");
waiting.click();
await tick();
store.setStepPanel(panelOf(["open", "open", "open"]));
console.log(JSON.stringify({ label, second, posts, reason, disabled, last: btn() }));
""",
    )
    assert out["label"] == "Ouvrir un indice"
    assert out["posts"] == [
        ["/api/ws/llm.indices.A/hint_open", {"tier": 1}],
        ["/api/ws/llm.indices.A/hint_open", {"tier": 2}],
    ]
    assert out["disabled"] == "true"
    assert out["reason"] == "Disponible après un essai ou un moment de lecture."
    assert out["last"] is None  # trois paliers ouverts : plus rien à ouvrir


def test_deblocage_annonce_puis_relecture_du_panneau(tmp_path: Path) -> None:
    out = _js(
        tmp_path,
        """
store.setStepPanel(panelOf(["open", "open", "locked"], { condition: "Disponible après un essai ou un moment de lecture.", unlock: 20000 }));
const before = text(".scenario-status");
store.setStepPanel(panelOf(["open", "open", "available"]));
const unlocked = text(".scenario-status");
event(store, "engine_state", { state: "command", reason_text: "" });
console.log(JSON.stringify({ before, unlocked, after: text(".scenario-status") }));
""",
    )
    assert "La solution est disponible." not in out["before"]
    assert out["unlocked"].endswith("La solution est disponible.")
    assert "La solution est disponible." not in out["after"]


def test_la_relecture_du_panneau_suit_l_ouverture_et_la_fin_d_une_action(tmp_path: Path) -> None:
    out = _js(
        tmp_path,
        """
const waiting = panelOf(["open", "open", "locked"], { condition: "Disponible après un essai ou un moment de lecture.", unlock: 60 });
const unlocked = panelOf(["open", "open", "available"]);
const reads = [];
let answer = waiting;
const fetchImpl = async (url) => {
  reads.push(url);
  return { ok: true, json: async () => ({ workspace_id: "w", boot_id: "b1", seq: reads.length === 1 ? 7 : live.state.seq, epoch: 0, state: "idle",
    views: {}, step_panel: answer }) };
};
const sources = [];
class Fake { constructor(url) { this.url = url; sources.push(this); } close() {} }
const live = createStore();
connectWorkspace(live, "w", { fetchImpl, EventSourceImpl: Fake });
await new Promise((r) => setTimeout(r, 20));
const send = (seq, kind, payload) => sources[0].onmessage({ data: JSON.stringify({ boot_id: "b1", seq, epoch: 0, kind, payload }) });
const first = reads.length;
send(8, "engine_state", { state: "command" });      // début d'action : rien à relire
const quiet = reads.length;
answer = unlocked;
send(9, "engine_state", { state: "idle" });          // fin d'action avec la solution en attente
await new Promise((r) => setTimeout(r, 20));
const tier3 = live.state.stepPanel.steps[0].hints.tiers[2].state;
const notice = live.state.hintNotice;
console.log(JSON.stringify({ first, quiet, tier3, notice, total: reads.length }));
""",
    )
    assert out["first"] == 1  # la lecture initiale seule
    assert out["quiet"] == 1
    assert out["tier3"] == "available"
    assert out["notice"] == "La solution est disponible."
    assert out["total"] == 2


def test_minuterie_de_deblocage_relit_le_panneau_sans_decompte(tmp_path: Path) -> None:
    out = _js(
        tmp_path,
        """
let answer = panelOf(["open", "open", "locked"], { condition: "Disponible après un essai ou un moment de lecture.", unlock: 40 });
const reads = [];
const fetchImpl = async (url) => {
  reads.push(url);
  return { ok: true, json: async () => ({ workspace_id: "w", boot_id: "b1", seq: reads.length === 1 ? 7 : live.state.seq, epoch: 0, state: "idle",
    views: {}, step_panel: answer }) };
};
class Fake { constructor() {} close() {} }
const live = createStore();
connectWorkspace(live, "w", { fetchImpl, EventSourceImpl: Fake });
await new Promise((r) => setTimeout(r, 20));
const beforeTimer = [reads.length, live.state.stepPanel.steps[0].hints.tiers[2].state];
answer = panelOf(["open", "open", "available"]);
await new Promise((r) => setTimeout(r, 150));
console.log(JSON.stringify({ beforeTimer, after: live.state.stepPanel.steps[0].hints.tiers[2].state,
  reads: reads.length, notice: live.state.hintNotice }));
""",
    )
    assert out["beforeTimer"] == [1, "locked"]
    assert out["after"] == "available"
    assert out["reads"] == 2
    assert out["notice"] == "La solution est disponible."
