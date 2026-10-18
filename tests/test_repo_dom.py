# ruff: noqa: E501
"""Vue « Dépôt local » (Story 2.7) sous Node, sur la doublure de DOM, avec de vraies projections.

Les `views` viennent de `build_views` sur un vrai dépôt git (états : branches, fusion, tag, ref
distante, index, HEAD détachée, commit perdu), sérialisées en JSON puis posées dans le magasin du
front. La doublure n'a ni mise en page ni lecteur d'écran : le rendu réel se vérifie dans un navigateur.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
from static_rules import STATIC
from test_projections import FREE, Sandbox
from test_shell_js import NODE, _run
from test_shell_ui import CONTRAST_PAIRS, _blocks, _palette, _ratio

from wavedevsecops.config import Settings
from wavedevsecops.engine import prepare_workspace
from wavedevsecops.gitio import Git
from wavedevsecops.projections import build_views
from wavedevsecops.scenarios import load_scenario

pytestmark = pytest.mark.skipif(NODE is None, reason="Node absent : comportement JS non exécuté")

MINIDOM = (Path(__file__).resolve().parent / "js" / "minidom.mjs").as_uri()
CSS = STATIC / "css"


@pytest.fixture(scope="module")
def snapshots(tmp_path_factory: pytest.TempPathFactory, git_path: Path) -> dict[str, dict]:
    settings = Settings(data_dir=tmp_path_factory.mktemp("data"))
    prepared = prepare_workspace(
        load_scenario(FREE, settings), "llm", settings=settings, git_path=git_path
    )
    box = Sandbox(Git.for_workspace(git_path, prepared.layout.root, settings), prepared.layout)
    out: dict[str, dict] = {}

    def dump(name: str, before, after) -> None:
        out[name] = build_views(after, before).model_dump(mode="json")

    start = box.state()
    out["start"] = build_views(start).model_dump(mode="json")
    box.run("switch", "-q", "-c", "feature")
    box.commit("Fonction 1")
    box.run("tag", "-a", "v1.0", "-m", "Première version")
    box.run("switch", "-q", "main")
    box.commit("Correctif sur main")
    before_merge = box.state()
    box.run("merge", "-q", "--no-ff", "feature", "-m", "Fusion de feature")
    box.write("a.txt", "a\n")
    box.run("add", "a.txt")
    box.write("README.md", "# Modifié\n")
    box.write("b.txt", "b\n")
    merged = box.state()
    dump("merged", before_merge, merged)
    box.run("checkout", "-q", "--detach", "HEAD~1")
    detached = box.state()
    dump("detached", merged, detached)
    box.run("switch", "-q", "main")
    box.run("switch", "-q", "-c", "wip")
    box.commit("Brouillon")
    wip = box.state()
    box.run("switch", "-q", "main")
    box.run("branch", "-q", "-D", "wip")
    dump("lost", wip, box.state())
    return out


PRELUDE = f"""
import {{ installDom, makeEvent, press }} from "{MINIDOM}";
import fs from "node:fs";
const snaps = JSON.parse(fs.readFileSync(process.env.SNAPS, "utf8"));
const {{ document, main }} = installDom({{ width: 1920, height: 1080 }});
let fetched = 0;
globalThis.fetch = () => {{ fetched++; return Promise.reject(new Error("réseau")); }};
await import("@JS@/views.js");
const {{ mountWorkspace }} = await import("@JS@/workspace.js");
const {{ createStore }} = await import("@JS@/store.js");
const {{ selectionFor }} = await import("@JS@/selection.js");
const store = createStore();
mountWorkspace(main, {{ title: "Bac à sable libre", store, storage: {{ getItem: () => null, setItem() {{}} }} }});
const $ = (s) => document.querySelector(s);
const $$ = (s) => [...document.querySelectorAll(s)];
let seq = 1;
const load = (name, extra = {{}}) => store.applySnapshot({{ workspace_id: "w", boot_id: "b", seq: seq++, epoch: 0,
  state: "idle", views: {{ ...snaps[name], ...extra }} }});
const repo = () => $('.pane[data-pane="repo"]');
const texts = (sel, root = document) => [...root.querySelectorAll(sel)].map((n) => n.textContent);
"""


def _js(tmp_path: Path, snapshots: dict, body: str) -> dict:
    snaps = tmp_path / "snaps.json"
    snaps.write_text(json.dumps(snapshots), encoding="utf-8")
    import os

    os.environ["SNAPS"] = str(snaps)
    try:
        return json.loads(_run(tmp_path, f"{PRELUDE}\n{body}"))
    finally:
        del os.environ["SNAPS"]


def test_graphe_dessine_noeuds_aretes_refs_et_marques(tmp_path: Path, snapshots: dict) -> None:
    views = snapshots["merged"]
    out = _js(
        tmp_path,
        snapshots,
        """
