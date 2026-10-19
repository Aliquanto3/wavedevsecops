# ruff: noqa: E501
"""Panneau Scénario (Story 4.1) exécuté sous Node, sur la doublure de DOM : ordre des éléments,
progression, consigne, explication, encart « État inattendu ». Les verdicts sont ceux du serveur
(`step_verdict`, `step_explanation`) : le front n'en calcule aucun. Le rendu réel (mise en page,
lecteur d'écran) se vérifie dans un navigateur."""

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
const {{ mountWorkspace, READY_TEXT }} = await import("@JS@/workspace.js");
const {{ createStore }} = await import("@JS@/store.js");
const $ = (s) => document.querySelector(s);
const $$ = (s) => [...document.querySelectorAll(s)];
const PANEL = {{
  title_text: "Scénario d'essai", mode: "A", mode_text: "Mode A : vous tapez les commandes.",
  current_step_id: "creer_branche",
  steps: [
    {{ step_id: "creer_branche", title_text: "Créer la branche", instruction_text: "Créez `feature`.",
       state: "current", explanation_text: "", explain_ref: "" }},
    {{ step_id: "commiter", title_text: "Faire un commit", instruction_text: "Commitez.",
       state: "todo", explanation_text: "", explain_ref: "" }},
  ],
}};
const snapshot = (panel) => ({{ workspace_id: "llm.essai.A", boot_id: "b", seq: 5, epoch: 0,
  state: "idle", reason_text: "", fingerprint: "", views: {{}}, step_panel: panel }});
let seq = 5;
const event = (store, kind, payload) =>
  store.applyEvent({{ kind, boot_id: "b", seq: ++seq, epoch: 0, payload }});
const selected = [];
const setup = (panel = PANEL) => {{
  const store = createStore();
  store.applySnapshot(snapshot(panel));
  main.replaceChildren();
  mountWorkspace(main, {{ title: "Scénario d'essai", store, storage: memoryStorage(),
    onSelect: (id) => selected.push(id) }});
  return store;
}};
const text = (s) => ($(s) ? $(s).textContent : null);
"""


def _js(tmp_path: Path, body: str) -> dict:
    return json.loads(_run(tmp_path, f"{PRELUDE}\n{body}"))


def test_ordre_et_progression(tmp_path: Path) -> None:
    out = _js(
        tmp_path,
        """
setup();
const body = $(".scenario-body");
const order = body.children.map((c) => c.className.split(" ")[0]);
const segments = $$(".step-segment").map((s) => [s.dataset.state, s.getAttribute("aria-disabled")]);
console.log(JSON.stringify({ order, count: text(".step-count"), badge: text(".mode-badge"),
  info: $(".mode-info").getAttribute("aria-expanded"), title: text(".step-title"),
  chat: text(".step-chat"), segments, status: text(".scenario-status"),
  firstChild: $(".scenario-panel").children.map((c) => c.className.split(" ")[0]) }));
""",
    )
    assert out["firstChild"] == [
        "scenario-panel-title",
        "scenario-body",
        "scenario-status",
        "scenario-error",
        "scenario-error-link",
    ]
    assert out["order"] == [
        "mode-row",
        "mode-text",
        "step-progress-nav",
        "step-instruction",
        "restart-foot",
    ]
    assert out["count"] == "Étape 1 sur 2"
    assert out["badge"] == "Mode A"
    assert out["info"] == "false"
    assert out["title"] == "Créer la branche"
    assert out["chat"] == "Créez feature."
    assert out["segments"] == [["current", None], ["todo", "true"]]
    assert out["status"] == "Étape 1 sur 2 : Créer la branche."


def test_bouton_i_du_mode(tmp_path: Path) -> None:
    out = _js(
        tmp_path,
        """
setup();
const hidden = () => $(".mode-text").hidden;
const before = hidden();
$(".mode-info").click();
const open = [hidden(), $(".mode-info").getAttribute("aria-expanded")];
$(".mode-info").click();
console.log(JSON.stringify({ before, open, after: hidden() }));
""",
    )
    assert out == {"before": True, "open": [False, "true"], "after": True}


def test_verdict_reussi_puis_explication(tmp_path: Path) -> None:
    out = _js(
        tmp_path,
        """
const store = setup();
event(store, "step_verdict", { step_id: "creer_branche", passed: true, status: "passed", next_step_id: "commiter",
  reason_text: "", expected_text: "", observed: [] });
const afterVerdict = { count: text(".step-count"), explanation: $(".step-explanation") !== null };
event(store, "step_explanation", { step_id: "creer_branche", explanation_text: "Une branche est un pointeur.", explain_ref: "graph.branch" });
const segments = $$(".step-segment").map((s) => [s.dataset.state, s.getAttribute("aria-disabled"), s.getAttribute("aria-current")]);
console.log(JSON.stringify({ afterVerdict, count: text(".step-count"), title: text(".step-title"),
  explanation: text(".step-explanation-text"), segments, status: text(".scenario-status"),
  order: $(".scenario-body").children.map((c) => c.className.split(" ")[0]) }));
""",
    )
    assert out["afterVerdict"] == {"count": "Étape 2 sur 2", "explanation": False}
    assert out["count"] == "Étape 2 sur 2"
    assert out["title"] == "Faire un commit"
    assert out["explanation"] == "Une branche est un pointeur."
    assert out["order"][-3:] == ["step-instruction", "step-explanation", "restart-foot"]
    assert out["segments"] == [["done", None, None], ["current", None, "step"]]
    assert out["status"] == "Étape réussie. Étape 2 sur 2 : Faire un commit."


def test_segment_termine_rouvre_sa_consigne(tmp_path: Path) -> None:
    out = _js(
        tmp_path,
        """
