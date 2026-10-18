# ruff: noqa: E501
"""Quiz (Story 4.5) exécuté sous Node, sur la doublure de DOM : cartes de commandes, bouton
inactif tant que rien n'est coché, bandeau d'état modifié, rétablissement et son échec. Le serveur
juge et écrit les textes ; le rendu réel (mise en page, lecteur d'écran) se vérifie dans un
navigateur."""

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
const {{ createStore }} = await import("@JS@/store.js");
const $ = (s) => document.querySelector(s);
const $$ = (s) => [...document.querySelectorAll(s)];
const PANEL = {{
  title_text: "Quiz", mode: "A", mode_text: "Mode A.", current_step_id: "annuler",
  quiz_altered: null, restore_failed: null,
  steps: [
    {{ step_id: "annuler", title_text: "Annuler le dernier commit", instruction_text: "Quelle commande ?",
       state: "current", explanation_text: "", explain_ref: "",
       quiz: {{ choices: [
         {{ choice_id: "reset_hard", command_text: "git reset --hard HEAD~1" }},
         {{ choice_id: "revert", command_text: "git revert --no-edit HEAD" }},
       ] }} }},
    {{ step_id: "ensuite", title_text: "Suite", instruction_text: "Continuez.",
       state: "todo", explanation_text: "", explain_ref: "" }},
  ],
}};
const posts = [];
globalThis.fetch = async (url, init) => {{
  posts.push([url, JSON.parse(init.body)]);
  return {{ ok: true, status: 202, json: async () => ({{}}) }};
}};
let seq = 5;
const event = (store, kind, payload) =>
  store.applyEvent({{ kind, boot_id: "b", seq: ++seq, epoch: 0, payload }});
const store = createStore();
store.applySnapshot({{ workspace_id: "llm.quiz.A", boot_id: "b", seq, epoch: 0, state: "idle",
  reason_text: "", fingerprint: "", views: {{}}, step_panel: PANEL }});
mountWorkspace(main, {{ title: "Quiz", store, storage: memoryStorage() }});
const text = (s) => ($(s) ? $(s).textContent : null);
const tick = () => new Promise((r) => setTimeout(r, 0));
const ALTERED = {{ step_id: "annuler", choice_id: "reset_hard", command_text: "git reset --hard HEAD~1",
  explanation_text: "`reset --hard` a effacé le commit.", first_attempt: true }};
"""


def _js(tmp_path: Path, body: str) -> dict:
    return json.loads(_run(tmp_path, f"{PRELUDE}\n{body}"))


def test_bouton_inactif_tant_que_rien_n_est_coche(tmp_path: Path) -> None:
    out = _js(
        tmp_path,
        """
const cards = $$(".quiz-card").map((c) => c.textContent);
const run = () => $(".quiz-run");
const reason = () => (run().nextElementSibling ? run().nextElementSibling.textContent : null);
const before = [run().getAttribute("aria-disabled"), reason()];
run().click();
await tick();
const clickedEarly = posts.length;
const radio = $('.quiz-radio[value="revert"]');
radio.checked = true;
radio.dispatchEvent(makeEvent("change", { bubbles: true }));
const after = [run().getAttribute("aria-disabled"), reason()];
run().click();
await tick();
console.log(JSON.stringify({ cards, before, clickedEarly, after, posts, label: run().textContent }));
""",
    )
    assert out["cards"] == ["git reset --hard HEAD~1", "git revert --no-edit HEAD"]
    assert out["before"] == ["true", "Choisissez une commande."]
    assert out["clickedEarly"] == 0
    assert out["after"] == [None, None]
    assert out["posts"] == [["/api/ws/llm.quiz.A/quiz_choice", {"choice_id": "revert"}]]
    assert out["label"] == "Exécuter ma réponse"


def test_mauvaise_reponse_bandeau_focus_et_retablissement(tmp_path: Path) -> None:
    out = _js(
        tmp_path,
        """
