# ruff: noqa: E501
"""Vue « Code » (story 2.8) sous Node, sur la doublure de DOM : liste, éditeur, enregistrement,
conflit, ouverture externe et diff. Le serveur est une doublure en JS ; le diff est la vraie
projection de `parse_diff`. La mise en page, le clavier réel et la lecture au lecteur d'écran se
vérifient dans un navigateur."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

import pytest
from static_rules import STATIC
from test_shell_js import NODE, _run

from wavedevsecops.projections.diff import parse_diff

pytestmark = pytest.mark.skipif(NODE is None, reason="Node absent : comportement JS non exécuté")

MINIDOM = (Path(__file__).resolve().parent / "js" / "minidom.mjs").as_uri()
SHA = "a" * 40
DIFF_TEXT = (
    "diff --git a/f.txt b/f.txt\n--- a/f.txt\n+++ b/f.txt\n@@ -1,3 +1,5 @@\n"
    " garde\n-ancien\n+nouveau\n+<<<<<<< HEAD\n+nous\n"
    "diff --git a/new.txt b/new.txt\nnew file mode 100644\n--- /dev/null\n+++ b/new.txt\n@@ -0,0 +1 @@\n+x\n"
)

PRELUDE = f"""
import {{ installDom, makeEvent }} from "{MINIDOM}";
import fs from "node:fs";
const DIFFS = JSON.parse(fs.readFileSync(process.env.DIFFS, "utf8"));
const {{ document, main }} = installDom({{ width: 1920, height: 1080 }});
const disk = new Map([["a.txt", "un\\n"], ["b.txt", "deux\\n"]]);
const hashOf = (s) => "h" + [...s].reduce((n, c) => (n * 31 + c.charCodeAt(0)) >>> 0, 7).toString(16);
const calls = [];
const json = (status, data) => ({{ ok: status < 300, status, json: async () => data }});
globalThis.fetch = async (url, options = {{}}) => {{
  const u = new URL(url, "http://x");
  const body = options.body ? JSON.parse(options.body) : null;
  calls.push({{ path: u.pathname.split("/").pop(), search: u.search, method: options.method || "GET", body }});
  if (u.pathname.endsWith("/code/tree")) return json(200, {{ files: [...disk.keys()].sort(), truncated: false }});
  if (u.pathname.endsWith("/code/file")) {{
    const p = u.searchParams.get("path");
    if (!disk.has(p)) return json(404, {{ reason_text: "absent" }});
    return json(200, {{ path: p, content: disk.get(p), hash: hashOf(disk.get(p)), editable: true, note_text: "" }});
  }}
  if (u.pathname.endsWith("/code/diff")) return json(200, u.searchParams.get("target") === "worktree" ? DIFFS.worktree : DIFFS.commit);
  if (u.pathname.endsWith("/save_file")) {{
    if (hashOf(disk.get(body.path)) !== body.base_hash) return json(409, {{ reason_text: "Le fichier a changé sur le disque." }});
    disk.set(body.path, body.content);
    return json(202, {{ op_id: "x" }});
  }}
  return json(202, {{ op_id: "y" }});
}};
const views = await import("@JS@/views.js");
const {{ renderCode }} = await import("@JS@/code.js");
const {{ createStore }} = await import("@JS@/store.js");
const {{ selectionFor }} = await import("@JS@/selection.js");
const store = createStore();
store.applySnapshot({{ workspace_id: "w", boot_id: "b", seq: 1, epoch: 0, state: "idle", views: {{}} }});
const section = document.createElement("section");
section.className = "pane";
const body = document.createElement("div");
section.append(body);
main.append(section);
const code = renderCode(body, {{ pane: {{}}, store }}, views.renderEmpty, {{ settleMs: 0 }});
const $ = (s) => body.querySelector(s);
const $$ = (s) => [...body.querySelectorAll(s)];
const flush = async () => {{ for (let i = 0; i < 6; i++) await new Promise((r) => setTimeout(r, 2)); }};
const type = (value) => {{ const area = $(".editor-area"); area.value = value; area.dispatchEvent(makeEvent("input")); }};
await flush();
"""


@pytest.fixture
def diffs(tmp_path: Path) -> Path:
    path = tmp_path / "diffs.json"
    payload = {
        "worktree": parse_diff(DIFF_TEXT, "worktree").model_dump(mode="json"),
        "commit": parse_diff(DIFF_TEXT, SHA).model_dump(mode="json"),
    }
    payload["worktree"]["target_text"] = "Arbre de travail (depuis HEAD)"
    payload["commit"]["target_text"] = f"Commit {SHA[:7]}"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _js(tmp_path: Path, diffs: Path, body: str) -> dict:
    os.environ["DIFFS"] = str(diffs)
    try:
        return json.loads(_run(tmp_path, f"{PRELUDE}\n{body}"))
    finally:
        del os.environ["DIFFS"]


def test_liste_ouverture_point_plein_et_enregistrement(tmp_path: Path, diffs: Path) -> None:
    out = _js(
        tmp_path,
        diffs,
        """
