# ruff: noqa: E501
"""Espace de travail (Story 2.3) exécuté sous Node, sur une doublure de DOM (`tests/js/minidom.mjs`).

`workspace.js` est monté tel quel avec le vrai registre (`views.js`) : on clique, on frappe des
touches et on lit le DOM, le focus et la mémorisation. La doublure n'a pas de mise en page : le
rendu réel (tailles à l'écran, glisser à la souris, lecteur d'écran) se vérifie dans un navigateur.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from test_shell_js import NODE, _run

pytestmark = pytest.mark.skipif(NODE is None, reason="Node absent : comportement JS non exécuté")

MINIDOM = (Path(__file__).resolve().parent / "js" / "minidom.mjs").as_uri()

PRELUDE = f"""
import {{ installDom, press, memoryStorage }} from "{MINIDOM}";
const width = globalThis.__width || 1920;
const {{ document, main }} = installDom({{ width, height: 1080 }});
await import("@JS@/views.js");
const {{ mountWorkspace, PREPARING_TEXT, LAST_VIEW_TEXT }} = await import("@JS@/workspace.js");
const {{ createStore }} = await import("@JS@/store.js");
const storage = memoryStorage();
const store = createStore();
const mount = () => {{
  main.replaceChildren();
  return mountWorkspace(main, {{ title: "Bac à sable libre", store, storage }});
}};
const $ = (s) => document.querySelector(s);
const $$ = (s) => [...document.querySelectorAll(s)];
const grid = () => $(".views-grid");
const shown = () => [...grid().querySelectorAll(".pane")].map((p) => p.dataset.pane);
const chips = () => $$(".pane-chip").map((c) => c.textContent);
const focused = () => {{
  const a = document.activeElement;
  return a.id || a.dataset.pane || a.getAttribute("aria-label") || a.className;
}};
const saved = () => JSON.parse(storage.getItem("wds.layout") || "null");
"""


def _js(tmp_path: Path, body: str, width: int = 1920) -> dict:
    script = f"globalThis.__width = {width};\n{PRELUDE}\n{body}"
    return json.loads(_run(tmp_path, script))


def test_disposition_par_defaut_et_preparation(tmp_path: Path) -> None:
    out = _js(
        tmp_path,
        """
mount();
const panes = $$(".pane").map((p) => ({
  id: p.dataset.pane,
  step: p.querySelector(".pane-step").textContent,
  title: p.querySelector(".pane-title").textContent,
  subtitle: p.querySelector(".pane-subtitle").textContent,
  empty: p.querySelector(".empty-title").textContent,
  scroll: p.dataset.scroll,
  flex: p.style.flex,
}));
const rows = $$(".view-row").map((r) => r.style.flex);
const handles = $$(".pane-resize-handle").map((h) => [h.getAttribute("role"), h.getAttribute("aria-orientation"),
  h.hasAttribute("aria-valuenow"), h.hasAttribute("aria-valuemin"), h.hasAttribute("aria-valuemax")]);
const status = $(".scenario-status").textContent;
console.log(JSON.stringify({ mode: $(".workspace").dataset.mode, panes, rows, handles, status,
  preparing: PREPARING_TEXT, chipsHidden: $(".chips").hidden }));
""",
    )
    assert out["mode"] == "full"
    assert [p["id"] for p in out["panes"]] == ["repo", "remote", "code", "terminal"]
    assert [p["step"] for p in out["panes"]] == ["1", "2", "3", "4"]
    assert out["panes"][0]["subtitle"] == "Graphe des commits et index, comme git log --all et git status"
    assert out["panes"][1]["empty"] == "Aucune PR."
    # Seuls le graphe, le diff et le terminal défilent dans les deux sens.
    assert [p["scroll"] for p in out["panes"]] == ["both", "y", "both", "both"]
    assert [p["flex"] for p in out["panes"][:2]] == ["55 1 0", "45 1 0"]
    assert out["rows"] == ["40 1 0", "33 1 0", "27 1 0"]
    # Ordre du document : la poignée de la rangée haute, puis les deux entre rangées.
    assert out["handles"] == [
        ["separator", "vertical", True, True, True],
        ["separator", "horizontal", True, True, True],
        ["separator", "horizontal", True, True, True],
    ]
    assert out["status"] == out["preparing"] == "Préparation du bac à sable…"
    assert out["chipsHidden"] is True


def test_masquer_reafficher_focus_et_memorisation(tmp_path: Path) -> None:
    out = _js(
        tmp_path,
        """
