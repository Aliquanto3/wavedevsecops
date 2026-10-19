# ruff: noqa: E501
"""Vue « Distant + PR » (Story 3.3) sous Node, sur la doublure de DOM, avec de vraies projections.

Les `views` viennent de `project` sur un vrai dépôt et un vrai `github.json` (checks dans les cinq
états, protection, revue du collègue, PR mergeable, PR mergée), sérialisées en JSON puis posées dans
le magasin du front. La doublure n'a ni mise en page ni lecteur d'écran : le rendu réel se vérifie
dans un navigateur.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

import pytest
from static_rules import STATIC
from test_github_sim import BASE
from test_repo_dom import MINIDOM
from test_shell_js import NODE, _run
from test_shell_ui import _blocks, _palette, _ratio

from wavedevsecops import github_sim
from wavedevsecops.config import Settings
from wavedevsecops.engine import prepare_workspace
from wavedevsecops.gitio import Git
from wavedevsecops.projections import project
from wavedevsecops.scenarios import LoadedScenario, parse_scenario

pytestmark = pytest.mark.skipif(NODE is None, reason="Node absent : comportement JS non exécuté")

CSS = STATIC / "css"

BLOCKED = """\
  - op: set_protection
    branch: main
    required_approvals: 2
    required_checks: [tests]
  - op: colleague_reaction
    trigger: pr_opened
    reviews:
      - {state: approved, body_text: "Bien vu."}
  - op: open_pr
    head: feature
    title_text: Change la valeur
    checks:
      - {job_id: lint, state: success}
      - {job_id: bandit, state: failure, required: true}
      - {job_id: build, state: running}
      - {job_id: audit, state: error}
      - {job_id: docs, state: queued}
"""
FREE = "  - op: open_pr\n    head: feature\n"


def _views(tmp_path: Path, git_path: Path, name: str, extra: str, merge: bool = False) -> dict:
    settings = Settings(data_dir=tmp_path / name)
    text = BASE.format(feature_path="autre.py") + extra
    loaded = LoadedScenario(parse_scenario(text, "essai.A.yaml"), Path("essai.A.yaml"), "0" * 64)
    prepared = prepare_workspace(loaded, "llm", settings=settings, git_path=git_path)
    git = Git.for_workspace(git_path, prepared.layout.root, settings)
    if merge:
        github_sim.merge_pr(git, prepared.layout, 1)
    return project(git, prepared.layout).views.model_dump(mode="json")


@pytest.fixture(scope="module")
def snapshots(tmp_path_factory: pytest.TempPathFactory, git_path: Path) -> dict[str, dict]:
    root = tmp_path_factory.mktemp("remote")
    return {
        "blocked": _views(root, git_path, "blocked", BLOCKED),
        "free": _views(root, git_path, "free", FREE),
        "merged": _views(root, git_path, "merged", FREE, merge=True),
        "nopr": _views(root, git_path, "nopr", ""),
    }


PRELUDE = f"""
import {{ installDom, makeEvent, press }} from "{MINIDOM}";
import fs from "node:fs";
const snaps = JSON.parse(fs.readFileSync(process.env.SNAPS, "utf8"));
const {{ document, main }} = installDom({{ width: 1920, height: 1080 }});
const posts = [];
globalThis.fetch = (url, opts) => {{ posts.push({{ url, body: JSON.parse(opts.body) }}); return Promise.resolve({{ ok: true, json: async () => ({{}}) }}); }};
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
const remote = () => $('.pane[data-pane="remote"]');
const texts = (sel, root = document) => [...root.querySelectorAll(sel)].map((n) => n.textContent);
"""


def _js(tmp_path: Path, snapshots: dict, body: str) -> dict:
    snaps = tmp_path / "snaps.json"
    snaps.write_text(json.dumps(snapshots), encoding="utf-8")
    os.environ["SNAPS"] = str(snaps)
    try:
        return json.loads(_run(tmp_path, f"{PRELUDE}\n{body}"))
    finally:
        del os.environ["SNAPS"]


def test_carte_de_pr_dans_l_ordre_de_l_ux(tmp_path: Path, snapshots: dict) -> None:
    out = _js(
        tmp_path,
        snapshots,
        """
