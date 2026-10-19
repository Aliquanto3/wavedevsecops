# ruff: noqa: E501
"""Lire la correction dans les vues et dans le panneau (Story 5.5) sous Node, sur la doublure de
DOM : marques « Votre choix / Attendu / Accepté aussi » sur les éléments des vues, liste de
correction du panneau avec « voir dans les vues », case « validée » sans ✕, « Continuer » et
« Recommencer », reprise après rechargement. Le serveur corrige et écrit les textes (story 5.2) ;
le front ne décide de rien. Le rendu réel (tirets, contraste, lecteur d'écran) se vérifie dans un
navigateur."""

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
const A = "commit:" + "a".repeat(40);
const B = "commit:" + "b".repeat(40);
const C = "commit:" + "c".repeat(40);
const mk = (id, short, row) => ({{
  element_id: id, sha: id.slice(7), short_sha: short, subject: "Sujet " + short, actor: "agent",
  column: 0, row, parents: [], refs: [], head: false, detached_head: false, lost: false, new: false,
  restored: false, designable: true, a11y_name_text: "Commit " + short, explain_ref: "", links: [] }});
const VIEWS = {{
  graph: {{ columns: 1, head_text: "", edges: [], nodes: [mk(C, "ccccccc", 2), mk(B, "bbbbbbb", 1), mk(A, "aaaaaaa", 0)] }},
  staging: {{ staged: [], unstaged: [], untracked: [] }},
}};
const texts = {{ [A]: "aaaaaaa « Sujet aaaaaaa »", [B]: "bbbbbbb « Sujet bbbbbbb »", [C]: "ccccccc « Sujet ccccccc »" }};
const correction = (chosen, ok, equivalent = false) => ({{
  step_id: "q", correct: ok, summary_text: ok ? "Désignation juste." : "Désignation fausse : la correction est affichée, vous n'avez plus d'essai.",
  slots: [{{ slot_id: "main", label_text: "Votre réponse", element_id: chosen, correct: ok, equivalent,
    expected_element_id: A, accepted_element_ids: [A, C], element_texts: texts,
    text: ok ? "Votre réponse : bien vu." : "Votre réponse : bbbbbbb n'est pas l'élément en cause ; l'attendu est aaaaaaa." }}],
}});
const designate = {{ question_text: "Quel commit ?", accept: ["commit"], slots: [{{ slot_id: "main", label_text: "Votre réponse" }}] }};
const STEPS = (q) => [
  {{ step_id: "q", title_text: "Qui a cassé ?", instruction_text: "Regardez.", ...q }},
  {{ step_id: "suite", title_text: "Suite", instruction_text: "Fin.", state: "todo", explanation_text: "", explain_ref: "" }},
];
const panelOf = (steps, current) => ({{ title_text: "Agent", mode: "B", mode_text: "Mode B.",
  current_step_id: current, quiz_altered: null, restore_failed: null, steps }});
const OPEN = panelOf(STEPS({{ state: "current", explanation_text: "", explain_ref: "", designate }}), "q");
const reloaded = (corr) => panelOf([
  {{ step_id: "q", title_text: "Qui a cassé ?", instruction_text: "Regardez.", state: "done",
     explanation_text: "Le commit B a écrasé la sauvegarde.", explain_ref: "", correction: corr }},
  {{ step_id: "suite", title_text: "Suite", instruction_text: "Fin.", state: "current", explanation_text: "", explain_ref: "" }},
], "suite");
const posts = [];
const selected = [];
globalThis.fetch = async (url, init) => {{
  if (init && init.method === "POST") {{ posts.push([url, JSON.parse(init.body || "{{}}")]); return {{ ok: true, status: 202, json: async () => ({{}}) }}; }}
  return {{ ok: false, status: 404, json: async () => ({{}}) }};
}};
let seq = 1;
const event = (store, kind, payload) => store.applyEvent({{ kind, boot_id: "b", seq: ++seq, epoch: 0, payload }});
const setup = (panel) => {{
  const store = createStore();
  store.applySnapshot({{ workspace_id: "w", boot_id: "b", seq: 1, epoch: 0, state: "idle", reason_text: "",
    fingerprint: "", views: VIEWS, step_panel: panel }});
  main.replaceChildren();
  mountWorkspace(main, {{ title: "Agent", store, storage: memoryStorage(), onSelect: (id) => selected.push(id) }});
  return store;
}};
const answer = (store, corr) => {{
  event(store, "answer_corrected", corr);
  event(store, "step_verdict", {{ step_id: "q", status: "passed", next_step_id: "suite" }});
  event(store, "step_explanation", {{ step_id: "q", explanation_text: "Le commit B a écrasé la sauvegarde.", explain_ref: "" }});
}};
const marksOf = () => Object.fromEntries($$(".graph-node").map((n) => [n.getAttribute("data-element-id").slice(7, 10),
  [...n.querySelectorAll(".verdict-mark")].map((m) => m.textContent)]));
