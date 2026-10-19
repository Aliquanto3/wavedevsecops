# ruff: noqa: E501
"""Désignation dans les vues (Story 5.3) sous Node, sur la doublure de DOM : mode armé, case,
✕, Échap, validation, champ SHA. Le serveur marque les éléments `designable` et corrige (story
5.2, `tests/test_designation.py`) ; ici, le front ne fait que proposer et envoyer. Le rendu réel
(tirets, curseur, lecteur d'écran) se vérifie dans un navigateur."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from test_shell_js import NODE, _run

pytestmark = pytest.mark.skipif(NODE is None, reason="Node absent : comportement JS non exécuté")

MINIDOM = (Path(__file__).resolve().parent / "js" / "minidom.mjs").as_uri()

PRELUDE = f"""
import {{ installDom, memoryStorage, makeEvent, press }} from "{MINIDOM}";
const {{ document, main }} = installDom({{ width: 1920, height: 1080 }});
await import("@JS@/views.js");
const {{ mountWorkspace }} = await import("@JS@/workspace.js");
const {{ createStore }} = await import("@JS@/store.js");
const {{ selectionFor }} = await import("@JS@/selection.js");
const $ = (s) => document.querySelector(s);
const $$ = (s) => [...document.querySelectorAll(s)];
const A = "commit:" + "a".repeat(40);
const B = "commit:" + "b".repeat(40);
const C = "commit:" + "c".repeat(40);
const mk = (id, short, row, designable = true, refs = []) => ({{
  element_id: id, sha: id.slice(7), short_sha: short, subject: "Sujet " + short, actor: "agent",
  column: 0, row, parents: [], refs, head: false, detached_head: false, lost: false, new: false,
  restored: false, designable, a11y_name_text: "Commit " + short, explain_ref: "", links: [] }});
const ref = {{ element_id: "ref:refs/heads/main", kind: "branch", name_text: "main",
  a11y_name_text: "branche locale main", explain_ref: "", current: true, new: false, designable: true, links: [] }};
const VIEWS = {{
  graph: {{ columns: 1, head_text: "", edges: [], nodes: [
    mk(C, "ccccccc", 2, true, [ref]), mk(B, "bbbbbbb", 1, false), mk(A, "aaaaaaa", 0) ] }},
  staging: {{ staged: [], unstaged: [], untracked: [] }},
}};
const PANEL = {{
  title_text: "Agent", mode: "B", mode_text: "Mode B.", current_step_id: "q", quiz_altered: null, restore_failed: null,
  steps: [
    {{ step_id: "q", title_text: "Qu'a fait l'agent ?", instruction_text: "Regardez le dépôt.", state: "current",
       explanation_text: "", explain_ref: "",
       designate: {{ question_text: "Quel commit a écrasé le travail ?", accept: ["commit", "ref"],
         slots: [{{ slot_id: "main", label_text: "Votre réponse" }}] }} }},
    {{ step_id: "suite", title_text: "Suite", instruction_text: "Fin.", state: "todo", explanation_text: "", explain_ref: "" }},
  ],
}};
const posts = [];
let resolver = async () => ({{ ok: false, status: 404, json: async () => ({{ reason_text: "Aucun commit ne correspond à ce SHA dans le bac à sable." }}) }});
globalThis.fetch = async (url, init) => {{
  if (init && init.method === "POST") {{
    posts.push([url, JSON.parse(init.body)]);
    return {{ ok: true, status: 202, json: async () => ({{}}) }};
  }}
  return resolver(url);
}};
const store = createStore();
store.applySnapshot({{ workspace_id: "w", boot_id: "b", seq: 1, epoch: 0, state: "idle", reason_text: "",
  fingerprint: "", views: VIEWS, step_panel: PANEL }});
mountWorkspace(main, {{ title: "Agent", store, storage: memoryStorage() }});
const tick = () => new Promise((r) => setTimeout(r, 0));
const workspace = () => $(".workspace");
const slotText = () => $(".answer-slot").textContent;
"""


def _js(tmp_path: Path, body: str) -> dict:
    return json.loads(_run(tmp_path, f"{PRELUDE}\n{body}"))


def test_arme_le_mode_annonce_et_marque_les_designables(tmp_path: Path) -> None:
    out = _js(
        tmp_path,
        """
