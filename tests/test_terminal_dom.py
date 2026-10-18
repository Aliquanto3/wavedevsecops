# ruff: noqa: E501
"""Volet Terminal (Story 2.4) exécuté sous Node, sur la doublure de DOM de `tests/js/minidom.mjs`.

La doublure n'a ni mise en page ni vrai clavier : l'apparence, le défilement réel, la sélection
de texte et la lecture par un lecteur d'écran se vérifient dans un navigateur.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from test_shell_js import NODE, _run

pytestmark = pytest.mark.skipif(NODE is None, reason="Node absent : comportement JS non exécuté")

MINIDOM = (Path(__file__).resolve().parent / "js" / "minidom.mjs").as_uri()

PRELUDE = f"""
import {{ installDom, makeEvent, press }} from "{MINIDOM}";
const {{ document, main }} = installDom({{ width: 1920, height: 1080 }});
const {{ createStore }} = await import("@JS@/store.js");
const T = await import("@JS@/terminal.js");
const store = createStore();
store.reset("llm.bac-a-sable-libre.A");
const calls = [];
let reply = () => ({{ ok: true, status: 202, json: async () => ({{}}) }});
globalThis.fetch = async (url, options) => {{
  calls.push({{ url, body: JSON.parse(options.body), method: options.method }});
  return reply();
}};
let seq = 0;
const send = (kind, payload) => store.applyEvent({{ boot_id: "b", seq: ++seq, epoch: 0, kind, payload }});
store.applySnapshot({{ workspace_id: "llm.bac-a-sable-libre.A", boot_id: "b", seq: 0, epoch: 0, state: "idle", views: {{}} }});
const out = (stream, text, lang = "") => send("terminal_output", {{ stream, text, lang, spans: [] }});
const state = (name) => send("engine_state", {{ state: name, reason_text: "" }});
let now = 1_000_000;
const timers = {{ setInterval: () => 7, clearInterval() {{}} }};
const realNow = Date.now;
Date.now = () => now;
const term = T.createTerminal(main, {{ store, timers }});
const $ = (s) => main.querySelector(s);
const $$ = (s) => main.querySelectorAll(s);
const type = (text) => {{ term.input.value = text; }};
const key = (k, init = {{}}) => {{
  const event = makeEvent("keydown", {{ key: k, ...init }});
  term.input.dispatchEvent(event);
  return event;
}};
const flush = () => new Promise((r) => setTimeout(r, 0));
"""


def _js(tmp_path: Path, body: str) -> dict:
    return json.loads(_run(tmp_path, f"{PRELUDE}\n{body}"))


def test_rendu_des_flux_et_des_composants(tmp_path: Path) -> None:
    out = _js(
        tmp_path,
        """
const before = { empty: $(".terminal-empty").hidden, title: $(".terminal-empty .empty-title").textContent };
out("stdout", "On branch main\\n", "en");
out("stderr", "fatal: bad\\n", "en");
out("stdout", "Sur la branche main\\n", "fr");
out("exit", "Code de sortie : 128");
out("app", "git attend un message de commit. Ajoutez `-m \\"…\\"`.");
out("refused", "« | » n'a aucun effet.");
const log = $(".terminal-log");
const kids = [...log.children];
console.log(JSON.stringify({
  before,
  emptyAfter: $(".terminal-empty").hidden,
  role: log.getAttribute("role"),
  label: log.getAttribute("aria-label"),
  classes: kids.map((k) => k.className),
  langs: kids.map((k) => k.getAttribute("lang")),
  stderrPrefix: kids[1].querySelector(".visually-hidden").textContent,
  stderrText: kids[1].textContent,
  appMark: kids[4].querySelector(".terminal-app-mark").textContent,
  appCode: kids[4].querySelector("code").textContent,
  refusedRole: kids[5].getAttribute("role"),
  exitText: kids[3].textContent,
  inRunning: $(".terminal-running").hidden,
}));
""",
    )
    assert out["before"] == {"empty": False, "title": "Tapez une commande git."}
    assert out["emptyAfter"] is True
    assert (out["role"], out["label"]) == ("log", "Sortie du terminal")
    assert out["classes"] == [
        "terminal-chunk terminal-stdout",
        "terminal-chunk terminal-stderr",
        "terminal-chunk terminal-stdout",
        "terminal-line terminal-exit-error",
        "terminal-line terminal-app-message",
        "terminal-line terminal-refused",
    ]
    assert out["langs"] == ["en", "en", None, None, None, None]
    assert out["stderrPrefix"] == "erreur standard : "
    assert out["stderrText"] == "erreur standard : fatal: bad\n"
    assert out["appMark"] == "› "
    assert out["appCode"] == '-m "…"'
    assert out["refusedRole"] == "alert"
    assert out["exitText"] == "Code de sortie : 128"


def test_entree_envoie_la_ligne_et_garde_l_historique(tmp_path: Path) -> None:
    out = _js(
        tmp_path,
        """