load("blocked");
const card = $(".pr-card");
const rows = (sel) => texts(sel + " .check-job");
console.log(JSON.stringify({
  problems: store.state.problems,
  order: [...card.children].map((c) => c.className.split(" ")[0]),
  title: $(".pr-title-text").textContent,
  branches: card.querySelector(".pr-branches code").textContent,
  failing: rows(".is-failing"),
  others: rows(".is-others"),
  states: texts(".pr-check .check-state"),
  glyphs: texts(".pr-check .check-glyph"),
  required: $$(".pr-check").filter((r) => r.querySelector(".tag-required")).map((r) => r.querySelector(".check-job").textContent),
  requiredLabel: texts(".tag-required"),
  animated: $$(".pending-dot").length,
  runningIsDot: $(".pr-check.is-running .check-glyph").className,
  classes: $$(".pr-check").map((r) => r.className.split(" ")[1]),
  mergeDisabled: $('[data-action="merge"]').getAttribute("aria-disabled"),
  mergeReason: $(".btn-reason").textContent,
  reasons: texts(".merge-reason-link .reason-text"),
  counter: $(".review-counter").textContent,
  entries: texts(".review-entry .review-author"),
  badge: texts(".review-entry .graph-actor"),
  action: texts(".review-entry .review-action"),
  body: texts(".review-entry .review-body"),
  tabstops: $$('.pane[data-pane="remote"] button').filter((b) => b.getAttribute("tabindex") === "0").length,
}));
""",
    )
    assert out["problems"] == []
    assert out["order"] == ["pr-head", "pr-branches", "pr-checks", "merge-zone", "pr-checks", "review-log"]
    assert out["title"] == "Change la valeur" and out["branches"] == "feature → main"
    assert out["failing"] == ["audit", "bandit"]
    assert out["others"] == ["build", "docs", "tests", "lint"]
    assert out["states"] == ["Erreur de l'outil", "Échec", "En cours", "En attente", "En attente", "Réussi"]
    assert out["glyphs"] == ["⚠", "✗", "", "○", "○", "✓"]
    assert out["required"] == ["bandit", "tests"] and set(out["requiredLabel"]) == {"Obligatoire"}
    assert out["animated"] == 1 and "pending-dot" in out["runningIsDot"]  # seul « En cours » est animé
    assert out["classes"] == ["is-error", "is-failure", "is-running", "is-queued", "is-queued", "is-success"]
    assert out["mergeDisabled"] == "true" and out["mergeReason"]
    assert len(out["reasons"]) == 3 and "bandit" in out["reasons"][0] or "bandit" in out["reasons"][1]
    assert out["counter"] == "Approbations : 1 sur 2 2 approbations requises"
    assert out["entries"] == ["Sacha Martin"] and out["badge"] == ["Collègue"]
    assert out["action"] == ["a approuvé"] and out["body"] == ["Bien vu."]
    assert out["tabstops"] == 1


def test_raisons_de_blocage_liees_a_leur_element_et_selection_partagee(
    tmp_path: Path, snapshots: dict
) -> None:
    out = _js(
        tmp_path,
        snapshots,
        """
load("blocked");
const sel = selectionFor(store);
const links = $$(".merge-reason-link").map((b) => b.getAttribute("data-link"));
const bandit = $$(".pr-check").find((r) => r.querySelector(".check-job").textContent === "bandit");
const banditId = bandit.getAttribute("data-element-id");
$$(".merge-reason-link").find((b) => b.getAttribute("data-link") === banditId).dispatchEvent(makeEvent("click"));
const afterReason = { value: sel.value, rowSelected: bandit.classList.contains("is-selected"),
  pressed: bandit.getAttribute("aria-pressed") };
$(".pr-pick").dispatchEvent(makeEvent("click"));
const afterTitle = { value: sel.value, bandit: bandit.classList.contains("is-selected") };
$(".review-pick").dispatchEvent(makeEvent("click"));
const afterReview = sel.value;
$(".remote-ref").dispatchEvent(makeEvent("click"));
const afterRef = sel.value;
$(".remote-ref").dispatchEvent(makeEvent("click"));
console.log(JSON.stringify({ links, banditId, afterReason, afterTitle, afterReview, afterRef, cleared: sel.value,
  posts: posts.length }));
""",
    )
    assert out["afterReason"] == {"value": out["banditId"], "rowSelected": True, "pressed": "true"}
    assert out["banditId"].startswith("check:1:bandit:")
    assert out["links"][2] == "pr:1" and out["banditId"] in out["links"]
    assert out["afterTitle"] == {"value": "pr:1", "bandit": False}
    assert out["afterReview"] == "review:1:1"
    assert out["afterRef"].startswith("ref:refs/remotes/origin/")
    assert out["cleared"] is None and out["posts"] == 0


def test_merger_actif_envoie_l_intention_et_inactif_ne_fait_rien(
    tmp_path: Path, snapshots: dict
) -> None:
    out = _js(
        tmp_path,
        snapshots,
        """