event(store, "engine_state", { state: "command", reason_text: "" });
event(store, "quiz_altered", ALTERED);
event(store, "engine_state", { state: "quiz_altered", reason_text: "" });
const banner = $(".quiz-banner");
const altered = {
  hidden: banner.hidden, text: banner.textContent, focus: document.activeElement === banner,
  explanation: text(".quiz-explanation"), status: text(".scenario-status"),
  runReason: [$(".quiz-run").nextElementSibling.textContent],
  inert: $(".views-grid").hasAttribute("inert"),
};
$(".quiz-restore").click();
await tick();
event(store, "engine_state", { state: "restoring", reason_text: "" });
const restoring = {
  text: text(".quiz-banner-text"), inert: $(".views-grid").hasAttribute("inert"),
  chips: $(".chips").hasAttribute("inert"), status: text(".scenario-status"),
  button: $(".quiz-restore").hidden,
};
event(store, "restore_ended", { status: "ok", snapshot_id: 1, reason_text: "" });
event(store, "engine_state", { state: "idle", reason_text: "" });
const done = {
  hidden: banner.hidden, inert: $(".views-grid").hasAttribute("inert"),
  focus: document.activeElement === $(".scenario-panel"), status: text(".scenario-status"),
  explanation: $(".quiz-explanation"), radios: $$(".quiz-radio").length,
};
event(store, "engine_state", { state: "command", reason_text: "" });
console.log(JSON.stringify({ altered, restoring, done, posts, later: text(".scenario-status") }));
""",
    )
    assert out["altered"]["hidden"] is False
    assert out["altered"]["text"].startswith("État modifié par le quiz — git reset --hard HEAD~1")
    assert "J'ai compris, rétablir l'état" in out["altered"]["text"]
    assert out["altered"]["focus"] is True
    assert out["altered"]["explanation"].endswith("`reset --hard` a effacé le commit.".replace("`", ""))
    assert out["altered"]["status"].startswith("État modifié par le quiz — git reset --hard")
    assert out["altered"]["runReason"] == ["Rétablissez d'abord l'état."]
    assert out["altered"]["inert"] is False
    assert out["restoring"]["text"] == "Rétablissement de l'état…"
    assert out["restoring"]["inert"] is True and out["restoring"]["chips"] is True
    assert out["restoring"]["status"] == "Rétablissement de l'état…"
    assert out["restoring"]["button"] is True
    assert out["done"]["hidden"] is True and out["done"]["inert"] is False
    assert out["done"]["focus"] is True
    assert out["done"]["status"] == "Rétabli."
    assert out["done"]["explanation"] is None
    assert out["done"]["radios"] == 2
    assert out["posts"] == [["/api/ws/llm.quiz.A/restore_state", {}]]
    assert out["later"] != "Rétabli."


def test_retablissement_echoue_encart_d_alerte_et_recommencer(tmp_path: Path) -> None:
    out = _js(
        tmp_path,
        """
event(store, "quiz_altered", ALTERED);
event(store, "engine_state", { state: "quiz_altered", reason_text: "" });
event(store, "engine_state", { state: "restoring", reason_text: "" });
event(store, "restore_ended", { status: "restore_failed", snapshot_id: 1, reason_text: "x" });
event(store, "engine_state", { state: "quiz_altered", reason_text: "" });
const notice = $('[data-notice="restore-failed"]');
const buttons = notice.querySelectorAll("button").map((b) => b.textContent);
notice.querySelector("button").click();
await tick();
console.log(JSON.stringify({
  role: notice.getAttribute("role"), text: notice.textContent, buttons, posts,
  banner: $(".quiz-banner").hidden, choices: $$(".quiz-radio").length,
}));
""",
    )
    assert out["role"] == "alert"
    assert (
        "L'état n'a pas pu être rétabli. Pour ne pas vous laisser sur un état faux, recommencez le scénario. Votre score du premier coup est conservé."
        in out["text"]
    )
    assert out["buttons"] == ["Recommencer"]
    assert out["posts"] == [["/api/ws/llm.quiz.A/restart", {}]]
    assert out["banner"] is True
    assert out["choices"] == 0


def test_rechargement_en_etat_modifie_affiche_le_bandeau(tmp_path: Path) -> None:
    out = _js(
        tmp_path,
        """
const panel = { ...PANEL, quiz_altered: { ...ALTERED } };
store.applySnapshot({ workspace_id: "llm.quiz.A", boot_id: "b", seq: 9, epoch: 0,
  state: "quiz_altered", reason_text: "", fingerprint: "", views: {}, step_panel: panel });
console.log(JSON.stringify({ hidden: $(".quiz-banner").hidden, text: text(".quiz-banner-text"),
  focus: document.activeElement === $(".quiz-banner") }));
""",
    )
    assert out["hidden"] is False
    assert out["text"] == "État modifié par le quiz — git reset --hard HEAD~1"
    assert out["focus"] is True