store.applyEvent({ boot_id: "b", seq: ++seq, epoch: 0, kind: "state_projected", payload: { views: { prompt: { text: "main" } }, fingerprint: "f" } });
type("  git status  ");
const enter = key("Enter");
await flush();
type("git log --oneline");
key("Enter");
await flush();
type("brouillon");
const up1 = (key("ArrowUp"), term.input.value);
const up2 = (key("ArrowUp"), term.input.value);
const up3 = (key("ArrowUp"), term.input.value);
const down1 = (key("ArrowDown"), term.input.value);
const down2 = (key("ArrowDown"), term.input.value);
const down3 = (key("ArrowDown"), term.input.value);
key("Enter");
await flush();
const typed = $$(".terminal-command").map((n) => n.textContent);
console.log(JSON.stringify({
  calls, prevented: enter.defaultPrevented, up: [up1, up2, up3], down: [down1, down2, down3], typed,
  prompt: $(".terminal-form .terminal-prompt").textContent, value: term.input.value,
}));
""",
    )
    assert [c["url"] for c in out["calls"]] == ["/api/ws/llm.bac-a-sable-libre.A/terminal_line"] * 3
    assert [c["body"]["line"] for c in out["calls"]] == ["git status", "git log --oneline", "brouillon"]
    assert all(c["method"] == "POST" for c in out["calls"])
    assert out["prevented"] is True
    assert out["up"] == ["git log --oneline", "git status", "git status"]
    assert out["down"] == ["git log --oneline", "brouillon", "brouillon"]
    assert out["typed"] == ["main $ git status", "main $ git log --oneline", "main $ brouillon"]
    assert out["prompt"] == "main $ "
    assert out["value"] == ""


def test_ctrl_l_efface_l_affichage_pas_l_historique(tmp_path: Path) -> None:
    out = _js(
        tmp_path,
        """
type("git status"); key("Enter"); await flush();
out("stdout", "x\\n");
const clear = key("l", { ctrlKey: true });
const afterClear = { nodes: $(".terminal-log").children.length, empty: $(".terminal-empty").hidden };
out("stdout", "y\\n");
const recall = (key("ArrowUp"), term.input.value);
console.log(JSON.stringify({ afterClear, prevented: clear.defaultPrevented, later: $(".terminal-log").children.length, recall }));
""",
    )
    assert out["afterClear"] == {"nodes": 0, "empty": False}
    assert out["prevented"] is True
    assert out["later"] == 1
    assert out["recall"] == "git status"


def test_commande_en_cours_saisie_inactive_chronometre_et_ctrl_c(tmp_path: Path) -> None:
    out = _js(
        tmp_path,
        """