const r = {};
mount();
$('[data-pane="remote"] [data-action="hide"]').click();
r.afterHide = { shown: shown(), chips: chips(), focus: focused(), saved: saved().hidden };
// Rechargement (et changement de scénario) : la disposition mémorisée revient.
mount();
r.reload = { shown: shown(), chips: chips() };
$(".pane-chip").click();
r.afterShow = { shown: shown(), chips: chips(), focus: focused(), saved: saved().hidden };
// On masque jusqu'à la dernière vue : « — » devient inactif, avec sa raison.
for (const id of ["repo", "remote", "code"]) $(`[data-pane="${id}"] [data-action="hide"]`).click();
const lastHide = $('[data-pane="terminal"] [data-action="hide"]');
lastHide.click();
r.last = { shown: shown(), disabled: lastHide.getAttribute("aria-disabled"),
  reason: document.getElementById(lastHide.getAttribute("aria-describedby")).textContent,
  expected: LAST_VIEW_TEXT };
console.log(JSON.stringify(r));
""",
    )
    assert out["afterHide"] == {
        "shown": ["repo", "code", "terminal"],
        "chips": ["+ Distant + PR"],
        "focus": "remote",  # la puce « + Distant + PR » a le focus
        "saved": ["remote"],
    }
    assert out["reload"] == {"shown": ["repo", "code", "terminal"], "chips": ["+ Distant + PR"]}
    assert out["afterShow"] == {
        "shown": ["repo", "remote", "code", "terminal"],
        "chips": [],
        "focus": "pane-remote-title",  # titre de la vue réaffichée
        "saved": [],
    }
    assert out["last"]["shown"] == ["terminal"]
    assert out["last"]["disabled"] == "true"
    assert out["last"]["reason"] == out["last"]["expected"]


def test_agrandir_puis_echap_et_ordre_d_echap(tmp_path: Path) -> None:
    out = _js(
        tmp_path,
        """
const r = {};
mount();
const max = $('[data-pane="code"] [data-action="maximize"]');
max.click();
r.max = { mode: $(".workspace").dataset.mode, shown: shown(), pressed: max.getAttribute("aria-pressed") };
// Le menu Volets ouvert se ferme d'abord ; la vue agrandie revient ensuite.
$("#pane-menu-trigger").click();
r.menuOpen = !$("#pane-menu-popup").hidden;
press("Escape");
r.afterFirst = { menuOpen: !$("#pane-menu-popup").hidden, shown: shown(), focus: focused() };
press("Escape");
r.afterSecond = { mode: $(".workspace").dataset.mode, shown: shown(), focus: focused(),
  pressed: max.getAttribute("aria-pressed") };
// Dans le terminal, Échap rend seulement le focus au titre de la vue.
$('[data-pane="terminal"] [data-action="hide"]').focus();
$('[data-pane="code"] [data-action="maximize"]').click();
$('[data-pane="code"] [data-action="maximize"]').click();
$('[data-pane="terminal"] [data-action="hide"]').focus();
press("Escape");
r.terminal = { focus: focused(), shown: shown().length };
// Le volet agrandi ne se mémorise pas.
max.click();
r.savedMax = "maximized" in saved();
console.log(JSON.stringify(r));
""",
    )
    assert out["max"] == {"mode": "single", "shown": ["code"], "pressed": "true"}
    assert out["menuOpen"] is True
    assert out["afterFirst"] == {"menuOpen": False, "shown": ["code"], "focus": "pane-menu-trigger"}
    assert out["afterSecond"]["mode"] == "full" and len(out["afterSecond"]["shown"]) == 4
    assert out["afterSecond"]["focus"] == "Agrandir Code" and out["afterSecond"]["pressed"] == "false"
    assert out["terminal"] == {"focus": "pane-terminal-title", "shown": 4}
    assert out["savedMax"] is False


def test_un_arret_de_tab_par_vue_fleches_et_f6(tmp_path: Path) -> None:
    out = _js(
        tmp_path,
        """
const r = {};
mount();
const stops = (p) => [...p.querySelectorAll("[tabindex]")].filter((n) => n.getAttribute("tabindex") === "0"
  || (n.tagName === "BUTTON" && n.getAttribute("tabindex") !== "-1"));
r.stopsPerPane = $$(".pane").map((p) => stops(p).length);
const hide = $('[data-pane="repo"] [data-action="hide"]');
hide.focus();
press("ArrowRight");
r.afterArrow = { focus: focused(), hide: hide.getAttribute("tabindex"),
  max: $('[data-pane="repo"] [data-action="maximize"]').getAttribute("tabindex") };
