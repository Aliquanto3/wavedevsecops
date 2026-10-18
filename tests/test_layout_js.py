# ruff: noqa: E501
"""Disposition des volets (Story 2.3) : logique pure du front, exécutée sous Node.

Masquage avec au moins une vue visible, taille minimale 240 x 160, redimensionnement au clavier
par pas de 16 px, repli selon la fenêtre, mémorisation protégée par try/catch, registre des vues
et magasin de projection. Le DOM (poignées, focus, menu) se vérifie dans un vrai navigateur.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from test_shell_js import NODE, _run

pytestmark = pytest.mark.skipif(NODE is None, reason="Node absent : comportement JS non exécuté")

PANES = """
const panes = [
  { id: "repo", step: 1, title: "Dépôt local", row: 1, rowShare: 40, share: 55 },
  { id: "remote", step: 2, title: "Distant + PR", row: 1, share: 45, foldRank: 1 },
  { id: "code", step: 3, title: "Code", row: 2, rowShare: 33, foldRank: 2 },
  { id: "terminal", step: 4, title: "Terminal", row: 3, rowShare: 27 },
];
"""


def _json(tmp_path: Path, body: str):
    script = f"""
import * as L from "@JS@/layout.js";
{PANES}
{body}
"""
    return json.loads(_run(tmp_path, script))


def test_rangees_et_proportions_par_defaut(tmp_path: Path) -> None:
    out = _json(
        tmp_path,
        """
const config = L.defaultConfig();
const rows = L.rowsOf(panes);
// Hauteurs 40 / 33 / 27 % de 950 px (gouttières déduites), largeurs 55 / 45 %.
const heights = L.sizesFromWeights(rows.map((r) => L.rowWeight(config, r)), 950, L.MIN_HEIGHT);
const widths = L.sizesFromWeights(rows[0].panes.map((p) => L.paneWeight(config, p)), 1472, L.MIN_WIDTH);
// La rangée haute garde sa part même si son premier volet est masqué.
const noRepo = L.rowsOf(panes, new Set(["remote", "code", "terminal"]));
console.log(JSON.stringify({ rows: rows.map((r) => r.panes.map((p) => p.id)), heights, widths,
  shareWithoutRepo: noRepo[0].share }));
""",
    )
    assert out["rows"] == [["repo", "remote"], ["code"], ["terminal"]]
    room = 950 - 16
    assert [round(h / room, 2) for h in out["heights"]] == [0.4, 0.33, 0.27]
    assert [round(w / (1472 - 8), 2) for w in out["widths"]] == [0.55, 0.45]
    assert out["shareWithoutRepo"] == 40


def test_au_moins_une_vue_visible(tmp_path: Path) -> None:
    out = _json(
        tmp_path,
        """
let config = L.defaultConfig();
const steps = [];
for (const id of ["repo", "remote", "code", "terminal"]) {
  const next = L.hidePane(config, panes, id);
  steps.push(next === null ? "refusé" : "masqué");
  if (next) config = next;
}
const shown = [...L.visibleIds(config, panes)];
const back = L.showPane(config, "code");
// Une configuration mémorisée qui masquerait tout est rejetée.
const all = L.sanitize({ hidden: ["repo", "remote", "code", "terminal"] }, panes);
const unknown = L.sanitize({ hidden: ["nope", "code"], widths: { nope: 3, repo: -1, remote: 9 } }, panes);
console.log(JSON.stringify({ steps, shown, back: back.hidden, all: all.hidden, unknown }));
""",
    )
    assert out["steps"] == ["masqué", "masqué", "masqué", "refusé"]
    assert out["shown"] == ["terminal"]
    assert out["back"] == ["repo", "remote"]
    assert out["all"] == []
    assert out["unknown"]["hidden"] == ["code"]
    assert out["unknown"]["widths"] == {"remote": 9}


def test_taille_minimale_et_pas_de_16_px(tmp_path: Path) -> None:
    out = _json(
        tmp_path,
        """