state("command");
const readonly = [term.input.hasAttribute("readonly"), term.input.getAttribute("aria-readonly")];
type("git log"); key("Enter"); await flush();
const ignored = calls.length;
const hiddenAt0 = $(".terminal-running").hidden;
term.tick(now + 500);
const hiddenAtHalf = $(".terminal-running").hidden;
term.tick(now + 2600);
const shown = [$(".terminal-running").hidden, $(".terminal-running").textContent];
const insideLog = $(".terminal-log").contains($(".terminal-running"));
const liveRoles = [$(".terminal-running").getAttribute("role"), $(".terminal-running").getAttribute("aria-live")];
const ctrlC = key("c", { ctrlKey: true });
await flush();
state("idle");
console.log(JSON.stringify({
  readonly, ignored, hiddenAt0, hiddenAtHalf, shown, insideLog, liveRoles,
  prevented: ctrlC.defaultPrevented, calls,
  afterIdle: [term.input.hasAttribute("readonly"), $(".terminal-running").hidden],
}));
""",
    )
    assert out["readonly"] == [True, "true"]
    assert out["ignored"] == 0  # Entrée est ignorée tant qu'une commande tourne
    assert out["hiddenAt0"] is True and out["hiddenAtHalf"] is True
    assert out["shown"] == [False, "En cours… 2 s"]
    assert out["insideLog"] is False  # hors de la région live
    assert out["liveRoles"] == [None, None]
    assert out["prevented"] is True
    assert [c["url"] for c in out["calls"]] == ["/api/ws/llm.bac-a-sable-libre.A/interrupt"]
    assert out["afterIdle"] == [False, True]


def test_ctrl_c_hors_commande_abandonne_la_ligne_et_tab_sort(tmp_path: Path) -> None:
    out = _js(
        tmp_path,
        """
type("git comm");
const ctrlC = key("c", { ctrlKey: true });
const value = term.input.value;
const tab = key("Tab");
const escape = key("Escape");
console.log(JSON.stringify({ value, ctrlC: ctrlC.defaultPrevented, tab: tab.defaultPrevented, escape: escape.defaultPrevented, calls: calls.length }));
""",
    )
    assert out == {"value": "", "ctrlC": True, "tab": False, "escape": False, "calls": 0}


def test_refus_du_serveur_s_affiche_dans_le_terminal(tmp_path: Path) -> None:
    out = _js(
        tmp_path,
        """
reply = () => ({ ok: false, status: 409, json: async () => ({ reason_text: "Le dépôt est dans l'état du quiz." }) });
type("git add ."); key("Enter"); await flush(); await flush();
reply = () => { throw new Error("réseau"); };
type("git status"); key("Enter"); await flush(); await flush();
const refused = $$(".terminal-refused").map((n) => [n.textContent, n.getAttribute("role")]);
console.log(JSON.stringify({ refused }));
""",
    )
    assert out["refused"] == [
        ["Le dépôt est dans l'état du quiz.", "alert"],
        ["WaveDevSecOps ne répond pas. Rechargez la page.", "alert"],
    ]


def test_au_dela_de_5000_lignes_les_plus_anciennes_sont_masquees(tmp_path: Path) -> None:
    result = _run(
        tmp_path,
        f"""{PRELUDE}
out("stdout", "a\\nb\\nc\\n");
for (let i = 0; i < 4999; i++) out("stdout", `ligne ${{i}}\\n`);
const first = $(".terminal-log").children[0].textContent;
const note = [$(".terminal-hidden-note").hidden, $(".terminal-hidden-note").textContent];
out("stdout", "x\\n");
const stillThree = $(".terminal-hidden-note").textContent;
out("stdout", "y\\n");
console.log(JSON.stringify({{ first, note, stillThree, again: $(".terminal-hidden-note").textContent,
  lines: T.countLines("a\\nb\\n") + T.countLines("c") + T.countLines("") + T.countLines("\\n\\n") }}));
""",
    )
    data = json.loads(result)
    assert data["first"] == "ligne 0\n"
    assert data["note"] == [False, "3 lignes plus anciennes sont masquées."]
    assert data["stillThree"] == "3 lignes plus anciennes sont masquées."
    assert data["again"] == "4 lignes plus anciennes sont masquées."
    assert data["lines"] == 2 + 1 + 1 + 2


def test_le_volet_du_registre_monte_le_terminal_et_echap_rend_le_focus_au_titre(
    tmp_path: Path,
) -> None:
    script = f"""