const button = $(".designate-button");
const before = [button.textContent, button.getAttribute("aria-pressed"), workspace().classList.contains("is-designating")];
button.click();
console.log(JSON.stringify({
  before,
  after: [button.textContent, button.getAttribute("aria-pressed"), workspace().classList.contains("is-designating")],
  live: $(".designate-block .designate-live").textContent,
  flags: $$(".graph-node").map((n) => n.getAttribute("data-designable")),
  pill: $(".graph-branch").getAttribute("data-designable"),
}));
""",
    )
    assert out["before"] == ["Désigner dans les vues", "false", False]
    assert out["after"] == ["Désignation active · Échap pour quitter", "true", True]
    assert "Désignation active" in out["live"] and "Échap" in out["live"]
    assert out["flags"] == ["true", "false", "true"]  # B n'est pas désignable
    assert out["pill"] == "true"


def test_clic_arme_place_remplace_et_vide_sans_toucher_la_selection(tmp_path: Path) -> None:
    out = _js(
        tmp_path,
        """
const nodes = () => $$(".graph-node");
$(".designate-button").click();
const empty = slotText();
nodes()[2].click(); // A
const first = slotText();
const outlined = nodes()[2].classList.contains("is-designated");
nodes()[0].click(); // C remplace A
const second = slotText();
const swapped = [nodes()[2].classList.contains("is-designated"), nodes()[0].classList.contains("is-designated")];
nodes()[1].click(); // B non désignable : pas de choix (la sélection ordinaire s'applique)
const third = slotText();
$(".answer-clear").click();
console.log(JSON.stringify({ empty, first, outlined, second, swapped, third, cleared: slotText(),
  selection: selectionFor(store).value }));
""",
    )
    assert "Aucun élément choisi" in out["empty"]
    assert "aaaaaaa" in out["first"] and out["outlined"] is True
    assert "ccccccc" in out["second"] and "aaaaaaa" not in out["second"]
    assert out["swapped"] == [False, True]
    assert "ccccccc" in out["third"]
    assert "Aucun élément choisi" in out["cleared"]
    assert out["selection"] == "commit:" + "b" * 40  # seul le clic non capté a sélectionné


def test_clic_sur_une_etiquette_de_ref_designe_la_ref(tmp_path: Path) -> None:
    out = _js(
        tmp_path,
        """
$(".designate-button").click();
$(".graph-branch").click();
$(".designate-submit").click();
await tick();
console.log(JSON.stringify({ slot: slotText(), posts }));
""",
    )
    assert "main" in out["slot"]
    assert out["posts"][0][1] == {"step_id": "q", "slots": ["ref:refs/heads/main"]}


def test_desarme_le_clic_ne_sert_qu_aux_correspondances(tmp_path: Path) -> None:
    out = _js(
        tmp_path,
        """
$$(".graph-node")[2].click();
console.log(JSON.stringify({ slot: slotText(), selection: selectionFor(store).value }));
""",
    )
    assert "Aucun élément choisi" in out["slot"]
    assert out["selection"] == "commit:" + "a" * 40


def test_echap_desarme_sans_vider_la_case_et_rend_le_focus(tmp_path: Path) -> None:
    out = _js(
        tmp_path,
        """
const button = $(".designate-button");
button.click();
$$(".graph-node")[0].click();
const node = $$(".graph-node")[0];
node.setAttribute("tabindex", "0");
node.focus();
const ev = press("Escape");
console.log(JSON.stringify({
  armed: workspace().classList.contains("is-designating"), pressed: button.getAttribute("aria-pressed"),
  label: button.textContent, slot: slotText(), focusOnButton: document.activeElement === button,
  stopped: ev._stop === true,
  live: $(".designate-block .designate-live").textContent,
}));
""",
    )
    assert out["armed"] is False and out["pressed"] == "false"
    assert out["label"] == "Désigner dans les vues"
    assert "ccccccc" in out["slot"]
    assert out["focusOnButton"] is True and out["stopped"] is True
    assert "désactivée" in out["live"]


def test_validation_envoie_step_id_et_cases_et_reste_inactive_si_vide(tmp_path: Path) -> None:
    out = _js(
        tmp_path,
        """