load("blocked");
$('[data-action="merge"]').dispatchEvent(makeEvent("click"));
const blocked = posts.length;
load("free");
const button = $('[data-action="merge"]');
const state = { disabled: button.getAttribute("aria-disabled"), reasons: $$(".merge-reason-link").length,
  zone: $(".merge-zone").className };
button.dispatchEvent(makeEvent("click"));
await new Promise((r) => setTimeout(r, 0));
console.log(JSON.stringify({ blocked, state, posts }));
""",
    )
    assert out["blocked"] == 0
    assert out["state"]["disabled"] is None and out["state"]["reasons"] == 0
    assert "merge-blocked" not in out["state"]["zone"]
    assert out["posts"] == [{"url": "/api/ws/w/pr_merge", "body": {"number": 1}}]


def test_ouvrir_une_pr_sur_une_branche_poussee_et_vue_vide(
    tmp_path: Path, snapshots: dict
) -> None:
    out = _js(
        tmp_path,
        snapshots,
        """
load("nopr");
const empty = { title: texts(".remote-empty .empty-title"), text: texts(".remote-empty .empty"),
  cards: $$(".pr-card").length };
const refs = texts(".remote-ref .ref-name");
const open = $$('[data-action="open-pr"]');
const labels = open.map((b) => [b.textContent, b.getAttribute("data-head"), b.getAttribute("aria-label")]);
open[0].dispatchEvent(makeEvent("click"));
await new Promise((r) => setTimeout(r, 0));
// Aucune branche ni PR : l'état vide seul, sans liste de refs.
const bare = structuredClone(snaps.nopr);
bare.remote = { branches: [], pulls: [], error_text: "" };
store.applySnapshot({ workspace_id: "w", boot_id: "b", seq: 50, epoch: 0, state: "idle", views: bare });
const none = { title: texts(".empty-title", remote()), refs: $$(".remote-refs").length };
console.log(JSON.stringify({ empty, refs, labels, posts, none }));
""",
    )
    assert out["empty"] == {"title": ["Aucune PR."], "text": ["Poussez une branche, puis ouvrez une PR."], "cards": 0}
    assert out["refs"] == ["origin/feature", "origin/main"]
    assert out["labels"] == [["Ouvrir une PR", "feature", "Ouvrir une PR pour origin/feature"]]
    assert out["posts"] == [{"url": "/api/ws/w/pr_open", "body": {"head": "feature"}}]
    assert out["none"] == {"title": ["Aucune PR."], "refs": 0}


def test_pr_mergee_sans_bouton_et_erreur_de_lecture(tmp_path: Path, snapshots: dict) -> None:
    out = _js(
        tmp_path,
        snapshots,
        """
load("merged");
const merged = { buttons: $$('[data-action="merge"]').length, done: texts(".merge-done"),
  state: texts(".tag-state"), openPr: $$('[data-action="open-pr"]').length };
const broken = structuredClone(snaps.free);
broken.remote = { branches: [], pulls: [], error_text: "L'état du GitHub simulé est illisible. Recommencez." };
store.applySnapshot({ workspace_id: "w", boot_id: "b", seq: 60, epoch: 0, state: "idle", views: broken });
console.log(JSON.stringify({ merged, error: texts(".remote-error"), cards: $$(".pr-card").length }));
""",
    )
    assert out["merged"]["buttons"] == 0 and out["merged"]["openPr"] == 0
    assert out["merged"]["done"][0].startswith("Mergée dans main (")
    assert out["merged"]["state"] == ["Mergée"]
    assert out["error"] == ["L'état du GitHub simulé est illisible. Recommencez."] and out["cards"] == 0


def test_type_d_element_non_declare_refuse_la_vue(tmp_path: Path, snapshots: dict) -> None:
    out = _js(
        tmp_path,
        snapshots,
        """
const bad = structuredClone(snaps.blocked);
bad.remote.pulls[0].element_id = "path:head:x.txt";
store.applySnapshot({ workspace_id: "w", boot_id: "b", seq: 70, epoch: 0, state: "idle", views: bad });
console.log(JSON.stringify({ problems: store.state.problems.length, hasRemote: "remote" in store.state.views,
  title: texts(".empty-title", remote()) }));