import {{ installDom, press, memoryStorage }} from "{MINIDOM}";
const {{ document, main }} = installDom({{ width: 1920, height: 1080 }});
await import("@JS@/views.js");
const {{ mountWorkspace }} = await import("@JS@/workspace.js");
const {{ createStore }} = await import("@JS@/store.js");
const store = createStore();
store.reset("llm.bac-a-sable-libre.A");
store.applySnapshot({{ workspace_id: "llm.bac-a-sable-libre.A", boot_id: "b", seq: 0, epoch: 0, state: "idle", views: {{}} }});
mountWorkspace(main, {{ title: "Bac à sable libre", store, storage: memoryStorage() }});
const pane = main.querySelector('[data-pane="terminal"]');
const input = pane.querySelector("input");
input.focus();
const event = press("Escape");
console.log(JSON.stringify({{
  terminalFlag: pane.dataset.terminal, hasLog: !!pane.querySelector('[role="log"]'),
  focusOnTitle: document.activeElement.className.includes("pane-title"), prevented: event.defaultPrevented,
  tabStops: pane.querySelectorAll("input").length,
}}));
"""
    out = json.loads(_run(tmp_path, script))
    assert out["terminalFlag"] == "true"
    assert out["hasLog"] is True
    assert out["focusOnTitle"] is True and out["prevented"] is True
    assert out["tabStops"] == 1


def test_le_front_ne_lit_pas_la_sortie_et_les_textes_viennent_du_serveur() -> None:
    js = (
        Path(__file__).resolve().parent.parent
        / "src/wavedevsecops/web/static/js/terminal.js"
    ).read_text(encoding="utf-8")
    # AD-2 : aucune analyse de la sortie (pas d'expression régulière sur `entry.text`).
    assert "entry.text.match" not in js and "entry.text.replace" not in js
    assert ".test(entry.text" not in js


def test_bloc_tool_output_etiquete_liens_et_designation(tmp_path: Path) -> None:
    """Story 7.2 (UX-DR20) : sortie d'outil verbatim, liens du serveur, bloc désignable."""
    out = _js(
        tmp_path,
        """
const { selectionFor } = await import("@JS@/selection.js");
const selection = selectionFor(store);
const text = "𝄞 src/a.py:3:8: F401 import inutile\\nFound 1 error.\\n";
const start = text.indexOf("src/a.py:3");
const link = { start, end: start + "src/a.py:3".length, text: "src/a.py:3", element_id: "path:worktree:src/a.py" };
store.applyEvent({ boot_id: "b", seq: ++seq, epoch: 0, op_id: "op1", kind: "terminal_output",
  payload: { stream: "stdout", text, lang: "", tool: "ruff", spans: [link, { start: 900, end: 905, text: "x", element_id: "path:worktree:hors" }] } });
out("stdout", "suite\\n");
const block = $(".tool-output");
const links = [...block.querySelectorAll(".terminal-link")];
const before = selection.value;
links[0].click();
const afterLink = selection.value;
block.click();
const afterBlock = selection.value;
block.click();
console.log(JSON.stringify({
  count: $$(".tool-output").length,
  plain: $$(".terminal-chunk").length,
  role: block.getAttribute("role"),
  label: block.getAttribute("aria-label"),
  tabindex: block.getAttribute("tabindex"),
  elementId: block.getAttribute("data-element-id"),
  tag: block.querySelector(".tool-output-label").textContent,
  verbatim: block.querySelector(".tool-output-text").textContent,
  links: links.map((l) => [l.textContent, l.getAttribute("data-element-id")]),
  split: T.splitSpans("abcdef", [{ start: 4, end: 9 }, { start: 1, end: 3, element_id: "x" }]),
  before, afterLink, afterBlock, afterSecondBlock: selection.value,
}));
""",
    )
    assert out["count"] == 1 and out["plain"] == 1  # le bloc d'outil n'est pas un morceau ordinaire
    assert (out["role"], out["label"], out["tabindex"]) == ("group", "Sortie de ruff", "0")
    assert out["elementId"] == "output:op1" and out["tag"] == "ruff"
    assert out["verbatim"] == "𝄞 src/a.py:3:8: F401 import inutile\nFound 1 error.\n"
    assert out["links"] == [["src/a.py:3", "path:worktree:src/a.py"]]  # le passage hors bornes saute
    assert out["split"] == [
        {"text": "a"},
        {"text": "bc", "elementId": "x"},
        {"text": "def"},
    ]
    assert out["before"] is None
    assert out["afterLink"] == "path:worktree:src/a.py"
    assert out["afterBlock"] == "output:op1" and out["afterSecondBlock"] is None