const submit = $(".designate-submit");
const reason = () => (submit.nextElementSibling && submit.nextElementSibling.classList.contains("btn-reason") ? submit.nextElementSibling.textContent : null);
const emptyState = [submit.getAttribute("aria-disabled"), reason()];
submit.click();
await tick();
const early = posts.length;
$(".designate-button").click();
$$(".graph-node")[0].click();
const ready = submit.getAttribute("aria-disabled");
submit.click();
await tick();
console.log(JSON.stringify({ emptyState, early, ready, posts,
  once: document.getElementById(submit.getAttribute("aria-describedby")) && document.getElementById(submit.getAttribute("aria-describedby")).textContent,
  tab: [!!$(".answer-clear"), !!$(".sha-field"), !!$(".designate-submit")],
  label: $(".sha-label").textContent }));
""",
    )
    assert out["emptyState"][0] == "true" and out["emptyState"][1]
    assert out["early"] == 0
    assert out["ready"] is None
    assert out["posts"] == [["/api/ws/w/answer_submit", {"step_id": "q", "slots": ["commit:" + "c" * 40]}]]
    assert out["tab"] == [True, True, True]
    assert out["label"] == "Ou saisir un SHA"


def test_champ_sha_place_un_commit_ou_signale_l_erreur(tmp_path: Path) -> None:
    out = _js(
        tmp_path,
        """
const field = $(".sha-field");
field.value = "zzzzzzz";
press("Enter", { target: field });
await tick(); await tick();
const bad = [field.getAttribute("aria-invalid"), $(".sha-error").textContent, slotText()];
resolver = async (url) => ({ ok: true, status: 200, json: async () => ({ element_id: A, short_sha: "aaaaaaa", subject: "Add config" }) });
field.value = "aaaaaaa";
press("Enter", { target: field });
await tick(); await tick();
console.log(JSON.stringify({ bad, good: [field.getAttribute("aria-invalid"), $(".sha-error").textContent, slotText()] }));
""",
    )
    assert out["bad"][0] == "true"
    assert "Aucun commit ne correspond" in out["bad"][1]
    assert "Aucun élément choisi" in out["bad"][2]
    assert out["good"][0] is None and out["good"][1] == ""
    assert "aaaaaaa" in out["good"][2]


def test_changement_d_etape_vide_la_case_et_desarme(tmp_path: Path) -> None:
    out = _js(
        tmp_path,
        """
$(".designate-button").click();
$$(".graph-node")[0].click();
let seq = 2;
store.applyEvent({ kind: "step_verdict", boot_id: "b", seq: seq++, epoch: 0, payload: { step_id: "q", status: "passed", next_step_id: "suite" } });
console.log(JSON.stringify({ block: !!$(".designate-block"), armed: workspace().classList.contains("is-designating") }));
""",
    )
    assert out == {"block": False, "armed": False}


def test_double_clic_sur_valider_n_envoie_qu_une_reponse(tmp_path: Path) -> None:
    """Revue M1 : la garde est posée au clic, avant la réponse du serveur ; un échec la lève."""
    out = _js(
        tmp_path,
        """