const tick = () => new Promise((r) => setTimeout(r, 0));
"""


def _js(tmp_path: Path, body: str) -> dict:
    return json.loads(_run(tmp_path, f"{PRELUDE}\n{body}"))


def test_une_reponse_fausse_marque_le_choix_l_attendu_et_les_equivalents(tmp_path: Path) -> None:
    out = _js(
        tmp_path,
        """
const store = setup(OPEN);
const before = marksOf();
answer(store, correction(B, false));
const node = (c) => $$(".graph-node").find((n) => n.getAttribute("data-element-id").includes(c));
console.log(JSON.stringify({
  before, marks: marksOf(),
  wrong: node("bbb").classList.contains("is-verdict-wrong"), right: node("aaa").classList.contains("is-verdict-expected"),
  label: node("bbb").getAttribute("aria-label"), expectedLabel: node("aaa").getAttribute("aria-label"),
  status: $('[role="status"]') ? $$('[role="status"]').map((s) => s.textContent).join(" | ") : "",
}));
""",
    )
    assert out["before"] == {"ccc": [], "bbb": [], "aaa": []}
    assert out["marks"] == {"ccc": ["≡ Accepté aussi"], "bbb": ["✗ Votre choix"], "aaa": ["✓ Attendu"]}
    assert out["wrong"] is True and out["right"] is True
    assert out["label"] == "Commit bbbbbbb — ✗ Votre choix"
    assert out["expectedLabel"] == "Commit aaaaaaa — ✓ Attendu"
    assert "Désignation fausse" in out["status"] and "Étape réussie" not in out["status"]


def test_un_choix_juste_ou_equivalent_porte_ses_deux_marques(tmp_path: Path) -> None:
    out = _js(
        tmp_path,
        """
const store = setup(OPEN);
answer(store, correction(C, true, true));
const first = marksOf();
const store2 = setup(OPEN);
answer(store2, correction(A, true));
console.log(JSON.stringify({ first, second: marksOf(), summary: $(".correction-summary").textContent }));
""",
    )
    assert out["first"] == {"ccc": ["✓ Votre choix", "≡ Accepté aussi"], "bbb": [], "aaa": ["✓ Attendu"]}
    assert out["second"] == {"ccc": ["≡ Accepté aussi"], "bbb": [], "aaa": ["✓ Votre choix", "✓ Attendu"]}
    assert out["summary"] == "Désignation juste."


def test_le_panneau_liste_l_attendu_et_les_equivalents_avec_voir_dans_les_vues(tmp_path: Path) -> None:
    out = _js(
        tmp_path,
        """
const store = setup(OPEN);
answer(store, correction(B, false));
const block = $(".step-explanation.is-correction");
const items = $$(".correction-item").map((i) => i.textContent);
const see = $$(".correction-see");
see[1].click();
const slot = $(".answer-slot");
console.log(JSON.stringify({
  title: $(".step-explanation-title").textContent, items, see: see.map((b) => b.textContent),
  seeIds: see.map((b) => b.getAttribute("data-element-id").slice(7, 10)), selected,
  slot: slot.textContent, clear: $$(".answer-clear").length, validated: slot.classList.contains("is-validated"),
  order: [...block.children].map((c) => c.className.split(" ")[0]),
  designateBlock: $$(".designate-block").length,
  actions: $$(".is-correction .btn").map((b) => b.textContent),
  foot: $$(".restart-foot .btn").map((b) => b.textContent),
}));
""",
    )
    assert out["title"] == "Correction"
    assert out["items"][0].startswith("✓ Attendu") and "aaaaaaa « Sujet aaaaaaa »" in out["items"][0]
    assert out["items"][1].startswith("≡ Accepté aussi") and "ccccccc" in out["items"][1]
    assert out["see"] == ["voir dans les vues", "voir dans les vues"]
    assert out["seeIds"] == ["aaa", "ccc"] and out["selected"] == ["commit:" + "c" * 40]
    assert "Votre réponse · validée" in out["slot"] and "✗ Votre choix" in out["slot"]
    assert "bbbbbbb « Sujet bbbbbbb »" in out["slot"]
    assert out["clear"] == 0 and out["validated"] is True
    # Ordre fixe : correction (titre, résumé, cases) puis explication.
    assert out["order"] == ["step-explanation-title", "correction-summary", "answer-slot", "step-explanation-text", "notice-actions"]
    assert out["designateBlock"] == 0
    assert out["actions"] == ["Continuer"]  # « Recommencer » est au pied du panneau (4.4)
    assert out["foot"] == ["Recommencer"]


def test_continuer_retire_les_marques_et_garde_l_explication(tmp_path: Path) -> None:
    out = _js(
        tmp_path,
        """
