# ruff: noqa: E501
"""`pipeline-tabs` (Story 7.6) sous Node, sur la doublure de DOM : « Voir dans le pipeline » sur un
check de la vue Distant + PR ouvre les trois écritures dans la vue Code, en lecture seule, avec les
lignes de la tâche surlignées et « lignes x à y » par onglet ; changer d'onglet garde la tâche ;
survoler un check éclaire ses lignes. Les données sont celles de vraies projections (`project`) et de
la vraie vue `pipeline_view` sur un vrai dépôt ; le serveur est une doublure en JS. La mise en page et
la lecture au lecteur d'écran se vérifient dans un navigateur."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
from static_rules import STATIC
from test_pipeline_files import NOTES, PIPELINE, _prepare
from test_repo_dom import MINIDOM
from test_shell_js import NODE, _run

from wavedevsecops.projections import project
from wavedevsecops.web.code import pipeline_view

pytestmark = pytest.mark.skipif(NODE is None, reason="Node absent : comportement JS non exécuté")

BROKEN = '  - op: write_file\n    path: Jenkinsfile\n    content: "pipeline { agent any }\\n"'

PRELUDE = f"""
import {{ installDom, makeEvent }} from "{MINIDOM}";
import fs from "node:fs";
const data = JSON.parse(fs.readFileSync(process.env.DATA, "utf8"));
const {{ document, main }} = installDom({{ width: 1920, height: 1080 }});
const calls = [];
let which = "ok";
const json = (status, body) => ({{ ok: status < 300, status, json: async () => body }});
globalThis.fetch = async (url, options = {{}}) => {{
  const u = new URL(url, "http://x");
  calls.push({{ path: u.pathname.split("/").pop(), search: u.search, method: options.method || "GET" }});
  if (u.pathname.endsWith("/code/tree")) return json(200, {{ files: [], truncated: false }});
  if (u.pathname.endsWith("/code/pipeline")) return which === "missing" ? json(404, {{ reason_text: "La PR n°9 n'existe pas." }}) : json(200, data[which]);
  return json(202, {{ op_id: "y" }});
}};
await import("@JS@/views.js");
const {{ mountWorkspace }} = await import("@JS@/workspace.js");
const {{ createStore }} = await import("@JS@/store.js");
const store = createStore();
mountWorkspace(main, {{ title: "Bac à sable libre", store, storage: {{ getItem: () => null, setItem() {{}} }} }});
store.applySnapshot({{ workspace_id: "w", boot_id: "b", seq: 1, epoch: 0, state: "idle", views: data.views }});
const $ = (s) => document.querySelector(s);
const $$ = (s) => [...document.querySelectorAll(s)];
const code = () => $('.pane[data-pane="code"]');
const flush = async () => {{ for (let i = 0; i < 8; i++) await new Promise((r) => setTimeout(r, 2)); }};
const texts = (sel, root = document) => [...root.querySelectorAll(sel)].map((n) => n.textContent);
const lit = (cls) => $$(`.pipeline-line.${{cls}}`).map((n) => Number(n.getAttribute("data-line")));
const rowOf = (job) => $$(".pr-check").find((r) => r.getAttribute("data-job") === job);
const viewButton = (job) => $$('[data-action="view-pipeline"]').find((b) => b.getAttribute("data-job") === job);
await flush();
"""


@pytest.fixture(scope="module")
def data_file(tmp_path_factory: pytest.TempPathFactory, git_path: Path) -> Path:
    root = tmp_path_factory.mktemp("tabs")
    payload = {}
    for name, feature in (("ok", NOTES), ("broken", BROKEN)):
        layout, git, _ = _prepare(root / name, git_path, feature)
        if name == "ok":
            payload["views"] = project(
                git, layout, pipeline_jobs=frozenset(PIPELINE.job_ids)
            ).views.model_dump(mode="json")
        payload[name] = pipeline_view(git, layout, PIPELINE, 1)
    path = root / "data.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _js(tmp_path: Path, data_file: Path, body: str) -> dict:
    os.environ["DATA"] = str(data_file)
    try:
        return json.loads(_run(tmp_path, f"{PRELUDE}\n{body}"))
    finally:
        del os.environ["DATA"]


def _ranges(data_file: Path, which: str = "ok") -> dict[str, dict[str, tuple[int, int]]]:
    payload = json.loads(data_file.read_text(encoding="utf-8"))
    return {
        tab["id"]: {j: (r["first"], r["last"]) for j, r in tab["jobs"].items() if r}
        for tab in payload[which]["tabs"]
    }


def _lines(first_last: tuple[int, int]) -> list[int]:
    return list(range(first_last[0], first_last[1] + 1))


def test_le_bouton_n_est_propose_que_pour_les_taches_du_pipeline(
    tmp_path: Path, data_file: Path
) -> None:
    out = _js(
        tmp_path,
        data_file,
        """
