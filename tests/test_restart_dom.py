# ruff: noqa: E501
"""Recommencer (Story 4.4) exécuté sous Node, sur la doublure de DOM : bouton du pied du panneau,
confirmation en ligne, annonce « Scénario remis à zéro. », encarts « État inattendu » et
« Scénario mis à jour », et relecture du panneau (le bilan disparaît). Le serveur écrit tous les
textes d'état ; le rendu réel se vérifie dans un navigateur."""

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
const {{ createStore, connectWorkspace }} = await import("@JS@/store.js");
const $ = (s) => document.querySelector(s);
const $$ = (s) => [...document.querySelectorAll(s)];
const text = (s) => ($(s) ? $(s).textContent : null);
const tick = () => new Promise((r) => setTimeout(r, 0));
const SUMMARY = {{
  quiz_correct: 1, quiz_total: 1, hints: 0, score_text: "1 sur 1 du premier coup",
  hints_text: "0 indice", text: "1 sur 1 du premier coup · 0 indice", next: null,
  next_none_text: "Aucun autre scénario n'est disponible pour l'instant.",
}};
const step = (id, state, extra = {{}}) => ({{ step_id: id, title_text: `Étape ${{id}}`,
  instruction_text: "Faites.", state, explanation_text: state === "done" ? "Fait." : "",
  explain_ref: "", ...extra }});
const FIRST = {{
  title_text: "Reprise", mode: "A", mode_text: "Mode A.", current_step_id: "un",
  quiz_altered: null, restore_failed: null, summary: null, content_changed: null,
  steps: [step("un", "current"), step("deux", "todo")],
}};
const DONE = {{ ...FIRST, current_step_id: "", summary: SUMMARY,
  steps: [step("un", "done"), step("deux", "done")] }};
const posts = [];
globalThis.fetch = async (url, init) => {{
  posts.push([url, JSON.parse(init.body)]);
  return {{ ok: true, status: 202, json: async () => ({{}}) }};
}};
let seq = 5;
const event = (store, kind, payload) =>
  store.applyEvent({{ kind, boot_id: "b", seq: ++seq, epoch: 0, payload }});
const mount = (panel) => {{
  const store = createStore();
  store.applySnapshot({{ workspace_id: "llm.reprise.A", boot_id: "b", seq, epoch: 0, state: "idle",
    reason_text: "", fingerprint: "", views: {{}}, step_panel: panel }});
  main.replaceChildren();
  mountWorkspace(main, {{ title: "Reprise", store, storage: memoryStorage() }});
  return store;
}};
"""


def _js(tmp_path: Path, body: str) -> dict:
    return json.loads(_run(tmp_path, f"{PRELUDE}\n{body}"))


def test_pied_du_panneau_confirmation_en_ligne_puis_envoi(tmp_path: Path) -> None:
    out = _js(
        tmp_path,
        """
const store = mount(FIRST);
const foot = $(".restart-foot");
const before = { label: text('.restart-foot [data-action="restart-ask"]'), confirm: $(".restart-confirm") === null };
$('[data-action="restart-ask"]').click();
const asked = { text: text(".restart-confirm-text"), buttons: $$(".restart-confirm button").map((b) => b.textContent),
  focus: document.activeElement.getAttribute("data-action"), group: $(".restart-confirm").getAttribute("role"), posts: posts.length };
$('[data-action="restart-cancel"]').click();
const cancelled = { confirm: $(".restart-confirm") === null, focus: document.activeElement.getAttribute("data-action"), posts: posts.length };
$('[data-action="restart-ask"]').click();
$('[data-action="restart-confirm"]').click();
await tick();
console.log(JSON.stringify({ before, asked, cancelled, posts, last: foot !== null }));
""",
    )
    assert out["before"] == {"label": "Recommencer", "confirm": True}
    assert out["asked"] == {
        "text": "Remettre le scénario à son état initial ? Votre score du premier coup est conservé.",
        "buttons": ["Annuler", "Remettre à zéro"],
        "focus": "restart-cancel",
        "group": "group",
        "posts": 0,
    }
    assert out["cancelled"] == {"confirm": True, "focus": "restart-ask", "posts": 0}
    assert out["posts"] == [["/api/ws/llm.reprise.A/restart", {}]]


def test_annonce_scenario_remis_a_zero_et_retour_a_l_etape_1(tmp_path: Path) -> None:
    out = _js(
        tmp_path,
        """
const store = mount(FIRST);
event(store, "step_verdict", { step_id: "un", passed: false, status: "unexpected", reason_text: "Pas ça.", expected_text: "", observed: [] });
const noticeBefore = $(".notice-card") !== null;
event(store, "engine_state", { state: "restoring", reason_text: "Remise à zéro du scénario en cours." });
event(store, "op_started", { intent: "restart" });
const waiting = text(".scenario-status");
const result = event(store, "progress_updated", { track: "llm", scenario_id: "reprise", mode: "A", facts: ["scenario_restarted"], step_ids: [] });
event(store, "engine_state", { state: "idle", reason_text: "" });
await tick();
const done = { status: text(".scenario-status"), noticeAfter: $(".notice-card") !== null,
  verdict: store.state.verdict, restarted: store.state.restarted, focus: document.activeElement.className };