load("merged");
const nodes = snaps.merged.graph.nodes;
const buttons = $$(".graph-node");
console.log(JSON.stringify({
  circles: $$("circle.graph-commit").length,
  buttons: buttons.length,
  edges: $$("path.graph-edge").length,
  mergeEdges: $$('path.graph-edge[data-kind="merge"]').length,
  labels: buttons.map((b) => b.getAttribute("aria-label")),
  pressed: buttons.map((b) => b.getAttribute("aria-pressed")),
  head: texts(".graph-head"),
  branches: texts(".graph-branch"),
  remotes: texts(".graph-remote-ref"),
  tags: texts(".graph-tag"),
  icons: $$(".graph-branch svg, .graph-remote-ref svg, .graph-tag svg").length,
  marks: texts(".new-mark"),
  svgHidden: $(".graph-lanes").getAttribute("aria-hidden"),
  group: $(".graph").getAttribute("aria-label"),
  headText: $(".graph-head-text").textContent,
  tabstops: $$('.pane[data-pane="repo"] button').filter((b) => b.getAttribute("tabindex") === "0").length,
  rowHeights: buttons.map((b) => b.style.paddingLeft),
}));
""",
    )
    nodes = views["graph"]["nodes"]
    assert out["circles"] == out["buttons"] == len(nodes) >= 5
    assert out["edges"] == len(views["graph"]["edges"])
    assert out["mergeEdges"] == sum(e["kind"] == "merge" for e in views["graph"]["edges"]) >= 1
    # Le nom accessible est celui du serveur, mot pour mot, dans l'ordre du serveur.
    assert out["labels"] == [n["a11y_name_text"] for n in nodes]
    assert set(out["pressed"]) == {"false"}
    assert out["head"] == ["HEAD"]
    assert "main" in out["branches"] and "feature" in out["branches"]
    assert out["remotes"] == ["origin/main"]
    assert out["tags"] == ["v1.0"]
    assert out["icons"] == len(out["branches"]) + len(out["remotes"]) + len(out["tags"])
    assert out["marks"].count("Nouveau") >= 1
    assert out["svgHidden"] == "true" and out["group"] == "Graphe des commits"
    assert out["headText"] == views["graph"]["head_text"]
    assert out["tabstops"] == 1  # un seul arrêt de tabulation dans la vue


def test_head_detachee_et_commit_perdu(tmp_path: Path, snapshots: dict) -> None:
    out = _js(
        tmp_path,
        snapshots,
        """
load("detached");
const detached = { head: texts(".graph-head"), headText: $(".graph-head-text").textContent };
load("lost");
console.log(JSON.stringify({
  detached,
  lostCircles: $$("circle.graph-commit.is-lost").length,
  lostEdges: $$("path.graph-edge.is-lost").length,
  lostLabels: texts(".graph-lost"),
  lostButtons: $$(".graph-node.is-lost").map((b) => b.getAttribute("aria-label")),
}));
""",
    )
    assert out["detached"]["head"] == ["HEAD détachée"]
    assert out["detached"]["headText"].startswith("HEAD détachée sur ")
    lost = [n for n in snapshots["lost"]["graph"]["nodes"] if n["lost"]]
    assert len(lost) == 1 and out["lostCircles"] == 1
    assert out["lostLabels"] == ["perdu · visible par reflog"]
    assert out["lostButtons"] == [lost[0]["a11y_name_text"]]
    assert out["lostEdges"] == sum(e["lost"] for e in snapshots["lost"]["graph"]["edges"]) >= 1


def test_badges_collegue_et_agent_et_marque_retabli(tmp_path: Path, snapshots: dict) -> None:
    out = _js(
        tmp_path,
        snapshots,
        """
const views = structuredClone(snaps.merged);
views.graph.nodes[0].actor = "colleague";
views.graph.nodes[1].actor = "agent";
views.graph.nodes[2].restored = true;
store.applySnapshot({ workspace_id: "w", boot_id: "b", seq: 1, epoch: 0, state: "idle", views });
console.log(JSON.stringify({ actors: texts(".graph-actor"), restored: texts(".new-mark") }));
""",
    )
    assert out["actors"] == ["Collègue", "Agent"]
    assert "Rétabli" in out["restored"]


def test_selection_au_clic_partagee_avec_la_liste(tmp_path: Path, snapshots: dict) -> None:
    out = _js(
        tmp_path,
        snapshots,
        """