""",
    )
    assert out["problems"] == 1 and out["hasRemote"] is False
    assert out["title"] == ["Aucune PR."]


# --- feuille de style : jetons seulement, contrastes des paires employées --------------------

REMOTE_PAIRS = (
    ("ink", "accent-soft", 4.5),  # pr-check réussi
    ("ink", "danger-soft", 4.5),  # pr-check en échec
    ("ink", "warning-soft", 4.5),  # pr-check erreur de l'outil, remote-error
    ("ink", "primary-soft", 4.5),  # pr-check en cours
    ("ink", "surface", 4.5),  # pr-check en attente, étiquettes
    ("ink-soft", "surface-raised", 4.5),  # branches, compteur
    ("ink-soft", "discipline-neutral-soft", 4.5),  # merge-blocked
    ("on-ink", "ink-fill", 4.5),  # étiquette Obligatoire
    ("ink", "surface-raised", 4.5),  # carte, journal
    ("muted", "surface-raised", 3),  # bord d'une carte, check d'un ancien commit
)


@pytest.mark.parametrize("theme", ["clair", "sombre"])
def test_contrastes_de_la_vue_distante(theme: str) -> None:
    light, _media, forced = _blocks((CSS / "tokens.css").read_text(encoding="utf-8"))
    palette = _palette(light)
    if theme == "sombre":
        palette |= _palette(forced)
    low = [
        f"{fg}/{bg} {_ratio(palette[fg], palette[bg]):.2f} < {minimum}"
        for fg, bg, minimum in REMOTE_PAIRS
        if _ratio(palette[fg], palette[bg]) < minimum
    ]
    assert low == []


def test_feuille_distante_sans_couleur_en_dur_ni_opacite() -> None:
    css = (CSS / "remote.css").read_text(encoding="utf-8")
    assert "/static/css/remote.css" in (STATIC / "index.html").read_text(encoding="utf-8")
    assert not re.search(r"#[0-9a-fA-F]{3,8}\b", css) and "opacity" not in css
    for size in re.findall(r"font-size:\s*(\d+(?:\.\d+)?)px", css):
        assert float(size) >= 12
    for rule in (".pr-card", ".pr-check.is-success", ".pr-check.is-failure", ".pending-dot", ".merge-blocked", ".review-log"):
        assert rule in css, rule
    assert css.count("animation:") == 1  # seul « En cours » est animé


def test_ouvrir_une_pr_inactif_pendant_une_action_et_focus_apres_merger(
    tmp_path: Path, snapshots: dict
) -> None:
    """Revue : « Ouvrir une PR » est inactif pendant une action de la file, comme Merger ; le
    focus d'un bouton qui disparaît après son action passe à la carte (ou à la branche)."""
    out = _js(
        tmp_path,
        snapshots,
        """
store.applySnapshot({ workspace_id: "w", boot_id: "b", seq: 80, epoch: 0, state: "command", views: snaps.nopr });
const open = $('[data-action="open-pr"]');
const busy = { disabled: open.getAttribute("aria-disabled"), reason: open.nextElementSibling.textContent };
open.dispatchEvent(makeEvent("click"));
await new Promise((r) => setTimeout(r, 0));
const busyPosts = posts.length;
load("free");
$('[data-action="merge"]').focus();
load("merged");
const afterMerge = document.activeElement.getAttribute("data-key");
load("nopr");
$('[data-action="open-pr"]').focus();
load("free");
const afterOpen = document.activeElement.getAttribute("data-key");
console.log(JSON.stringify({ busy, busyPosts, afterMerge, afterOpen }));
""",
    )
    assert out["busy"] == {"disabled": "true", "reason": "Une action est en cours."}
    assert out["busyPosts"] == 0
    assert out["afterMerge"] == "pr:1"
    assert out["afterOpen"] == "ref:refs/remotes/origin/feature"


# ------------------------------------------------------------------ story 7.4 : sortie d'un check
def _pipeline_snaps(snapshots: dict) -> dict:
    """La vue « blocked » où deux checks portent ce que projette le pipeline simulé (7.4)."""
    views = json.loads(json.dumps(snapshots["blocked"]))
    for check in views["remote"]["pulls"][0]["checks"]:
        if check["job_id"] == "bandit":  # échec : sortie, fichier:ligne lié
            check["output_text"] = "agent/tools.py:27:1: B602 shell=True\n1 issue\n"
            check["output_spans"] = [
                {"start": 0, "end": 14, "text": "agent/tools.py", "element_id": "path:worktree:agent/tools.py"}
            ]
            check["details"] = [
                {"rule_id": "B602", "message_text": "shell=True", "location_text": "agent/tools.py:27",
                 "link": "path:worktree:agent/tools.py"},
                {"rule_id": "B101", "message_text": "assert", "location_text": "hors/bac.py:3", "link": ""},
            ]
            check["output_element_id"] = "output:check-1-bandit-x"
        if check["job_id"] == "audit":  # erreur de l'outil : texte, Relancer
            check["output_text"] = "panic\n"
            check["tool_error_text"] = (
                "pip-audit s'est arrêté sans résultat (code 2). Ce n'est pas un défaut de votre code."
            )
            check["can_rerun"] = True
            check["output_element_id"] = "output:check-1-audit-x"
    return {**snapshots, "pipe": views}