console.log(JSON.stringify({
  problems: store.state.problems,
  buttons: $$('[data-action="view-pipeline"]').map((b) => [b.getAttribute("data-job"), b.textContent]),
  checks: $$(".pr-check").map((r) => r.getAttribute("data-job")),
  tabsBefore: $$(".pipeline-tab").length,
  modeButtons: $$(".code-mode").map((b) => b.textContent),
}));
""",
    )
    assert out["problems"] == []
    assert sorted(job for job, _ in out["buttons"]) == ["gitleaks", "pytest", "ruff"]
    assert {label for _, label in out["buttons"]} == {"Voir dans le pipeline"}
    assert "bandit" in out["checks"]  # présent, mais sans bouton : hors de pipeline.yaml
    assert out["tabsBefore"] == 0 and out["modeButtons"] == ["Fichier", "Diff"]


def test_voir_dans_le_pipeline_ouvre_les_trois_onglets_en_lecture_seule(
    tmp_path: Path, data_file: Path
) -> None:
    out = _js(
        tmp_path,
        data_file,
        """
viewButton("pytest").click();
await flush();
console.log(JSON.stringify({
  mode: $$(".code-mode").map((b) => [b.textContent, b.getAttribute("aria-pressed"), b.hidden]),
  readOnly: $(".pipeline-readonly").textContent,
  notRun: $(".pipeline-not-run").textContent,
  title: $(".pipeline-title").textContent,
  tabs: $$(".pipeline-tab").map((t) => [t.querySelector(".pipeline-tab-name").textContent, t.querySelector(".pipeline-tab-range").textContent, t.getAttribute("aria-selected")]),
  role: $(".pipeline-tabs").getAttribute("role"),
  panelLabel: $(".pipeline-lines").getAttribute("aria-label"),
  path: $(".pipeline-path").textContent,
  job: lit("is-job"),
  litNone: lit("is-lit"),
  jobs: $$(".pipeline-job").map((b) => [b.getAttribute("data-job"), b.getAttribute("aria-pressed")]),
  editors: $$(".code-pipeline-panel textarea, .code-pipeline-panel input").length,
  filePanelHidden: $(".code-file-panel").hidden,
  fetched: calls.filter((c) => c.path === "pipeline").map((c) => c.search),
  posts: calls.filter((c) => c.method !== "GET").length,
  status: $(".code-status").textContent,
}));
""",
    )
    ranges = _ranges(data_file)
    assert out["mode"] == [
        ["Fichier", "false", False],
        ["Diff", "false", False],
        ["Pipeline", "true", False],
    ]
    assert out["readOnly"] == "Lecture seule"
    assert out["notRun"] == "Ces fichiers se lisent : rien ne s'exécute depuis cette vue."
    assert out["title"].startswith("Pipeline de la PR n°1, commit ")
    names = [(n, sel) for n, _, sel in out["tabs"]]
    assert names == [("GitHub Actions", "true"), ("Jenkins", "false"), ("GitLab CI", "false")]
    expected = {
        "github": ranges["github"]["pytest"],
        "jenkins": ranges["jenkins"]["pytest"],
        "gitlab": ranges["gitlab"]["pytest"],
    }
    # « lignes x à y » pour chaque onglet, tirées du serveur.
    assert [r for _, r, _ in out["tabs"]] == [
        f"lignes {a} à {b}" if a != b else f"ligne {a}" for a, b in expected.values()
    ]
    assert out["role"] == "tablist" and out["path"] == ".github/workflows/ci.yml"
    assert out["panelLabel"] == ".github/workflows/ci.yml, lecture seule"
    assert out["job"] == _lines(expected["github"]) and out["litNone"] == []
    assert out["jobs"] == [["ruff", "false"], ["pytest", "true"], ["gitleaks", "false"]]
    assert out["editors"] == 0 and out["filePanelHidden"]  # lecture seule : ni éditeur ni saisie
    assert out["fetched"] == ["?pr=1"] and out["posts"] == 0
    assert out["status"].startswith("Pipeline, pytest : ")


def test_changer_d_onglet_garde_la_tache_et_changer_de_tache_garde_l_onglet(
    tmp_path: Path, data_file: Path
) -> None:
    out = _js(
        tmp_path,
        data_file,
        """