event(store, "engine_state", { state: "command", reason_text: "" });
console.log(JSON.stringify({ noticeBefore, waiting, result, ...done, later: text(".scenario-status") }));
""",
    )
    assert out["noticeBefore"] is True
    assert out["waiting"] == "Remise à zéro du scénario…"
    assert out["result"] == "applied"
    assert "Scénario remis à zéro." in out["status"]
    assert out["noticeAfter"] is False
    assert out["verdict"] is None and out["restarted"] is True
    assert out["focus"] == "step-title"
    assert "Scénario remis à zéro." not in out["later"]  # annonce propre à la remise à zéro


def test_le_bilan_disparait_apres_recommencer(tmp_path: Path) -> None:
    """Constat L6 de la 4.7 : le resync n'est déclenché que par un fait nouveau ; la remise à zéro
    en est un, et le panneau relu n'a plus de bilan."""
    out = _js(
        tmp_path,
        """
let answer = DONE;
const reads = [];
const fetchImpl = async (url) => {
  reads.push(url);
  return { ok: true, json: async () => ({ workspace_id: "llm.reprise.A", boot_id: "b1", seq: reads.length === 1 ? 7 : live.state.seq,
    epoch: 0, state: "idle", views: {}, step_panel: answer }) };
};
const sources = [];
class Fake { constructor(url) { this.url = url; sources.push(this); } close() {} }
const live = createStore();
main.replaceChildren();
mountWorkspace(main, { title: "Reprise", store: live, storage: memoryStorage() });
connectWorkspace(live, "llm.reprise.A", { fetchImpl, EventSourceImpl: Fake });
await new Promise((r) => setTimeout(r, 20));
const withSummary = $(".score-summary") !== null;
const send = (n, kind, payload) => sources[0].onmessage({ data: JSON.stringify({ boot_id: "b1", seq: n, epoch: 0, kind, payload }) });
answer = FIRST;
send(8, "progress_updated", { track: "llm", scenario_id: "reprise", mode: "A", facts: ["scenario_restarted"], step_ids: [] });
await new Promise((r) => setTimeout(r, 20));
const afterRestart = { summary: $(".score-summary") !== null, count: text(".step-count"), reads: reads.length };
// Seconde fin de scénario : aucun fait nouveau, mais le verdict final relit le panneau.
answer = DONE;
send(9, "step_verdict", { step_id: "deux", passed: true, status: "passed", next_step_id: "", reason_text: "", expected_text: "", observed: [] });
await new Promise((r) => setTimeout(r, 20));
console.log(JSON.stringify({ withSummary, afterRestart, again: $(".score-summary") !== null, reads: reads.length }));
""",
    )
    assert out["withSummary"] is True
    assert out["afterRestart"] == {"summary": False, "count": "Étape 1 sur 2", "reads": 2}
    assert out["again"] is True
    assert out["reads"] == 3


def test_le_bouton_du_bilan_et_l_encart_etat_inattendu_demandent_confirmation(tmp_path: Path) -> None:
    out = _js(
        tmp_path,
        """
const store = mount(DONE);
$('.score-summary [data-action="restart"]').click();
const fromSummary = { confirm: $(".restart-confirm") !== null, posts: posts.length };
$('[data-action="restart-cancel"]').click();
const live = mount(FIRST);
event(live, "step_verdict", { step_id: "un", passed: false, status: "unexpected", reason_text: "Pas ça.", expected_text: "Attendu.", observed: [] });
const inNotice = $$(".notice-card .notice-actions button").map((b) => b.textContent);
$('.notice-card [data-action="restart-ask"]').click();
const fromNotice = { confirm: $(".restart-confirm") !== null, posts: posts.length };
console.log(JSON.stringify({ fromSummary, inNotice, fromNotice }));
""",
    )
    assert out["fromSummary"] == {"confirm": True, "posts": 0}
    assert out["inNotice"] == ["Continuer", "Recommencer"]
    assert out["fromNotice"] == {"confirm": True, "posts": 0}


def test_encart_scenario_mis_a_jour_propose_recommencer(tmp_path: Path) -> None:
    out = _js(
        tmp_path,
        """
mount({ ...FIRST, content_changed: { text: "Ce scénario a changé. Recommencez-le." } });
const card = $(".notice-card");
const shown = { title: text(".notice-title"), body: text(".notice-explanation"), button: text('.notice-card [data-action="restart-ask"]') };
card.querySelector("button").click();
const confirm = $(".restart-confirm") !== null;
mount(FIRST);
console.log(JSON.stringify({ shown, confirm, none: $(".notice-card") === null }));
""",
    )
    assert out["shown"] == {
        "title": "Scénario mis à jour",
        "body": "Ce scénario a changé. Recommencez-le.",
        "button": "Recommencer",
    }
    assert out["confirm"] is True
    assert out["none"] is True


def test_une_erreur_de_remise_a_zero_propose_le_diagnostic(tmp_path: Path) -> None:
    out = _js(
        tmp_path,
        """
const store = mount(FIRST);
const before = $(".scenario-error-link").hidden;
event(store, "app_error", { cause_text: "L'espace n'a pas pu être reconstruit.", action_text: "Voir le diagnostic, puis recommencez le scénario." });
const link = $(".scenario-error-link");
console.log(JSON.stringify({ before, hidden: link.hidden, label: link.textContent, href: link.getAttribute("href"),
  error: text(".scenario-error") }));
""",
    )
    assert out["before"] is True
    assert out["hidden"] is False
    assert (out["label"], out["href"]) == ("Voir le diagnostic", "/diagnostic")
    assert out["error"].startswith("L'espace n'a pas pu")