const submit = $(".designate-submit");
$(".designate-button").click();
$$(".graph-node")[0].click();
submit.click();
submit.click();
const during = submit.getAttribute("aria-disabled");
await tick(); await tick();
const afterOk = [posts.length, submit.getAttribute("aria-disabled")];
// Le moteur passe occupé puis revient au repos sans changer d'étape (refus dans la file) : la garde tombe.
let seq = 2;
store.applyEvent({ kind: "engine_state", boot_id: "b", seq: seq++, epoch: 0, payload: { state: "running", reason_text: "" } });
store.applyEvent({ kind: "engine_state", boot_id: "b", seq: seq++, epoch: 0, payload: { state: "idle", reason_text: "" } });
const released = submit.getAttribute("aria-disabled");
// Un envoi refusé (409) lève aussi la garde.
globalThis.fetch = async (url, init) => {
  posts.push([url, JSON.parse(init.body)]);
  return { ok: false, status: 409, json: async () => ({ reason_text: "Refusé." }) };
};
submit.click();
await tick(); await tick(); await tick();
console.log(JSON.stringify({ during, afterOk, released, refused: [posts.length, submit.getAttribute("aria-disabled")] }));
""",
    )
    assert out["during"] == "true"
    assert out["afterOk"] == [1, "true"]
    assert out["released"] is None
    assert out["refused"] == [2, None]


def test_sha_resolu_hors_type_ou_apres_changement_d_etape_ne_remplit_rien(tmp_path: Path) -> None:
    """Revue L3 : un commit non attendu est signalé ; une résolution tardive ne remplit pas l'étape suivante."""
    out = _js(
        tmp_path,
        """
const field = $(".sha-field");
let release;
resolver = () => new Promise((r) => { release = () => r({ ok: true, status: 200, json: async () => ({ element_id: A, short_sha: "aaaaaaa", subject: "Add config" }) }); });
field.value = "aaaaaaa";
press("Enter", { target: field });
await tick();
const panel2 = structuredClone(PANEL);
panel2.steps[0].step_id = "q2";
panel2.current_step_id = "q2";
panel2.steps[0].designate.accept = ["diffline"];
store.applySnapshot({ workspace_id: "w", boot_id: "b", seq: 5, epoch: 0, state: "idle", reason_text: "",
  fingerprint: "", views: VIEWS, step_panel: panel2 });
release();
await tick(); await tick(); await tick();
const stale = slotText();
resolver = async () => ({ ok: true, status: 200, json: async () => ({ element_id: A, short_sha: "aaaaaaa", subject: "Add config" }) });
const f2 = $(".sha-field");
f2.value = "aaaaaaa";
press("Enter", { target: f2 });
await tick(); await tick(); await tick();
console.log(JSON.stringify({ stale, typed: [slotText(), $(".sha-error").textContent, f2.getAttribute("aria-invalid")] }));
""",
    )
    assert "Aucun élément choisi" in out["stale"]
    assert "Aucun élément choisi" in out["typed"][0]
    assert out["typed"][1] == "Cette question n'attend pas de commit."
    assert out["typed"][2] == "true"


def test_la_liaison_entre_vues_ne_gene_pas_le_mode_designer(tmp_path: Path) -> None:
    """Story 2.10 : survol et focus montrent les liens, le clic armé désigne sans sélectionner."""
    out = _js(
        tmp_path,
        """
store.applySnapshot({ workspace_id: "w", boot_id: "b", seq: 2, epoch: 0, state: "idle", reason_text: "",
  fingerprint: "", views: { ...VIEWS, links: { [C]: [A] }, names: { [C]: "commit ccccccc", [A]: "commit aaaaaaa" } }, step_panel: PANEL });
await tick();
const nodes = () => $$(".graph-node");
$(".designate-button").click();
nodes()[0].dispatchEvent(makeEvent("pointerover"));
const hovered = { armed: workspace().classList.contains("is-designating"), linked: nodes().map((n) => n.classList.contains("is-linked")) };
nodes()[0].click();   // armé : désigne C, ne sélectionne rien
console.log(JSON.stringify({ hovered, slot: slotText(), selection: selectionFor(store).value }));
""",
    )
    assert out["hovered"] == {"armed": True, "linked": [True, False, True]}
    assert "ccccccc" in out["slot"] and out["selection"] is None