const base = [600, 400];
const right = L.resizeSizes(base, 0, L.keyDelta("ArrowRight", "vertical"), L.MIN_WIDTH);
const left = L.resizeSizes(base, 0, L.keyDelta("ArrowLeft", "vertical"), L.MIN_WIDTH);
const down = L.resizeSizes([300, 200], 0, L.keyDelta("ArrowDown", "horizontal"), L.MIN_HEIGHT);
const toMin = L.resizeSizes(base, 0, -10000, L.MIN_WIDTH);
const toMax = L.resizeSizes(base, 0, 10000, L.MIN_WIDTH);
console.log(JSON.stringify({
  step: L.STEP, right, left, down, toMin, toMax,
  ignored: [L.keyDelta("ArrowUp", "vertical"), L.keyDelta("a", "horizontal")],
  aria: L.separatorValues(base, 0, L.MIN_WIDTH),
  clamped: L.clampSizes([100, 900], 240),
  weights: L.weightsFromSizes([300, 100], [50, 30]),
}));
""",
    )
    assert out["step"] == 16
    assert out["right"] == [616, 384] and out["left"] == [584, 416]
    assert out["down"] == [316, 184]
    assert out["toMin"] == [240, 760] and out["toMax"] == [760, 240]
    assert out["ignored"] == [None, None]
    assert out["aria"] == {"now": 600, "min": 240, "max": 760}
    assert out["clamped"] == [240, 760]
    # Les parts des volets masqués ne sont pas faussées : la somme visible est conservée.
    assert sum(out["weights"]) == pytest.approx(80)


def test_modification_de_poignee_puis_reinitialisation(tmp_path: Path) -> None:
    out = _json(
        tmp_path,
        """
let config = L.defaultConfig();
config = L.setPaneWidths(config, ["repo", "remote"], [60, 40]);
config = L.setRowWeights(config, [1, 2], [50, 20]);
const changed = JSON.stringify([config.widths, config.rows]);
config = L.resetWeights(config, { paneIds: ["repo", "remote"] });
console.log(JSON.stringify({ changed, widths: config.widths, rows: config.rows }));
""",
    )
    assert out["widths"] == {} and out["rows"] == {"1": 50, "2": 20}


def test_repli_selon_la_fenetre(tmp_path: Path) -> None:
    out = _json(
        tmp_path,
        """
const config = L.defaultConfig();
const at = (width, height, viewport, pinned = new Set(), focus = null, cfg = config) => {
  const e = L.effectiveLayout(panes, cfg, { width, height, viewport }, pinned, focus);
  return { mode: e.mode, shown: e.shown, hidden: [...e.hidden] };
};
console.log(JSON.stringify({
  full: at(1472, 950, 1920),
  // Trop bas pour trois rangées à 160 px : Distant + PR ne gagne rien, Code se replie d'abord
  // après lui (foldRank 1 puis 2) jusqu'à ce que cela tienne.
  short: at(1472, 520, 1920),
  narrow: at(400, 950, 1920),
  compact: at(840, 950, 1100),
  compactFocus: at(840, 950, 1100, new Set(), "code"),
  pinned: at(1472, 520, 1920, new Set(["code"])),
  maximized: at(1472, 950, 1920, new Set(), null, { ...config, maximized: "code" }),
  userHidden: at(1472, 950, 1920, new Set(), null, { ...config, hidden: ["repo"] }),
}));
""",
    )
    assert out["full"]["mode"] == "full" and out["full"]["hidden"] == []
    # 3 rangées demandent 3 x 160 + 16 = 496 px : tient à 520 px, mais pas à 450.
    assert out["short"]["mode"] == "full"
    assert out["narrow"]["mode"] == "fold" and out["narrow"]["hidden"] == ["remote"]
    assert out["compact"] == {
        "mode": "single",
        "shown": ["repo"],
        "hidden": ["remote", "code", "terminal"],
    }
    assert out["compactFocus"]["shown"] == ["code"]
    assert out["maximized"]["shown"] == ["code"] and out["maximized"]["mode"] == "single"
    assert out["userHidden"]["shown"] == ["remote", "code", "terminal"]


def test_repli_dans_l_ordre_des_puces(tmp_path: Path) -> None:
    out = _json(
        tmp_path,
        """
const config = L.defaultConfig();
const run = (height, pinned = new Set()) => {
  const e = L.effectiveLayout(panes, config, { width: 1472, height, viewport: 1920 }, pinned);
  return { mode: e.mode, shown: e.shown };
};
console.log(JSON.stringify({
  a: run(450),            // 3 rangées ne tiennent plus : Distant + PR ne libère pas de hauteur
  b: run(300),
  c: run(100),
  pin: run(300, new Set(["remote"])),
}));
""",
    )
    # Tant que la hauteur manque, on replie par foldRank : Distant + PR (1), puis Code (2).
    assert out["a"]["shown"] == ["repo", "terminal"]
    assert out["b"] == {"mode": "single", "shown": ["repo"]}
    # Plus rien à replier et rien ne tient : une seule vue.
    assert out["c"]["mode"] == "single"
    assert out["pin"]["shown"][0] == "repo"


def test_focus_itinerant_et_f6(tmp_path: Path) -> None:
    out = _json(
        tmp_path,
        """