const store = setup(OPEN);
answer(store, correction(B, false));
$('[data-action="continue"]').click();
console.log(JSON.stringify({
  marks: marksOf(), badges: $$(".verdict-mark").length, block: $$(".is-correction").length,
  classes: $$(".has-verdict").length, label: $$(".graph-node")[1].getAttribute("aria-label"),
  explanation: $$(".step-explanation").map((e) => e.textContent),
}));
""",
    )
    assert out["marks"] == {"ccc": [], "bbb": [], "aaa": []}
    assert out["badges"] == 0 and out["block"] == 0 and out["classes"] == 0
    assert out["label"] == "Commit bbbbbbb"
    assert len(out["explanation"]) == 1 and "écrasé la sauvegarde" in out["explanation"][0]


def test_la_correction_revient_apres_un_rechargement_et_recommencer_la_retire(tmp_path: Path) -> None:
    out = _js(
        tmp_path,
        """
const store = setup(reloaded(correction(B, false)));
const marks = marksOf();
const hasBlock = $$(".is-correction").length;
const status = $$('[role="status"]').map((s) => s.textContent).join(" | ");
$('[data-action="restart-ask"]').click(); // confirmation en ligne de 4.4
$('[data-action="restart-confirm"]').click();
await tick();
store.setStepPanel(panelOf(STEPS({ state: "current", explanation_text: "", explain_ref: "", designate }), "q"));
console.log(JSON.stringify({ marks, hasBlock, posts, after: marksOf(), blocks: $$(".is-correction").length,
  armed: $$(".designate-block").length }));
""",
    )
    assert out["marks"] == {"ccc": ["≡ Accepté aussi"], "bbb": ["✗ Votre choix"], "aaa": ["✓ Attendu"]}
    assert out["hasBlock"] == 1
    assert len(out["posts"]) == 1 and out["posts"][0][0].endswith("/restart")
    assert out["after"] == {"ccc": [], "bbb": [], "aaa": []} and out["blocks"] == 0
    assert out["armed"] == 1  # la désignation est rouverte


def test_une_designation_suivante_armee_efface_les_marques_de_la_precedente(tmp_path: Path) -> None:
    out = _js(
        tmp_path,
        """
const next = panelOf([
  { step_id: "q", title_text: "Qui a cassé ?", instruction_text: "Regardez.", state: "done",
    explanation_text: "Le commit B a écrasé la sauvegarde.", explain_ref: "", correction: correction(B, false) },
  { step_id: "q2", title_text: "Et ensuite ?", instruction_text: "Désignez encore.", state: "current",
    explanation_text: "", explain_ref: "", designate },
], "q2");
const store = setup(next);
const shown = marksOf();
$(".designate-button").click();
const armed = marksOf();
const node = $$(".graph-node").find((n) => n.getAttribute("data-element-id").includes("aaa"));
node.click();
console.log(JSON.stringify({ shown, armed, picked: marksOf(), label: node.getAttribute("aria-label"),
  slot: $(".designate-slots").textContent, block: $$(".is-correction").length }));
""",
    )
    assert out["shown"]["bbb"] == ["✗ Votre choix"]
    assert out["armed"] == {"ccc": [], "bbb": [], "aaa": []}
    assert out["picked"] == {"ccc": [], "bbb": [], "aaa": []}
    assert out["label"] == "Commit aaaaaaa"
    assert "Attendu" not in out["slot"] and "aaaaaaa" in out["slot"]
    assert out["block"] == 1  # la correction précédente reste lisible dans le panneau


def test_la_marque_d_une_ref_s_entend_dans_le_nom_du_noeud(tmp_path: Path) -> None:
    out = _js(
        tmp_path,
        """
const REF = "ref:refs/heads/main";
VIEWS.graph.nodes[2].refs = [{ element_id: REF, kind: "branch", name_text: "main", current: true, designable: true }];
const store = setup(OPEN);
const corr = correction(B, false);
corr.slots[0].expected_element_id = REF;
corr.slots[0].accepted_element_ids = [REF];
answer(store, corr);
const node = () => $$(".graph-node").find((n) => n.getAttribute("data-element-id").includes("aaa"));
const marked = node().getAttribute("aria-label");
const pill = node().querySelector(".graph-branch").textContent;
$('[data-action="continue"]').click();
console.log(JSON.stringify({ marked, pill, after: node().getAttribute("aria-label") }));
""",
    )
    assert out["marked"] == "Commit aaaaaaa — main : ✓ Attendu"
    assert out["pill"].endswith("✓ Attendu")
    assert out["after"] == "Commit aaaaaaa"


def test_une_etape_rouverte_montre_la_correction_sans_continuer(tmp_path: Path) -> None:
    out = _js(
        tmp_path,
        """
const store = setup(reloaded(correction(B, false)));
$('[data-action="continue"]').click(); // marques fermées
const closed = marksOf();
$$(".step-segment")[0].click(); // rouvre l'étape terminée
console.log(JSON.stringify({ closed, reopened: marksOf(), actions: $$(".is-correction .btn").map((b) => b.textContent) }));
""",
    )
    assert out["closed"]["bbb"] == []
    assert out["reopened"]["bbb"] == ["✗ Votre choix"]
    assert out["actions"] == []  # rien à « Continuer » : on relit une étape passée