# ------------------------------------------------------------------ Story 5.4
def test_liste_filtrable_groupe_par_vue_filtre_et_marque_choisi(tmp_path: Path) -> None:
    out = _js(
        tmp_path,
        """
const toggle = $(".designate-list-toggle");
const closed = [toggle.getAttribute("aria-expanded"), $(".designate-list-box").hidden, toggle.textContent];
toggle.click();
const items = () => $$(".designate-item").map((b) => b.getAttribute("data-element-id"));
const opened = [toggle.getAttribute("aria-expanded"), items(), $$(".designate-group-title").map((n) => n.textContent),
  $(".designate-filter-label").textContent];
const filter = $(".designate-filter");
filter.value = "sujet ccc";
filter.dispatchEvent(makeEvent("input"));
const filtered = items();
filter.value = "refs/heads";
filter.dispatchEvent(makeEvent("input"));
const byPath = items();
filter.value = "zzz";
filter.dispatchEvent(makeEvent("input"));
const none = $(".designate-list-empty").textContent;
filter.value = "";
filter.dispatchEvent(makeEvent("input"));
$$(".designate-item").find((b) => b.getAttribute("data-element-id") === C).click();
const chosen = $$(".designate-item").find((b) => b.getAttribute("data-element-id") === C);
console.log(JSON.stringify({ closed, opened, filtered, byPath, none, slot: slotText(),
  chosen: [chosen.textContent, chosen.getAttribute("aria-pressed")] }));
""",
    )
    assert out["closed"][:2] == ["false", True] and "▾" in out["closed"][2]
    assert out["opened"][0] == "true"
    assert out["opened"][1][0].startswith("commit:") and "ref:refs/heads/main" in out["opened"][1]
    assert "commit:" + "b" * 40 not in out["opened"][1]  # non désignable : absent de la liste
    assert out["opened"][2] == ["Graphe"]
    assert out["opened"][3] == "Filtrer par nom, SHA ou chemin"
    assert out["filtered"] == ["commit:" + "c" * 40]
    assert out["byPath"] == ["ref:refs/heads/main"]
    assert "Aucun élément ne correspond" in out["none"]
    assert "ccccccc" in out["slot"]
    assert "choisi" in out["chosen"][0] and out["chosen"][1] == "true"


def test_apercu_du_sha_en_direct_puis_placement(tmp_path: Path) -> None:
    out = _js(
        tmp_path,
        """
const field = $(".sha-field");
const urls = [];
resolver = async (url) => { urls.push(url); return { ok: true, status: 200, json: async () => ({ element_id: A, short_sha: "aaaaaaa", subject: "Add config", actor: "agent" }) }; };
const wait = () => new Promise((r) => setTimeout(r, 350));
field.value = "aaa";
field.dispatchEvent(makeEvent("input"));
await wait();
const short = [urls.length, $(".sha-preview").textContent];
field.value = "aaaaaaa";
field.dispatchEvent(makeEvent("input"));
await wait();
const preview = $(".sha-preview");
const shown = [preview.textContent, preview.getAttribute("role"), slotText(), $(".sha-place").hidden];
$(".sha-place").click();
await tick(); await tick();
console.log(JSON.stringify({ short, shown, after: slotText(), left: preview.textContent, value: field.value, calls: urls.length }));
""",
    )
    assert out["short"] == [0, ""]  # sous 7 caractères : aucune requête
    assert out["shown"][0] == "aaaaaaa · Add config · Agent"
    assert out["shown"][1] == "status" and out["shown"][3] is False
    assert "Aucun élément choisi" in out["shown"][2]  # l'aperçu ne place rien
    assert "aaaaaaa" in out["after"] and out["left"] == "" and out["value"] == ""
    assert out["calls"] == 1  # le placement réutilise l'aperçu


def test_sha_inconnu_en_direct_aria_invalid_et_alerte_sans_case(tmp_path: Path) -> None:
    out = _js(
        tmp_path,
        """
const field = $(".sha-field");
const wait = () => new Promise((r) => setTimeout(r, 350));
field.value = "deadbee";
field.dispatchEvent(makeEvent("input"));
await wait();
const err = $(".sha-error");
const bad = [field.getAttribute("aria-invalid"), err.textContent, err.getAttribute("role"), slotText(), posts.length, $(".sha-place").hidden];
field.value = "deadbeef";
field.dispatchEvent(makeEvent("input"));
const cleared = [field.getAttribute("aria-invalid"), err.textContent];
console.log(JSON.stringify({ bad, cleared }));
""",
    )
    assert out["bad"][0] == "true"
    assert out["bad"][1] == "Aucun commit ne correspond à ce SHA dans le bac à sable."
    assert out["bad"][2] == "alert" and "Aucun élément choisi" in out["bad"][3]
    assert out["bad"][4] == 0 and out["bad"][5] is True  # aucune réponse envoyée : l'essai reste entier
    assert out["cleared"] == [None, ""]