load("merged");
const ids = snaps.merged.graph.nodes.map((n) => n.element_id);
const sel = selectionFor(store);
const pressed = () => $$(".graph-node").map((b) => b.getAttribute("aria-pressed"));
$$(".graph-node")[1].click();
const afterClick = { value: sel.value, pressed: pressed(), selectedCircle: $$("circle.is-selected").length };
// Bascule en liste : même sélection, mêmes éléments.
const toggle = $('[data-action="view-toggle"]');
const before = toggle.textContent;
toggle.click();
const rows = $$(".commit-list tbody tr");
const list = {
  before, after: toggle.textContent, label: toggle.getAttribute("aria-label"),
  caption: $(".commit-list caption").textContent,
  headers: texts(".commit-list th"),
  count: rows.length,
  order: rows.map((r) => r.getAttribute("data-element-id")),
  selected: rows.map((r) => r.classList.contains("is-selected")),
  pressed: $$(".commit-pick").map((b) => b.getAttribute("aria-pressed")),
  graphGone: $(".graph") === null,
  cells: texts("td", rows[0]),
};
// Un clic sur une autre ligne déplace la sélection ; un nouveau clic l'efface.
rows[3].click();
const moved = sel.value;
$$(".commit-pick")[3].click();
const cleared = sel.value;
toggle.click();
console.log(JSON.stringify({ ids, afterClick, list, moved, cleared, back: toggle.textContent,
  graph: $(".graph") !== null, fetched }));
""",
    )
    nodes = snapshots["merged"]["graph"]["nodes"]
    ids = out["ids"]
    assert out["afterClick"]["value"] == ids[1]
    assert out["afterClick"]["pressed"] == ["false", "true"] + ["false"] * (len(ids) - 2)
    assert out["afterClick"]["selectedCircle"] == 1
    lst = out["list"]
    assert (lst["before"], lst["after"]) == ("Liste", "Graphe")
    assert lst["label"] == "Afficher le graphe des commits"
    assert lst["caption"] == "Commits, dans l'ordre de git log --all --graph"
    assert lst["headers"] == ["SHA", "Message", "Auteur", "Parents", "Refs", "État"]
    assert lst["order"] == ids and lst["count"] == len(nodes)
    assert lst["selected"] == [False, True] + [False] * (len(ids) - 2)
    assert lst["pressed"][1] == "true" and lst["graphGone"]
    sha, message, author, parents, refs, state = lst["cells"]
    assert sha.replace("●", "") == nodes[0]["short_sha"] and message == nodes[0]["subject"]
    assert author.startswith("Camille Durand")  # auteur repris du RepoState
    assert out["moved"] == ids[3]
    assert out["cleared"] is None
    assert out["back"] == "Liste" and out["graph"]
    assert out["fetched"] == 0  # sélectionner ne contacte pas le serveur


def test_liste_des_commits_auteur_parents_refs_et_etat(tmp_path: Path, snapshots: dict) -> None:
    out = _js(
        tmp_path,
        snapshots,
        """
load("lost");
$('[data-action="view-toggle"]').click();
console.log(JSON.stringify($$(".commit-list tbody tr").map((r) => texts("td", r))));
""",
    )
    nodes = snapshots["lost"]["graph"]["nodes"]
    authors = {c["sha"]: c["author_name"] for c in snapshots["lost"]["repo"]["commits"]}
    for row, node in zip(out, nodes, strict=True):
        sha, message, author, parents, refs, state = row
        assert sha.replace("●", "") == node["short_sha"] and message == node["subject"]
        assert author.startswith(authors[node["sha"]])
        expected = ", ".join(by_short_id(nodes, p) for p in node["parents"]) or "—"
        assert parents == expected
        assert ("perdu" in state) == node["lost"]
        assert all(label["name_text"] in refs for label in node["refs"])
    assert any("HEAD" in row[5] for row in out)


def by_short_id(nodes: list[dict], element_id: str) -> str:
    return next(n["short_sha"] for n in nodes if n["element_id"] == element_id)


def test_index_en_trois_groupes_sans_rien_indexer(tmp_path: Path, snapshots: dict) -> None:
    out = _js(
        tmp_path,
        snapshots,
        """
load("merged");
const groups = $$(".staging-group").map((g) => ({
  cls: g.className, title: g.querySelector(".staging-group-title").textContent,
  items: [...g.querySelectorAll(".staging-item")].map((b) => ({
    letter: b.querySelector(".status-letter").textContent,
    path: b.querySelector(".staging-path").textContent,
    label: b.getAttribute("aria-label"), id: b.getAttribute("data-element-id") })),
}));
const first = $(".staging-item");
first.click();
const sel = selectionFor(store);
console.log(JSON.stringify({ groups, value: sel.value, id: first.getAttribute("data-element-id"),
  pressed: first.getAttribute("aria-pressed"), fetched,
  stagingBefore: JSON.stringify(store.state.views.staging) }));