console.log(JSON.stringify({
  right: L.rovingIndex("ArrowRight", 0, 3),
  end: L.rovingIndex("ArrowRight", 2, 3),
  left: L.rovingIndex("ArrowLeft", 0, 3),
  home: L.rovingIndex("Home", 2, 3),
  last: L.rovingIndex("End", 0, 3),
  other: L.rovingIndex("a", 1, 3),
  empty: L.rovingIndex("ArrowDown", 0, 0),
  f6: [L.nextZone(4, 0, false), L.nextZone(4, 3, false), L.nextZone(4, 0, true), L.nextZone(4, -1, false), L.nextZone(0, 0, false)],
}));
""",
    )
    assert out["right"] == 1 and out["end"] == 2 and out["left"] == 0
    assert out["home"] == 0 and out["last"] == 2 and out["other"] == 1 and out["empty"] == -1
    assert out["f6"] == [1, 0, 3, 0, -1]


def test_memorisation_protegee_par_try_catch(tmp_path: Path) -> None:
    out = _json(
        tmp_path,
        """
const store = new Map();
const good = { getItem: (k) => store.get(k) ?? null, setItem: (k, v) => store.set(k, v) };
const broken = { getItem() { throw new Error("bloqué"); }, setItem() { throw new Error("plein"); } };
let config = L.hidePane(L.defaultConfig(), panes, "remote");
config = L.toggleMaximized(config, "code");
config = L.setPaneWidths(config, ["repo"], [70]);
const saved = L.saveConfig(config, good);
const reloaded = L.loadConfig(panes, good);
store.set(L.STORAGE_KEY, "{pas du json");
const garbage = L.loadConfig(panes, good);
console.log(JSON.stringify({
  saved, reloaded, garbage,
  brokenSave: L.saveConfig(config, broken),
  brokenLoad: L.loadConfig(panes, broken),
  noStorage: L.loadConfig(panes, null),
}));
""",
    )
    assert out["saved"] is True and out["brokenSave"] is False
    assert out["reloaded"]["hidden"] == ["remote"] and out["reloaded"]["widths"] == {"repo": 70}
    assert out["reloaded"]["maximized"] is None  # le volet agrandi ne se mémorise pas
    for key in ("garbage", "brokenLoad", "noStorage"):
        assert out[key] == {"hidden": [], "rows": {}, "widths": {}, "maximized": None}


def test_registre_refuse_un_type_emis_non_declare(tmp_path: Path) -> None:
    out = _run(
        tmp_path,
        """
import { registerPane, listPanes, assertElementType, getPane } from "@JS@/panes.js";
import { createStore, acceptViews } from "@JS@/store.js";
registerPane({ id: "repo", title: "Dépôt", elementTypes: ["commit", "ref"], render() {} });
registerPane({ id: "later", title: "Plus tard", step: 9, elementTypes: [], render() {} });
const errors = [];
const attempt = (fn) => { try { fn(); errors.push("ok"); } catch (e) { errors.push(e.message); } };
attempt(() => assertElementType("repo", "commit"));
attempt(() => assertElementType("repo", "pr"));
attempt(() => assertElementType("absent", "commit"));
attempt(() => registerPane({ id: "repo", title: "x", render() {} }));
attempt(() => registerPane({ id: "bad", title: "x", elementTypes: [3], render() {} }));
attempt(() => registerPane({ title: "sans id", render() {} }));
// Le magasin écarte la projection d'un volet qui émet un type non déclaré, garde les autres.
const problems = [];
const kept = acceptViews({
  repo: { elements: [{ type: "commit" }] },
  later: { elements: [{ type: "ref" }] },
}, problems);
console.log(JSON.stringify({ errors, kept: Object.keys(kept), problems, steps: listPanes().map((p) => p.step),
  def: getPane("repo").row }));