press("Home");
r.afterHome = focused();
// F6 : en-tête, panneau Scénario, puis chaque vue ; Maj+F6 revient en arrière.
const zones = [];
for (let i = 0; i < 6; i++) {
  press("F6");
  zones.push(document.activeElement.closest("[data-zone]").dataset.zone
    + ":" + (document.activeElement.closest("[data-pane]")?.dataset.pane || ""));
}
press("F6", { shiftKey: true });
r.back = document.activeElement.closest("[data-zone]").dataset.zone;
r.zones = zones;
console.log(JSON.stringify(r));
""",
    )
    assert out["stopsPerPane"] == [1, 1, 1, 1]
    assert out["afterArrow"] == {"focus": "Agrandir Dépôt local", "hide": "-1", "max": "0"}
    assert out["afterHome"] == "Masquer Dépôt local"
    # Départ dans la vue Dépôt local : vue suivante, puis la boucle complète.
    assert out["zones"] == [
        "pane:remote",
        "pane:code",
        "pane:terminal",
        "header:",
        "scenario:",
        "pane:repo",
    ]
    assert out["back"] == "scenario"


def test_poignee_clavier_minimum_et_double_clic(tmp_path: Path) -> None:
    out = _js(
        tmp_path,
        """
const r = {};
mount();
// Pas de mise en page dans la doublure : on pose 300 px à chaque volet de la rangée haute.
for (const id of ["repo", "remote"]) $(`.pane[data-pane="${id}"]`).style.flex = "300 1 0";
const handle = $('.pane-resize-handle[data-kind="pane"]');
handle.focus();
press("ArrowRight");
r.one = [$('.pane[data-pane="repo"]').style.flex, $('.pane[data-pane="remote"]').style.flex, handle.getAttribute("aria-valuenow")];
for (let i = 0; i < 20; i++) press("ArrowLeft");
r.min = [$('.pane[data-pane="repo"]').style.flex, $('.pane[data-pane="remote"]').style.flex,
  handle.getAttribute("aria-valuenow"), handle.getAttribute("aria-valuemin"), handle.getAttribute("aria-valuemax")];
r.savedWidths = Object.keys(saved().widths).sort();
handle.dispatchEvent({ type: "dblclick", bubbles: true, preventDefault() {}, stopPropagation() {} });
r.reset = { widths: saved().widths, flex: $('.pane[data-pane="repo"]').style.flex,
  focus: document.activeElement.getAttribute("role") };
console.log(JSON.stringify(r));
""",
    )
    assert out["one"] == ["316 1 0", "284 1 0", "316"]
    # 240 px au moins, quel que soit le nombre de pressions.
    assert out["min"] == ["240 1 0", "360 1 0", "240", "240", "360"]
    assert out["savedWidths"] == ["remote", "repo"]
    assert out["reset"] == {"widths": {}, "flex": "55 1 0", "focus": "separator"}


def test_sous_1280_px_une_seule_vue(tmp_path: Path) -> None:
    out = _js(
        tmp_path,
        """
mount();
const r = { mode: $(".workspace").dataset.mode, shown: shown(), chips: chips(),
  handles: $$(".pane-resize-handle").length };
$(".pane-chip").click();  // « + Distant + PR » : la vue montrée change
r.after = { shown: shown(), focus: focused(), saved: saved().hidden };
console.log(JSON.stringify(r));
""",
        width=1000,
    )
    assert out["mode"] == "single"
    assert out["shown"] == ["repo"]
    assert out["chips"] == ["+ Distant + PR", "+ Code", "+ Terminal"]
    assert out["handles"] == 0
    # Un repli automatique ne se mémorise pas comme un masquage voulu.
    assert out["after"] == {"shown": ["remote"], "focus": "pane-remote-title", "saved": []}


def test_parametre_vue_ouvre_l_espace_sur_distant_meme_masquee(tmp_path: Path) -> None:
    """Lien « traçabilité » (story 9.6) : `?vue=remote` montre Distant + PR, titre au focus."""
    out = _js(
        tmp_path,
        """
const r = {};
main.replaceChildren();
mountWorkspace(main, { title: "Échec", store, storage, initialPane: "remote" });
r.narrow = { shown: shown(), focus: focused() };
$('[data-pane="remote"] [data-action="hide"]').click();
main.replaceChildren();
mountWorkspace(main, { title: "Échec", store, storage, initialPane: "remote" });
r.hidden = { shown: shown().includes("remote"), focus: focused() };
main.replaceChildren();
mountWorkspace(main, { title: "Échec", store, storage, initialPane: "inconnue" });
r.unknown = shown();
console.log(JSON.stringify(r));
""",
        width=1000,
    )
    # Sous 1280 px, une seule vue : celle du paramètre, et non la première.
    assert out["narrow"] == {"shown": ["remote"], "focus": "pane-remote-title"}
    assert out["hidden"] == {"shown": True, "focus": "pane-remote-title"}
    assert out["unknown"] == ["repo"]  # une vue inconnue est ignorée