const store = setup();
event(store, "step_verdict", { step_id: "creer_branche", passed: true, status: "passed", next_step_id: "commiter" });
event(store, "step_explanation", { step_id: "creer_branche", explanation_text: "Expliqué.", explain_ref: "" });
$$(".step-segment")[0].click();
const reopened = { title: text(".step-title"), chat: text(".step-chat"), explanation: text(".step-explanation-text"),
  current: $$(".step-segment").map((s) => s.getAttribute("aria-current")), focus: document.activeElement.dataset.step };
$$(".step-segment")[1].click();
const back = { title: text(".step-title") };
$$(".step-segment")[1].click();
console.log(JSON.stringify({ reopened, back }));
""",
    )
    assert out["reopened"] == {
        "title": "Créer la branche",
        "chat": "Créez feature.",
        "explanation": "Expliqué.",
        "current": ["step", None],
        "focus": "creer_branche",
    }
    assert out["back"] == {"title": "Faire un commit"}


def test_encart_etat_inattendu(tmp_path: Path) -> None:
    out = _js(
        tmp_path,
        """
const store = setup();
event(store, "step_verdict", { step_id: "creer_branche", passed: false, status: "unexpected",
  expected_text: "Attendu : HEAD sur la branche `feature`.",
  observed: [{ text: "HEAD est sur la branche `autre`.", element_id: "ref:HEAD" }, { text: "Rien de lié." }],
  reason_text: "Rien n'est bloqué : vous pouvez continuer." });
const card = $(".notice-card");
const shown = {
  title: text(".notice-title"), role: card.getAttribute("role"), classes: card.className,
  expected: text(".notice-expected"), sees: text(".notice-sees"),
  links: $$(".element-link").map((l) => [l.dataset.elementId, l.textContent]),
  plain: $$(".notice-observed-item").map((i) => i.children.length),
  explanation: text(".notice-explanation"), action: text(".notice-actions .btn"),
  status: text(".scenario-status"), step: text(".step-count"),
};
$(".element-link").click();
$(".notice-actions .btn").click();
console.log(JSON.stringify({ shown, selected, gone: $(".notice-card") === null, step: text(".step-count") }));
""",
    )
    shown = out["shown"]
    assert shown["title"] == "État inattendu"
    assert shown["role"] == "group"
    assert "notice-card" in shown["classes"]
    assert shown["expected"] == "Attendu : HEAD sur la branche feature."
    assert shown["sees"] == "Ce que l'étape voit :"
    assert shown["links"] == [["ref:HEAD", "HEAD est sur la branche autre."]]
    assert shown["plain"] == [1, 0]
    assert shown["explanation"] == "Rien n'est bloqué : vous pouvez continuer."
    assert shown["action"] == "Continuer"
    assert shown["status"] == "État inattendu. Étape 1 sur 2 : Créer la branche."
    assert out["selected"] == ["ref:HEAD"]
    assert out["gone"] is True
    assert out["step"] == "Étape 1 sur 2"  # rien n'est bloqué : l'étape reste ouverte


def test_etat_prevu_dans_la_region_de_statut(tmp_path: Path) -> None:
    out = _js(
        tmp_path,
        """
const store = setup();
event(store, "step_verdict", { step_id: "creer_branche", passed: false, status: "failed",
  reason_text: "La branche `feature` existe, mais HEAD n'est pas dessus.", expected_text: "", observed: [] });
console.log(JSON.stringify({ status: text(".scenario-status"), card: $(".notice-card") !== null }));
""",
    )
    assert out["status"].startswith("La branche feature existe, mais HEAD n'est pas dessus.")
    assert out["card"] is False


def test_sans_etape_le_panneau_garde_son_message(tmp_path: Path) -> None:
    out = _js(
        tmp_path,
        """
setup(null);
console.log(JSON.stringify({ hidden: $(".scenario-body").hidden, status: text(".scenario-status"), ready: READY_TEXT }));
""",
    )
    assert out["hidden"] is True
    assert out["status"] == out["ready"]


def test_un_evenement_sans_rapport_ne_redessine_pas_le_panneau(tmp_path: Path) -> None:
    out = _js(
        tmp_path,
        """
const store = setup();
const before = $(".step-segment");
before.focus();
event(store, "engine_state", { state: "command", reason_text: "" });
event(store, "engine_state", { state: "idle", reason_text: "" });
console.log(JSON.stringify({ same: $(".step-segment") === before, focused: document.activeElement === before }));
""",
    )
    assert out == {"same": True, "focused": True}


def test_le_focus_survit_au_redessin_et_a_continuer(tmp_path: Path) -> None:
    """Revue 4.1 : un verdict redessine le panneau sans renvoyer le focus sur `body`."""
    out = _js(
        tmp_path,
        """
const store = setup();
$(".step-segment").focus();
const unexpected = { step_id: "creer_branche", passed: false, status: "unexpected",
  expected_text: "Attendu : x.", observed: [], reason_text: "Rien n'est bloqué." };
event(store, "step_verdict", unexpected);
const afterVerdict = document.activeElement.dataset.step || null;
const next = $(".notice-actions .btn");
next.focus();
next.click();
console.log(JSON.stringify({ afterVerdict, afterContinue: document.activeElement.className,
  body: document.activeElement === document.body }));
""",
    )
    assert out["afterVerdict"] == "creer_branche"
    assert out["afterContinue"] == "step-title"
    assert out["body"] is False