def test_voir_la_sortie_erreur_de_l_outil_et_relancer(tmp_path: Path, snapshots: dict) -> None:
    out = _js(
        tmp_path,
        _pipeline_snaps(snapshots),
        """
load("pipe");
const sel = selectionFor(store);
const item = (job) => $$(".pr-check-item").find((i) => i.querySelector(".check-job").textContent === job);
const before = {
  toggles: texts('[data-action="toggle-output"]'),
  outputs: $$(".check-output").length,
  error: texts(".check-tool-error", item("audit")),
  errorState: item("audit").querySelector(".check-state").textContent,
  rerun: texts('[data-action="check-rerun"]'),
  links: $$(".check-detail-link", item("bandit")).map((b) => [b.textContent, b.getAttribute("data-link")]),
  plain: texts(".check-detail-where", item("bandit")),
  rules: texts(".check-detail-rule", item("bandit")),
  declared: texts('[data-action="toggle-output"]', item("lint")).length,
};
item("bandit").querySelector('[data-action="toggle-output"]').focus();
item("bandit").querySelector('[data-action="toggle-output"]').dispatchEvent(makeEvent("click"));
await new Promise((r) => setTimeout(r, 0));
const block = item("bandit").querySelector(".check-output");
const opened = {
  label: block.querySelector(".tool-output-label").textContent,
  text: block.querySelector(".tool-output-text").textContent,
  link: block.querySelector(".terminal-link").getAttribute("data-link"),
  expanded: item("bandit").querySelector('[data-action="toggle-output"]').getAttribute("aria-expanded"),
  toggle: item("bandit").querySelector('[data-action="toggle-output"]').textContent,
  roving: block.hasAttribute("data-roving"),
  focus: document.activeElement && document.activeElement.getAttribute("data-key"),
};
block.querySelector(".terminal-link").dispatchEvent(makeEvent("click"));
const linked = sel.value;
block.dispatchEvent(makeEvent("click"));
const designated = sel.value;
// Un nouveau dessin (projection suivante) garde la sortie dépliée ; la preuve part une seule fois.
load("pipe");
const kept = $$(".check-output").length;
item("bandit").querySelector('[data-action="toggle-output"]').dispatchEvent(makeEvent("click"));
item("bandit").querySelector('[data-action="toggle-output"]').dispatchEvent(makeEvent("click"));
item("audit").querySelector('[data-action="check-rerun"]').dispatchEvent(makeEvent("click"));
await new Promise((r) => setTimeout(r, 0));
console.log(JSON.stringify({ before, opened, linked, designated, kept, after: $$(".check-output").length,
  posts, problems: store.state.problems }));
""",
    )
    before = out["before"]
    assert before["toggles"] == ["Voir la sortie", "Voir la sortie"] and before["outputs"] == 0
    assert before["errorState"] == "Erreur de l'outil"
    assert before["error"] == [
        "pip-audit s'est arrêté sans résultat (code 2). Ce n'est pas un défaut de votre code."
    ]
    assert before["rerun"] == ["Relancer le check"]
    assert before["links"] == [["agent/tools.py:27", "path:worktree:agent/tools.py"]]
    assert before["plain"] == ["hors/bac.py:3"] and before["rules"] == ["B602", "B101"]
    assert before["declared"] == 0  # un check sans sortie n'a pas de « Voir la sortie »
    opened = out["opened"]
    assert opened["label"] == "bandit" and opened["text"] == "agent/tools.py:27:1: B602 shell=True\n1 issue\n"
    assert opened["link"] == "path:worktree:agent/tools.py"
    assert opened["expanded"] == "true" and opened["toggle"] == "Masquer la sortie"
    assert opened["roving"] and opened["focus"].startswith("toggle:check:1:bandit:")
    assert out["linked"] == "path:worktree:agent/tools.py"
    assert out["designated"] == "output:check-1-bandit-x"
    assert out["kept"] == 1 and out["after"] == 1
    assert out["posts"] == [
        {"url": "/api/ws/w/check_output_seen", "body": {"number": 1, "job_id": "bandit"}},
        {"url": "/api/ws/w/check_rerun", "body": {"number": 1, "job_id": "audit"}},
    ]
    assert out["problems"] == []