const listed = $$(".code-file").map((b) => b.getAttribute("data-path"));
const emptyBefore = !$(".code-empty").hidden;
$$(".code-file")[0].click();
await flush();
const opened = { value: $(".editor-area").value, title: $(".code-path").textContent, unsaved: $(".code-unsaved").textContent, hasDot: $$(".dirty-dot").length };
type("un\\ndeux\\n");
const dirty = { unsaved: $(".code-unsaved").textContent, dot: $$(".dirty-dot").map((d) => d.textContent), hidden: $$(".code-file .visually-hidden").map((d) => d.textContent), gutter: $$(".editor-no").length };
$(".code-save").click();
await flush();
const after = { unsaved: $(".code-unsaved").textContent, dots: $$(".dirty-dot").length, status: $(".code-status").textContent, disk: disk.get("a.txt") };
console.log(JSON.stringify({ listed, emptyBefore, opened, dirty, after, post: calls.filter((c) => c.method === "POST") }));
""",
    )
    assert out["listed"] == ["a.txt", "b.txt"] and out["emptyBefore"]
    assert out["opened"] == {"value": "un\n", "title": "a.txt", "unsaved": "", "hasDot": 0}
    assert out["dirty"]["unsaved"] == "● non enregistré"
    assert out["dirty"]["dot"] == ["●"] and out["dirty"]["hidden"] == [" non enregistré"]
    assert out["dirty"]["gutter"] == 3
    assert out["after"] == {
        "unsaved": "",
        "dots": 0,
        "status": "Enregistré : a.txt.",
        "disk": "un\ndeux\n",
    }
    [post] = out["post"]
    assert post["path"] == "save_file"
    assert post["body"]["path"] == "a.txt" and post["body"]["content"] == "un\ndeux\n"
    assert re.fullmatch(r"h[0-9a-f]+", post["body"]["base_hash"])


def test_ctrl_s_enregistre(tmp_path: Path, diffs: Path) -> None:
    out = _js(
        tmp_path,
        diffs,
        """
$$(".code-file")[1].click();
await flush();
type("changé\\n");
const event = makeEvent("keydown", { key: "s", ctrlKey: true });
$(".editor-area").dispatchEvent(event);
await flush();
console.log(JSON.stringify({ prevented: event.defaultPrevented, disk: disk.get("b.txt") }));
""",
    )
    assert out == {"prevented": True, "disk": "changé\n"}


def test_conflit_garder_ma_version_et_recharger(tmp_path: Path, diffs: Path) -> None:
    out = _js(
        tmp_path,
        diffs,
        """
$$(".code-file")[0].click();
await flush();
type("ma version\\n");
disk.set("a.txt", "version du disque\\n");      // modifié ailleurs depuis l'ouverture
$(".code-save").click();
await flush();
const bar = { hidden: $(".code-conflict").hidden, role: $(".code-conflict").getAttribute("role"), text: $(".code-conflict-text").textContent, buttons: $$(".code-conflict button").map((b) => b.textContent), disk: disk.get("a.txt") };
$(".code-reload").click();
await flush();
const reloaded = { value: $(".editor-area").value, hidden: $(".code-conflict").hidden, unsaved: $(".code-unsaved").textContent };
// Second tour : on garde sa version.
type("ma version\\n");
disk.set("a.txt", "encore ailleurs\\n");
$(".code-save").click();
await flush();
$(".code-keep").click();
await flush();
console.log(JSON.stringify({ bar, reloaded, kept: disk.get("a.txt"), hiddenAfter: $(".code-conflict").hidden, saves: calls.filter((c) => c.path === "save_file").length }));
""",
    )
    assert out["bar"] == {
        "hidden": False,
        "role": "alert",
        "text": "Le fichier a changé sur le disque depuis son ouverture.",
        "buttons": ["Garder ma version", "Recharger"],
        "disk": "version du disque\n",
    }
    assert out["reloaded"] == {"value": "version du disque\n", "hidden": True, "unsaved": ""}
    assert out["kept"] == "ma version\n" and out["hiddenAfter"] is True
    assert out["saves"] == 3  # refus, refus, enregistrement forcé


def test_ouvrir_dans_mon_editeur_envoie_open_external(tmp_path: Path, diffs: Path) -> None:
    out = _js(
        tmp_path,
        diffs,
        """
$$(".code-file")[1].click();
await flush();
$(".code-external").click();
await flush();
console.log(JSON.stringify(calls.filter((c) => c.path === "open_external")));
""",
    )
    assert [c["body"] for c in out] == [{"path": "b.txt"}]


def test_marqueurs_de_conflit_visibles_et_editables(tmp_path: Path, diffs: Path) -> None:
    out = _js(
        tmp_path,
        diffs,
        """