viewButton("pytest").click();
await flush();
const tab = (id) => $$(".pipeline-tab").find((t) => t.getAttribute("data-tab") === id);
tab("jenkins").click();
const jenkins = { selected: $$(".pipeline-tab").map((t) => t.getAttribute("aria-selected")), path: $(".pipeline-path").textContent, job: lit("is-job"), pressed: $$(".pipeline-job").filter((b) => b.getAttribute("aria-pressed") === "true").map((b) => b.getAttribute("data-job")) };
tab("gitlab").click();
const gitlab = { path: $(".pipeline-path").textContent, job: lit("is-job") };
$$(".pipeline-job").find((b) => b.getAttribute("data-job") === "gitleaks").click();
const other = { path: $(".pipeline-path").textContent, job: lit("is-job"), ranges: $$(".pipeline-tab-range").map((n) => n.textContent) };
console.log(JSON.stringify({ jenkins, gitlab, other, fetched: calls.filter((c) => c.path === "pipeline").length }));
""",
    )
    ranges = _ranges(data_file)
    assert out["jenkins"]["selected"] == ["false", "true", "false"]
    assert out["jenkins"]["path"] == "Jenkinsfile"
    assert out["jenkins"]["job"] == _lines(ranges["jenkins"]["pytest"])
    assert out["jenkins"]["pressed"] == ["pytest"]
    assert out["gitlab"] == {"path": ".gitlab-ci.yml", "job": _lines(ranges["gitlab"]["pytest"])}
    assert out["other"]["path"] == ".gitlab-ci.yml"  # l'onglet est gardé
    assert out["other"]["job"] == _lines(ranges["gitlab"]["gitleaks"])
    assert all(r.startswith("ligne") for r in out["other"]["ranges"])
    assert out["fetched"] == 1  # changer d'onglet ou de tâche ne relit rien


def test_survoler_un_check_eclaire_ses_lignes_dans_l_onglet_ouvert(
    tmp_path: Path, data_file: Path
) -> None:
    out = _js(
        tmp_path,
        data_file,
        """
viewButton("pytest").click();
await flush();
$$(".pipeline-tab").find((t) => t.getAttribute("data-tab") === "jenkins").click();
const over = (job) => rowOf(job).dispatchEvent(makeEvent("mouseover", { bubbles: true }));
const out = (job) => rowOf(job).dispatchEvent(makeEvent("mouseout", { bubbles: true }));
over("ruff");
const ruff = { lit: lit("is-lit"), job: lit("is-job") };
out("ruff");
const left = lit("is-lit");
rowOf("gitleaks").focus();
const focused = lit("is-lit");
rowOf("gitleaks").blur?.();
rowOf("gitleaks").dispatchEvent(makeEvent("focusout", { bubbles: true }));
const blurred = lit("is-lit");
console.log(JSON.stringify({ ruff, left, focused, blurred, fetched: calls.filter((c) => c.path === "pipeline").length }));
""",
    )
    ranges = _ranges(data_file)["jenkins"]
    assert out["ruff"] == {"lit": _lines(ranges["ruff"]), "job": _lines(ranges["pytest"])}
    assert out["left"] == []
    assert out["focused"] == _lines(ranges["gitleaks"])  # au clavier comme à la souris
    assert out["blurred"] == []
    assert out["fetched"] == 1


def test_balises_absentes_un_constat_non_bloquant_et_les_autres_onglets_restent(
    tmp_path: Path, data_file: Path
) -> None:
    out = _js(
        tmp_path,
        data_file,
        """
which = "broken";
viewButton("ruff").click();
await flush();
const tab = (id) => $$(".pipeline-tab").find((t) => t.getAttribute("data-tab") === id);
const ranges = $$(".pipeline-tab-range").map((n) => n.textContent);
tab("jenkins").click();
const jenkins = { job: lit("is-job"), path: $(".pipeline-path").textContent, lines: $$(".pipeline-line").length };
console.log(JSON.stringify({ ranges, jenkins, notice: $(".pipeline-notice").textContent, github: lit("is-job").length }));
""",
    )
    assert out["ranges"][0].startswith("lignes") and out["ranges"][1] == "tâche non repérée"
    assert out["jenkins"] == {"job": [], "path": "Jenkinsfile", "lines": 1}
    assert "ne sont pas surlignées" in out["notice"]


def test_une_pr_inconnue_dit_pourquoi_sans_casser_la_vue(tmp_path: Path, data_file: Path) -> None:
    out = _js(
        tmp_path,
        data_file,
        """
which = "missing";
viewButton("ruff").click();
await flush();
console.log(JSON.stringify({ message: $(".code-pipeline-panel").textContent, tabs: $$(".pipeline-tab").length }));
""",
    )
    assert out == {"message": "La PR n°9 n'existe pas.", "tabs": 0}


def test_feuille_de_style_de_pipeline_tabs() -> None:
    css = (STATIC / "css" / "code.css").read_text(encoding="utf-8")
    for needle in (".pipeline-line.is-job", ".pipeline-line.is-lit", ".pipeline-tab[aria-selected"):
        assert needle in css
    assert "http" not in css  # aucune URL externe (AD-13)