""",
    )
    assert [g["title"] for g in out["groups"]] == [
        "Indexé (1)",
        "Modifié, non indexé (1)",
        "Non suivi (1)",
    ]
    assert [g["items"][0]["letter"] for g in out["groups"]] == ["A", "M", "?"]
    assert [g["items"][0]["path"] for g in out["groups"]] == ["a.txt", "README.md", "b.txt"]
    assert out["groups"][0]["items"][0]["label"] == "Indexé : a.txt, ajouté"
    assert "is-staged" in out["groups"][0]["cls"] and "is-untracked" in out["groups"][2]["cls"]
    assert out["value"] == out["id"] == "path:index:a.txt" and out["pressed"] == "true"
    # Un clic sélectionne : aucun appel au serveur, aucun changement de la projection.
    assert out["fetched"] == 0
    assert json.loads(out["stagingBefore"]) == snapshots["merged"]["staging"]


def test_etat_vide_vues_refusees_et_annonce(tmp_path: Path, snapshots: dict) -> None:
    out = _js(
        tmp_path,
        snapshots,
        """
const empty = () => repo().querySelector(".empty-title")?.textContent ?? null;
const start = empty();
store.applySnapshot({ workspace_id: "w", boot_id: "b", seq: 1, epoch: 0, state: "idle",
  views: { graph: { nodes: [], edges: [], columns: 0, rows: 0, head_text: "" },
           staging: { staged: [], unstaged: [], untracked: [{ element_id: "path:worktree:n.txt", path: "n.txt", letter: "?" }] } } });
const emptyGraph = { title: empty(), items: $$(".staging-item").length, clean: $(".staging-clean") };
load("merged");
const shown = empty();
// Une vue dont un element_id a un type non déclaré par le volet est refusée.
const bad = structuredClone(snaps.merged);
bad.graph.nodes[0].element_id = "pr:1";
store.applySnapshot({ workspace_id: "w", boot_id: "b", seq: 9, epoch: 0, state: "idle", views: bad });
const refused = { title: empty(), problems: store.state.problems.length, keys: Object.keys(store.state.views) };
// Annonce : commande terminée, puis changement venu de l'extérieur, puis ouverture.
const status = () => $(".scenario-status").textContent;
load("merged");
const opened = status();
const evt = (n, kind, op, payload) => ({ boot_id: "b", seq: 100 + n, kind, epoch: 0, op_id: op, payload });
store.applyEvent(evt(1, "state_projected", "op1", { views: snaps.lost, fingerprint: "x" }));
const command = status();
store.applyEvent(evt(2, "external_change", "op2", { fingerprint: "y" }));
store.applyEvent(evt(3, "state_projected", "op2", { views: snaps.detached, fingerprint: "z" }));
const external = status();
console.log(JSON.stringify({ start, emptyGraph: { ...emptyGraph, clean: emptyGraph.clean !== null }, shown, refused,
  opened, command, external, lost: snaps.lost.announce_text, detached: snaps.detached.announce_text }));
""",
    )
    assert out["start"] == "Aucun commit pour l'instant."
    assert out["emptyGraph"] == {"title": "Aucun commit pour l'instant.", "items": 1, "clean": False}
    assert out["shown"] is None
    assert out["refused"]["title"] == "Aucun commit pour l'instant."
    assert out["refused"]["problems"] == 1 and "graph" not in out["refused"]["keys"]
    assert out["opened"] == "Le bac à sable est prêt. Les consignes du scénario s'afficheront ici."
    assert out["command"] == f"Commande terminée. {out['lost']}"
    assert out["lost"].startswith("Vues mises à jour")
    assert out["external"] == out["detached"]


def test_annonce_de_commande_puis_statut_d_etape(tmp_path: Path, snapshots: dict) -> None:
    """Une seule région role="status" : l'annonce de la commande, puis le statut d'étape (4.1)."""
    out = _js(
        tmp_path,
        snapshots,
        """
const status = () => $(".scenario-status").textContent;
const panel = { title_text: "Essai", mode: "A", mode_text: "Mode A.", current_step_id: "s1",
  steps: [
    { step_id: "s1", title_text: "Créer la branche", instruction_text: "", state: "current", explanation_text: "", explain_ref: "" },
    { step_id: "s2", title_text: "Faire un commit", instruction_text: "", state: "todo", explanation_text: "", explain_ref: "" },
  ] };