$$(".code-file")[0].click();
await flush();
type("a\\n<<<<<<< HEAD\\nnous\\n=======\\neux\\n>>>>>>> feature\\nz\\n");
console.log(JSON.stringify({
  gutter: $$(".editor-no").map((n) => n.textContent),
  flagged: $$(".editor-no.is-conflict").length,
  message: $(".code-markers").textContent,
  hidden: $(".code-markers").hidden,
  readonly: $(".editor-area").hasAttribute("readonly"),
}));
""",
    )
    assert out["gutter"][1] == "⚠ 2" and out["gutter"][3] == "⚠ 4" and out["gutter"][5] == "⚠ 6"
    assert out["flagged"] == 3 and out["hidden"] is False and not out["readonly"]
    assert "lignes 2, 4, 6" in out["message"]


def test_selection_d_un_commit_montre_son_diff(tmp_path: Path, diffs: Path) -> None:
    out = _js(
        tmp_path,
        diffs,
        """
const selection = selectionFor(store);
selection.set("commit:" + "a".repeat(40));
await flush();
const files = $$(".diff-file-header");
const lines = $$(".diff-line");
const diffCall = calls.filter((c) => c.path === "diff").map((c) => c.search);
const snapshot = {
  diffCall,
  target: $(".diff-target-text").textContent,
  headers: files.map((f) => [f.getAttribute("data-element-id"), f.getAttribute("aria-label"), f.textContent]),
  lines: lines.map((l) => [l.getAttribute("data-element-id"), l.className, l.querySelector(".diff-marker").textContent, l.getAttribute("aria-label"), l.getAttribute("tabindex"), l.hasAttribute("data-roving")]),
  conflict: lines.map((l) => l.querySelectorAll(".diff-conflict-mark").length),
  worktreeButton: $$(".diff-worktree").length,
  panelHidden: [$(".code-file-panel").hidden, $(".code-diff-panel").hidden],
  group: $(".diff-view").getAttribute("aria-label"),
  roles: [files[0].getAttribute("role"), files[0].getAttribute("aria-level"), lines[0].getAttribute("role")],
};
$(".diff-worktree").click();
await flush();
snapshot.afterClear = { selection: selection.value, target: $(".diff-target-text").textContent, button: $$(".diff-worktree").length, last: calls.filter((c) => c.path === "diff").pop().search };
console.log(JSON.stringify(snapshot));
""",
    )
    assert out["diffCall"] == [f"?target={'a' * 40}"]
    assert out["target"] == f"Commit {SHA[:7]}" and out["group"] == out["target"]
    assert out["panelHidden"] == [True, False] and out["worktreeButton"] == 1
    # Un nom accessible ne vaut que sur un rôle qui l'admet (pas sur un div générique).
    assert out["roles"] == ["heading", "3", "group"]
    [first, second] = out["headers"]
    assert first[0] == "path:head:f.txt" and "modifié" in first[1] and "modifié · +3 −1" in first[2]
    assert second[0] == "path:head:new.txt" and "nouveau fichier" in second[2]
    lines = out["lines"]
    assert [row[2] for row in lines] == [" ", "−", "+", "+", "+", "+"]
    assert lines[1][0] == f"diffline:{SHA}:f.txt:old:2"
    assert lines[2][0] == f"diffline:{SHA}:f.txt:new:2"
    assert "is-removed" in lines[1][1] and "is-added" in lines[2][1] and "is-context" in lines[0][1]
    assert (
        lines[1][3] == "Ligne supprimée 2 : ancien" and lines[2][3] == "Ligne ajoutée 2 : nouveau"
    )
    assert all(row[4] in ("-1", "0") and row[5] for row in lines)
    assert out["conflict"] == [0, 0, 0, 1, 0, 0]
    assert out["afterClear"] == {
        "selection": None,
        "target": "Arbre de travail (depuis HEAD)",
        "button": 0,
        "last": "?target=worktree",
    }


def test_onglet_diff_montre_l_arbre_de_travail(tmp_path: Path, diffs: Path) -> None:
    out = _js(
        tmp_path,
        diffs,
        """
$$(".code-mode")[1].click();
await flush();
console.log(JSON.stringify({ last: calls.filter((c) => c.path === "diff").pop().search, pressed: $$(".code-mode").map((b) => b.getAttribute("aria-pressed")) }));
""",
    )
    assert out == {"last": "?target=worktree", "pressed": ["false", "true"]}


def test_feuille_de_la_vue_code() -> None:
    css = (STATIC / "css" / "code.css").read_text(encoding="utf-8")
    assert "/static/css/code.css" in (STATIC / "index.html").read_text(encoding="utf-8")
    assert not re.search(r"#[0-9a-fA-F]{3,8}\b", css) and "opacity" not in css
    for size in re.findall(r"font-size:\s*(\d+(?:\.\d+)?)px", css):
        assert float(size) >= 12
    assert "var(--diff-line-height)" in css
    assert "var(--color-accent-soft)" in css and "var(--color-danger-soft)" in css


def test_aucune_url_externe_dans_le_composant_d_edition() -> None:
    for name in ("editor.js", "code.js"):
        source = (STATIC / "js" / name).read_text(encoding="utf-8")
        assert not re.search(r"https?://", source), name