def test_revue_apercu_perime_entree_pendant_l_attente_et_focus_apres_placer(tmp_path: Path) -> None:
    """Revue 5.4 : M1 (aperçu de l'étape précédente), L2 (Entrée et anti-rebond), L3 (focus)."""
    out = _js(
        tmp_path,
        """
const field = $(".sha-field");
const urls = [];
const okA = { ok: true, status: 200, json: async () => ({ element_id: A, short_sha: "aaaaaaa", subject: "Add config" }) };
resolver = async (url) => { urls.push(url); return okA; };
const wait = () => new Promise((r) => setTimeout(r, 350));
// L3 : « Placer » rend le focus au champ.
field.value = "aaaaaaa";
field.dispatchEvent(makeEvent("input"));
await wait();
$(".sha-place").focus();
$(".sha-place").click();
await tick(); await tick();
const focusAfterPlace = document.activeElement === field;
$(".answer-clear").click();
// M1 : aperçu posé, puis l'étape change pour une étape qui n'attend que des refs.
field.value = "aaaaaaa";
field.dispatchEvent(makeEvent("input"));
await wait();
const panel2 = structuredClone(PANEL);
panel2.steps[0].step_id = "q2";
panel2.current_step_id = "q2";
panel2.steps[0].designate.accept = ["ref"];
store.applySnapshot({ workspace_id: "w", boot_id: "b", seq: 5, epoch: 0, state: "idle", reason_text: "",
  fingerprint: "", views: VIEWS, step_panel: panel2 });
await tick();
const cleared = [$(".sha-preview").textContent, $(".sha-place").hidden];
press("Enter", { target: field });
await tick(); await tick(); await tick();
const refused = [slotText(), $(".sha-error").textContent, field.getAttribute("aria-invalid")];
// L2 : Entrée avant la fin de l'anti-rebond, réponse lente : le commit est placé, une seule requête.
const panel3 = structuredClone(PANEL);
panel3.steps[0].step_id = "q3";
panel3.current_step_id = "q3";
store.applySnapshot({ workspace_id: "w", boot_id: "b", seq: 6, epoch: 0, state: "idle", reason_text: "",
  fingerprint: "", views: VIEWS, step_panel: panel3 });
await tick();
urls.length = 0;
resolver = (url) => { urls.push(url); return new Promise((r) => setTimeout(() => r(okA), 400)); };
field.value = "aaaaaaa";
field.dispatchEvent(makeEvent("input"));
press("Enter", { target: field });
await new Promise((r) => setTimeout(r, 700));
console.log(JSON.stringify({ focusAfterPlace, cleared, refused, slow: [slotText(), urls.length] }));
""",
    )
    assert out["focusAfterPlace"] is True
    assert out["cleared"] == ["", True]
    assert "Aucun élément choisi" in out["refused"][0]
    assert out["refused"][1] == "Cette question n'attend pas de commit." and out["refused"][2] == "true"
    assert "aaaaaaa" in out["slow"][0] and out["slow"][1] == 1


def test_echap_quitte_d_abord_le_mode_designer_puis_ferme_la_chaine(tmp_path: Path) -> None:
    """Arbitrage 5.3 : chaîne ouverte et mode Désigner actif, un premier Échap quitte le mode
    (la chaîne reste ouverte), un second Échap ferme la chaîne."""
    from test_chain_band_dom import MAP_CHAIN  # noqa: PLC0415

    prelude = PRELUDE.replace("mountWorkspace(main,", "const first = mountWorkspace(main,", 1)
    script = f"""{prelude}
first.destroy();
$("#pane-menu").remove();
main.replaceChildren();
mountWorkspace(main, {{ title: "Agent", store, storage: memoryStorage(), chain: {json.dumps(MAP_CHAIN)} }});
const toggle = $("#chain-map-toggle"), map = $("#chain-map");
const button = $(".designate-button");
button.click();
toggle.click();
const state = () => ({{ armed: workspace().classList.contains("is-designating"), chainHidden: map.hidden }});
const r = {{ both: state() }};
press("Escape", {{ target: document.body }}); // focus hors de l'espace
r.first = state();
press("Escape", {{ target: document.body }});
r.second = state();
console.log(JSON.stringify(r));
"""
    out = json.loads(_run(tmp_path, script))
    assert out["both"] == {"armed": True, "chainHidden": False}
    assert out["first"] == {"armed": False, "chainHidden": False}
    assert out["second"] == {"armed": False, "chainHidden": True}