store.applySnapshot({ workspace_id: "w", boot_id: "b", seq: 50, epoch: 0, state: "idle",
  views: snaps.merged, step_panel: panel });
const opened = status();
const evt = (n, kind, op, payload) => ({ boot_id: "b", seq: 200 + n, kind, epoch: 0, op_id: op, payload });
store.applyEvent(evt(1, "state_projected", "op1", { views: snaps.lost, fingerprint: "x" }));
const command = status();
store.applyEvent(evt(2, "step_verdict", "op1", { step_id: "s1", status: "passed", next_step_id: "s2" }));
const both = status();
console.log(JSON.stringify({ opened, command, both, lost: snaps.lost.announce_text,
  statuses: $$(".scenario-status").length }));
""",
    )
    assert out["opened"] == "Étape 1 sur 2 : Créer la branche."
    assert out["command"] == f"Commande terminée. {out['lost']} Étape 1 sur 2 : Créer la branche."
    assert out["both"] == (
        f"Commande terminée. {out['lost']} Étape réussie. Étape 2 sur 2 : Faire un commit."
    )
    assert out["statuses"] == 1


def test_le_focus_survit_a_une_mise_a_jour(tmp_path: Path, snapshots: dict) -> None:
    out = _js(
        tmp_path,
        snapshots,
        """
load("merged");
const target = $$(".graph-node")[2];
target.focus();
const id = target.getAttribute("data-element-id");
load("merged"); // nouvelle projection : tout est redessiné
const active = document.activeElement;
console.log(JSON.stringify({ id, kept: active.getAttribute("data-element-id"), same: active === target,
  tabstops: $$('.pane[data-pane="repo"] button').filter((b) => b.getAttribute("tabindex") === "0").map((b) => b.getAttribute("data-element-id")) }));
""",
    )
    assert out["kept"] == out["id"] and not out["same"]
    assert out["tabstops"] == [out["id"]]


# --- feuille de style : jetons seulement, contrastes des paires employées --------------------

REPO_PAIRS = (
    ("primary-deep", "primary-soft", 4.5),  # graph-branch, badge Agent
    ("ink", "discipline-context-soft", 4.5),  # graph-remote-ref
    ("ink", "surface", 4.5),  # graph-tag
    ("on-ink", "ink-fill", 4.5),  # graph-head, new-mark
    ("ink", "accent-soft", 4.5),  # staging-index, groupe Indexé
    ("ink", "primary-soft", 4.5),  # élément sélectionné
    ("ink", "surface-raised", 4.5),  # sélection, badge Collègue, groupes
    ("ink-soft", "surface-raised", 4.5),  # libellé « perdu · visible par reflog »
    ("ink-soft", "surface", 4.5),
    ("discipline-prompt", "surface-raised", 3),  # disque d'un commit (trait porteur)
    ("muted", "surface-raised", 3),  # commit perdu, arête vers un commit perdu
    ("ink-soft", "surface-raised", 3),  # arête
    ("discipline-context", "discipline-context-soft", 3),  # double bord de la ref distante
    ("primary", "primary-soft", 3),  # bord de la branche locale
)


@pytest.mark.parametrize("theme", ["clair", "sombre"])
def test_contrastes_du_graphe_et_de_l_index(theme: str) -> None:
    light, _media, forced = _blocks((CSS / "tokens.css").read_text(encoding="utf-8"))
    palette = _palette(light)
    if theme == "sombre":
        palette |= _palette(forced)
    low = [
        f"{fg}/{bg} {_ratio(palette[fg], palette[bg]):.2f} < {minimum}"
        for fg, bg, minimum in REPO_PAIRS
        if _ratio(palette[fg], palette[bg]) < minimum
    ]
    assert low == []
    assert set(REPO_PAIRS) - set(CONTRAST_PAIRS)  # ces paires complètent celles de la coquille


def test_feuille_du_depot_local_sans_couleur_en_dur() -> None:
    css = (CSS / "repo.css").read_text(encoding="utf-8")
    assert "/static/css/repo.css" in (STATIC / "index.html").read_text(encoding="utf-8")
    assert not re.search(r"#[0-9a-fA-F]{3,8}\b", css) and "opacity" not in css
    for size in re.findall(r"font-size:\s*(\d+(?:\.\d+)?)px", css):
        assert float(size) >= 12
    for rule in (".graph-commit", ".graph-edge", ".graph-head", ".graph-branch", ".graph-remote-ref",
                 ".graph-tag", ".graph-commit.is-lost", ".commit-list", ".new-mark", ".staging-index"):
        assert rule in css, rule
    assert "double" in css and "dasharray" in css and "dashed" in css