""",
    )
    data = json.loads(out)
    assert data["errors"][0] == "ok"
    assert "sans l'avoir déclaré" in data["errors"][1]
    assert "inconnu" in data["errors"][2] and "déjà enregistré" in data["errors"][3]
    assert "elementTypes" in data["errors"][4] and "id" in data["errors"][5]
    assert data["kept"] == ["repo"] and len(data["problems"]) == 1
    assert data["steps"] == [1, 9] and data["def"] == 1


def test_magasin_de_projection_ordre_reprise_et_resynchronisation(tmp_path: Path) -> None:
    out = _run(
        tmp_path,
        """
import { registerPane } from "@JS@/panes.js";
import { createStore, connectWorkspace, LOADING } from "@JS@/store.js";
registerPane({ id: "repo", title: "Dépôt", elementTypes: ["commit"], render() {} });
const store = createStore();
const first = store.state.engineState;
store.applySnapshot({ workspace_id: "no_ai.x.A", boot_id: "b1", seq: 4, epoch: 1, state: "setup",
  reason_text: "Préparation", fingerprint: "", views: {} });
const envelope = (seq, kind, payload, boot = "b1") => ({ boot_id: boot, seq, kind, epoch: 1, payload });
const results = [
  store.applyEvent(envelope(4, "engine_state", { state: "idle" })),          // déjà vu
  store.applyEvent(envelope(5, "engine_state", { state: "idle", reason_text: "" })),
  store.applyEvent(envelope(6, "state_projected", { views: { repo: { elements: [{ type: "commit" }] } }, fingerprint: "f" })),
  store.applyEvent(envelope(7, "state_projected", { views: { repo: { elements: [{ type: "nope" }] } }, fingerprint: "g" })),
  store.applyEvent(envelope(8, "app_error", { cause_text: "Cause.", action_text: "Action." })),
  store.applyEvent(envelope(9, "engine_state", { state: "idle" }, "autre")),  // autre lancement
  store.applyEvent({ boot_id: "b1", seq: 9, kind: "resync_required", payload: {} }),
];
const s = store.state;

// connectWorkspace : état puis flux repris à <boot_id>:<seq>, resynchronisation sur resync_required.
const urls = [];
const snaps = [
  { workspace_id: "w", boot_id: "b1", seq: 3, epoch: 0, state: "idle", views: {} },
  { workspace_id: "w", boot_id: "b2", seq: 1, epoch: 0, state: "idle", views: {} },
];
const sources = [];
class Fake { constructor(url) { this.url = url; sources.push(this); } close() { this.closed = true; } }
const fetchImpl = async (url) => { urls.push(url); return { ok: true, json: async () => snaps.shift() }; };
const live = createStore();
connectWorkspace(live, "w", { fetchImpl, EventSourceImpl: Fake });
await new Promise((r) => setTimeout(r, 20));
sources[0].onmessage({ data: JSON.stringify({ boot_id: "b1", seq: 4, kind: "engine_state", payload: { state: "command" } }) });
sources[0].onmessage({ data: "pas du json" });
const during = live.state.engineState;
sources[0].onmessage({ data: JSON.stringify({ boot_id: "b1", seq: 5, kind: "resync_required", payload: {} }) });
await new Promise((r) => setTimeout(r, 20));
console.log(JSON.stringify({ first, LOADING, results, s: { seq: s.seq, state: s.engineState, fp: s.fingerprint,
  views: Object.keys(s.views), problems: s.problems.length, error: s.errorText },
  sources: sources.map((x) => [x.url, Boolean(x.closed)]), urls, during, after: live.state.bootId }));
""",
    )
    data = json.loads(out)
    assert data["first"] == data["LOADING"] == "loading"
    assert data["results"] == [
        "stale",
        "applied",
        "applied",
        "applied",
        "applied",
        "resync",
        "resync",
    ]
    assert data["s"]["seq"] == 8 and data["s"]["state"] == "idle" and data["s"]["fp"] == "g"
    assert data["s"]["error"] == "Cause. Action."
    # La dernière projection (type non déclaré) est écartée : la vue repo n'y figure plus.
    assert data["s"]["views"] == [] and data["s"]["problems"] == 1
    assert data["sources"][0] == ["/api/ws/w/events?last_event_id=b1%3A3", True]
    assert data["sources"][1][0] == "/api/ws/w/events?last_event_id=b2%3A1"
    assert data["during"] == "command" and data["after"] == "b2"
    assert data["urls"] == ["/api/ws/w/state", "/api/ws/w/state"]
