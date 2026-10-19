# ruff: noqa: E501
"""Suivre un élément d'une vue à l'autre et lire son explication (story 2.10) sous Node, sur la
doublure de DOM, avec de vraies projections.

Les `views` viennent de `project` sur un vrai dépôt et un vrai GitHub simulé (une PR, des checks,
une revue) : `links`, `names` et `explain` sont ceux du serveur. Le diff est la vraie projection de
`parse_diff`, l'explication celle de `content/explanations.yaml`. La doublure n'a ni mise en page,
ni défilement, ni lecteur d'écran : le rendu réel se vérifie dans un navigateur.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

import pytest
import yaml
from static_rules import STATIC
from test_remote_dom import BLOCKED, _views
from test_repo_dom import MINIDOM
from test_shell_js import NODE, _run

from wavedevsecops.config import Settings
from wavedevsecops.projections.diff import parse_diff
from wavedevsecops.web.glossary import glossary_body

pytestmark = pytest.mark.skipif(NODE is None, reason="Node absent : comportement JS non exécuté")

CSS = STATIC / "css"
CONTENT = Path(__file__).resolve().parent.parent / "content"
UNIFIED = (
    "diff --git a/src/app.py b/src/app.py\n--- a/src/app.py\n+++ b/src/app.py\n"
    "@@ -1,2 +1,2 @@\n import os\n-print(1)\n+print(2)\n"
)


@pytest.fixture(scope="module")
def snaps(tmp_path_factory: pytest.TempPathFactory, git_path: Path) -> dict:
    root = tmp_path_factory.mktemp("liens-dom")
    views = _views(root, git_path, "pr", BLOCKED)
    sha = views["remote"]["branches"][0]["sha"]
    return {
        "views": views,
        "sha": sha,
        "explanations": yaml.safe_load((CONTENT / "explanations.yaml").read_text("utf-8")),
        "glossary": glossary_body(Settings(content_dir=CONTENT)),
        "diff": {
            **parse_diff(UNIFIED, sha).model_dump(mode="json"),
            "target_text": f"Commit {sha[:7]}",
        },
    }


PRELUDE = f"""
import {{ installDom, makeEvent, press }} from "{MINIDOM}";
import fs from "node:fs";
const snaps = JSON.parse(fs.readFileSync(process.env.SNAPS, "utf8"));
const {{ document, main }} = installDom({{ width: 1920, height: 1080 }});
const calls = [];
const json = (status, data) => ({{ ok: status < 300, status, json: async () => data }});
globalThis.fetch = async (url) => {{
  const u = new URL(url, "http://x");
  calls.push(u.pathname + u.search);
  if (u.pathname === "/api/explanations") return json(200, snaps.explanations);
  if (u.pathname === "/api/glossary") return json(200, snaps.glossary);
  if (u.pathname.endsWith("/code/tree")) return json(200, {{ files: ["src/app.py"], truncated: false }});
  if (u.pathname.endsWith("/code/diff")) return json(200, snaps.diff);
  return json(404, {{ reason_text: "absent" }});
}};
await import("@JS@/views.js");
const {{ mountWorkspace }} = await import("@JS@/workspace.js");
const {{ createStore }} = await import("@JS@/store.js");
const {{ selectionFor }} = await import("@JS@/selection.js");
const store = createStore();
mountWorkspace(main, {{ title: "Bac à sable libre", store, storage: {{ getItem: () => null, setItem() {{}} }}, fetchImpl: globalThis.fetch }});
const selection = selectionFor(store);
const $ = (s) => document.querySelector(s);
const $$ = (s) => [...document.querySelectorAll(s)];
const flush = async () => {{ for (let i = 0; i < 8; i++) await new Promise((r) => setTimeout(r, 2)); }};
let seq = 1;
const load = () => store.applySnapshot({{ workspace_id: "w", boot_id: "b", seq: seq++, epoch: 0, state: "idle", views: snaps.views }});
const event = (type, init) => makeEvent(type, init);
const over = (node) => node.dispatchEvent(event("pointerover"));
const idOf = (n) => n.getAttribute("data-element-id") || n.getAttribute("data-ref") || n.getAttribute("data-link");
const nodes = () => $$(".views-grid [data-element-id], .views-grid [data-ref], .views-grid [data-link]");
const marked = () => [...new Set(nodes().filter((n) => n.classList.contains("is-linked")).map(idOf))].sort();
const ws = $(".workspace");
const commitId = `commit:${{snaps.sha}}`;
const output = (text, spans = [], extra = {{}}) => store.applyEvent({{ kind: "terminal_output", boot_id: "b", epoch: 0, seq: 1000 + seq++, op_id: extra.op || "", payload: {{ stream: "stdout", text, lang: "", spans, tool: extra.tool || "", explain_ref: extra.explain || "" }} }});
load();
await flush();
"""


def _js(tmp_path: Path, snaps: dict, body: str) -> dict:
    path = tmp_path / "snaps.json"
    path.write_text(json.dumps(snaps), encoding="utf-8")
    os.environ["SNAPS"] = str(path)
    try:
        return json.loads(_run(tmp_path, f"{PRELUDE}\n{body}"))
    finally:
        del os.environ["SNAPS"]


def _mirror(links: dict[str, list[str]], start: str) -> set[str]:
    """Voisins directs d'un élément, arêtes lues dans les deux sens (l'oracle du test)."""
    out = {start, *links.get(start, [])}
    out |= {key for key, targets in links.items() if start in targets}
    return out


def test_survol_allume_les_correspondants_dans_toutes_les_vues(tmp_path: Path, snaps: dict) -> None:
    expected = sorted(_mirror(snaps["views"]["links"], "pr:1"))
    out = _js(
        tmp_path,
        snaps,
        f"""
const EXPECTED = new Set({json.dumps(expected)});
over($(".pr-pick"));
const wrong = nodes().filter((n) => n.classList.contains("is-linked") !== EXPECTED.has(idOf(n))).length;
console.log(JSON.stringify({{ lit: marked(), wrong, linking: ws.getAttribute("data-linking"), selected: selection.value }}));
""",
    )
    assert out["wrong"] == 0 and out["linking"] == "on"
    assert out["selected"] is None  # survoler ne sélectionne pas
    assert "pr:1" in out["lit"] and f"commit:{snaps['sha']}" in expected
    # La branche distante est dans le volet Distant et, par le même element_id, dans le graphe.
    branch = snaps["views"]["remote"]["branches"][0]["element_id"]
    assert branch in out["lit"]


def test_la_ref_du_graphe_et_celle_du_distant_s_allument_ensemble(
    tmp_path: Path, snaps: dict
) -> None:
    branch = snaps["views"]["remote"]["branches"][0]["element_id"]
    out = _js(
        tmp_path,
        snaps,
        f"""
over($('.remote-ref[data-element-id="{branch}"]'));
const same = nodes().filter((n) => idOf(n) === "{branch}");
console.log(JSON.stringify({{ n: same.length, lit: same.filter((n) => n.classList.contains("is-linked")).length,
  inGraph: same.filter((n) => n.closest(".repo-view")).length }}));
""",
    )
    assert out["n"] >= 2 and out["lit"] == out["n"] and out["inGraph"] >= 1


def test_sans_survol_ni_selection_rien_n_est_lie(tmp_path: Path, snaps: dict) -> None:
    out = _js(
        tmp_path,
        snaps,
        """
over($(".pr-pick"));
ws.dispatchEvent(event("pointerleave", { bubbles: false }));
console.log(JSON.stringify({ lit: marked(), linking: ws.getAttribute("data-linking") }));
""",
    )
    assert out == {"lit": [], "linking": None}


def test_selection_unique_persistante_et_effacee_par_un_nouveau_clic(
    tmp_path: Path, snaps: dict
) -> None:
    out = _js(
        tmp_path,
        snaps,
        """
const pick = () => $$(`.graph-node[data-element-id="${commitId}"]`)[0];
pick().click();
const first = { value: selection.value, pressed: pick().getAttribute("aria-pressed"), selected: $$(".graph-node.is-selected").length };
over($(".pane-title"));   // le pointeur quitte l'élément : la sélection garde les liens
const kept = { lit: marked().length, linking: ws.getAttribute("data-linking") };
$(".remote-ref").click();  // une seule sélection à la fois
const second = { value: selection.value, graphSelected: $$(".graph-node.is-selected").length };
$(".remote-ref").click();  // un nouveau clic l'efface
console.log(JSON.stringify({ first, kept, second, cleared: selection.value, linking: ws.getAttribute("data-linking"), lit: marked().length }));
""",
    )
    assert out["first"] == {"value": f"commit:{snaps['sha']}", "pressed": "true", "selected": 1}
    assert out["kept"]["lit"] > 1 and out["kept"]["linking"] == "on"
    assert out["second"]["graphSelected"] == 0 and out["second"]["value"].startswith(
        "ref:refs/remotes/origin/"
    )
    assert out["cleared"] is None and out["linking"] is None and out["lit"] == 0


def test_une_selection_pr_ou_check_survit_au_redessin_du_depot(tmp_path: Path, snaps: dict) -> None:
    """Report de la story 3.3 : le volet Dépôt local ne vide plus la sélection d'un autre volet."""
    out = _js(
        tmp_path,
        snaps,
        """
$(".pr-pick").click();
const check = $(".pr-check");
const checkId = idOf(check);
load();
await flush();
const afterPr = selection.value;
check.click();
load();
await flush();
output("sortie", [], { op: "o9", tool: "ruff", explain: "terminal.output" });
$(".tool-output").click();
load();
await flush();
console.log(JSON.stringify({ afterPr, afterOutput: selection.value, checkId }));
""",
    )
    assert out["afterPr"] == "pr:1" and out["afterOutput"] == "output:o9"


def test_une_selection_perimee_quitte_la_selection(tmp_path: Path, snaps: dict) -> None:
    out = _js(
        tmp_path,
        snaps,
        """
selection.set("pr:9");
load();
await flush();
console.log(JSON.stringify({ value: selection.value }));
""",
    )
    assert out["value"] is None


def test_le_diff_se_lie_au_commit_et_garde_sa_cible_quand_on_selectionne_une_ligne(
    tmp_path: Path, snaps: dict
) -> None:
    out = _js(
        tmp_path,
        snaps,
        """
$$(`.graph-node[data-element-id="${commitId}"]`)[0].click();
await flush();
const lines = $$(".diff-line");
const diffCalls = () => calls.filter((c) => c.includes("/code/diff")).length;
const before = diffCalls();
over($$(`.graph-node[data-element-id="${commitId}"]`)[0]);
const litByCommit = lines.filter((l) => l.classList.contains("is-linked")).length;
over(lines[1]);
const commitLit = $$(`.graph-node[data-element-id="${commitId}"]`)[0].classList.contains("is-linked");
lines[1].click();                    // une ligne se sélectionne comme le reste
await flush();
const chosen = { value: selection.value, mark: lines[1].classList.contains("is-selected"), current: lines[1].getAttribute("aria-current") };
const keptDiff = diffCalls() === before;   // le diff du commit reste affiché
lines[2].focus();
press("Enter", { target: lines[2] });      // Entrée sélectionne aussi
await flush();
console.log(JSON.stringify({ n: lines.length, litByCommit, commitLit, chosen, keptDiff, enter: selection.value === lines[2].getAttribute("data-element-id"),
  pressedTarget: $(".diff-target-text").textContent }));
""",
    )
    assert out["n"] == 3
    assert out["litByCommit"] == 3  # toutes les lignes du diff du commit
    assert out["commitLit"] is True
    assert out["chosen"]["mark"] is True and out["chosen"]["current"] == "true"
    assert out["chosen"]["value"].startswith("diffline:")
    assert out["keptDiff"] is True and out["enter"] is True
    assert out["pressedTarget"].startswith("Commit ")


def test_une_ligne_de_diff_disparue_n_est_plus_selectionnee(tmp_path: Path, snaps: dict) -> None:
    out = _js(
        tmp_path,
        snaps,
        """
$$(`.graph-node[data-element-id="${commitId}"]`)[0].click();
await flush();
selection.set("diffline:" + snaps.sha + ":src/app.py:new:99");
load();       // le diff est relu : cette ligne n'y est pas
await flush();
console.log(JSON.stringify({ value: selection.value, target: $(".diff-target-text").textContent }));
""",
    )
    assert out["value"] is None
    assert out["target"].startswith("Commit ")  # l'effacement ne ramène pas à l'arbre de travail


def test_terminal_lignes_liees_en_terminal_lit_les_autres_en_retrait(
    tmp_path: Path, snaps: dict
) -> None:
    out = _js(
        tmp_path,
        snaps,
        """
const short = snaps.sha.slice(0, 7);
output(`* ${short} Fonction`, [{ start: 2, end: 9, text: short, element_id: commitId }]);
output("rien de lié ici");
await flush();
over($$(`.graph-node[data-element-id="${commitId}"]`)[0]);
const chunks = $$(".terminal-log > *");
console.log(JSON.stringify({ lit: chunks.map((c) => c.classList.contains("terminal-lit")), ids: chunks.map((c) => c.getAttribute("data-span-ids")), linking: ws.getAttribute("data-linking") }));
""",
    )
    assert out["lit"] == [True, False] and out["linking"] == "on"
    assert out["ids"] == [f"commit:{snaps['sha']}", None]


def test_le_focus_relie_le_resume_des_elements_lies_par_aria_describedby(
    tmp_path: Path, snaps: dict
) -> None:
    out = _js(
        tmp_path,
        snaps,
        """
const button = $$(`.graph-node[data-element-id="${commitId}"]`)[0];
button.focus();
const summary = document.getElementById("link-summary");
const during = { describedby: button.getAttribute("aria-describedby"), text: summary.textContent, lit: marked().length };
button.dispatchEvent(event("focusout"));
const after = { describedby: button.getAttribute("aria-describedby"), text: summary.textContent, lit: marked().length };
console.log(JSON.stringify({ during, after }));
""",
    )
    assert out["during"]["describedby"] == "link-summary" and out["during"]["lit"] > 1
    assert re.fullmatch(r"\d+ éléments? liés?? : .+", out["during"]["text"])
    assert "PR n°1" in out["during"]["text"] or "ref origin/" in out["during"]["text"]
    assert out["after"] == {"describedby": None, "text": "", "lit": 0}


def test_le_i_ouvre_l_explication_au_clic_jamais_au_survol_et_echap_rend_le_focus(
    tmp_path: Path, snaps: dict
) -> None:
    out = _js(
        tmp_path,
        snaps,
        """
let escapes = 0;
document.addEventListener("keydown", (e) => { if (e.key === "Escape") escapes++; });
const trigger = $(`.explain-trigger[data-explain-for="${commitId}"]`);
over(trigger);
await flush();
const hovered = $$(".explain-popover").length;
trigger.click();
await flush();
const popover = $(".explain-popover");
const opened = { role: popover.getAttribute("role"), title: $(".explain-title").textContent, body: $(".explain-body").textContent,
  ref: popover.getAttribute("data-explain-ref"), expanded: trigger.getAttribute("aria-expanded"), focusInside: document.activeElement === popover,
  labelled: document.getElementById(popover.getAttribute("aria-labelledby")).textContent, label: trigger.getAttribute("aria-label"), tabindex: trigger.getAttribute("tabindex"), selection: selection.value };
press("Escape", { target: popover });
const closed = { popovers: $$(".explain-popover").length, focusOnTrigger: document.activeElement === trigger, expanded: trigger.getAttribute("aria-expanded"), escapes };
console.log(JSON.stringify({ hovered, opened, closed, fetched: calls.filter((c) => c === "/api/explanations").length }));
""",
    )
    assert out["hovered"] == 0  # jamais au seul survol
    expected = snaps["explanations"]["entries"]["graph.commit"]
    assert out["opened"]["role"] == "dialog" and out["opened"]["title"] == expected["title_text"]
    assert out["opened"]["body"].startswith("Un commit est une photo")
    assert out["opened"]["ref"] == "graph.commit" and out["opened"]["expanded"] == "true"
    assert out["opened"]["focusInside"] and out["opened"]["labelled"] == expected["title_text"]
    assert (
        out["opened"]["label"].startswith("Expliquer commit ") and out["opened"]["tabindex"] == "-1"
    )
    assert out["opened"]["selection"] is None  # le « i » ne sélectionne pas l'élément
    assert out["closed"] == {
        "popovers": 0,
        "focusOnTrigger": True,
        "expanded": "false",
        "escapes": 0,
    }
    assert out["fetched"] == 1


def test_le_popover_liste_les_elements_lies_et_un_choix_les_selectionne(
    tmp_path: Path, snaps: dict
) -> None:
    out = _js(
        tmp_path,
        snaps,
        """
const trigger = $(`.explain-trigger[data-explain-for="${commitId}"]`);
trigger.click();
await flush();
const list = $(".explain-links");
const before = { hidden: list.hidden, expanded: $(".explain-links-toggle").getAttribute("aria-expanded"), label: $(".explain-links-toggle").textContent };
$(".explain-links-toggle").click();
const open = { hidden: list.hidden, expanded: $(".explain-links-toggle").getAttribute("aria-expanded") };
const names = $$(".explain-link").map((b) => b.textContent);
$$(".explain-link")[0].click();
await flush();
console.log(JSON.stringify({ before, open, names, picked: selection.value, popovers: $$(".explain-popover").length }));
""",
    )
    assert out["before"] == {"hidden": True, "expanded": "false", "label": "Voir les éléments liés"}
    assert out["open"] == {"hidden": False, "expanded": "true"}
    assert out["names"] and out["picked"] is not None and out["popovers"] == 0


def test_explications_des_sorties_d_outil_sans_selectionner_le_bloc(
    tmp_path: Path, snaps: dict
) -> None:
    out = _js(
        tmp_path,
        snaps,
        """
output("All checks passed!\\n", [], { op: "o7", tool: "ruff", explain: "terminal.output" });
await flush();
const block = $(".tool-output");
const trigger = block.querySelector(".explain-trigger");
trigger.click();
await flush();
console.log(JSON.stringify({ ref: block.getAttribute("data-explain-ref"), has: Boolean(trigger), title: $(".explain-title").textContent, selection: selection.value }));
""",
    )
    assert out["ref"] == "terminal.output" and out["has"]
    assert out["title"] == snaps["explanations"]["entries"]["terminal.output"]["title_text"]
    assert out["selection"] is None


def test_une_sortie_d_outil_allume_ce_qu_elle_cite_dans_les_deux_sens(
    tmp_path: Path, snaps: dict
) -> None:
    out = _js(
        tmp_path,
        snaps,
        """
const short = snaps.sha.slice(0, 7);
output(`src/app.py:1:1 voir ${short}\n`, [{ start: 20, end: 27, text: short, element_id: commitId }], { op: "o8", tool: "ruff", explain: "terminal.output" });
await flush();
const block = $(".tool-output");
over(block);
const hovered = { graph: marked().includes(commitId), lit: block.classList.contains("terminal-lit"), linking: ws.getAttribute("data-linking") };
over($(".views-grid"));
block.querySelector(".explain-trigger").click();
await flush();
$(".explain-links-toggle").click();
const names = $$(".explain-link").map((b) => b.getAttribute("data-link-id"));
console.log(JSON.stringify({ hovered, names }));
""",
    )
    assert out["hovered"] == {"graph": True, "lit": True, "linking": "on"}
    assert f"commit:{snaps['sha']}" in out["names"]


def test_sans_catalogue_le_i_le_dit_au_lieu_de_rester_muet(tmp_path: Path, snaps: dict) -> None:
    out = _js(
        tmp_path,
        {**snaps, "explanations": {"schema_version": 1, "entries": {}}},
        """
$(`.explain-trigger[data-explain-for="${commitId}"]`).click();
await flush();
console.log(JSON.stringify({ title: $(".explain-title").textContent, body: $(".explain-body").textContent }));
""",
    )
    assert out["title"] == "Explication indisponible"
    assert "pas disponible" in out["body"]


def test_vue_masquee_la_puce_devient_lie_et_un_clic_reaffiche_avec_l_element_en_evidence(
    tmp_path: Path, snaps: dict
) -> None:
    out = _js(
        tmp_path,
        snaps,
        """
$('.pane[data-pane="remote"] [data-action="hide"]').click();
const chip = () => $('.chips [data-pane="remote"]');
const plain = chip().textContent;
over($$(`.graph-node[data-element-id="${commitId}"]`)[0]);
const hovered = chip().textContent;
ws.dispatchEvent(event("pointerleave", { bubbles: false }));
const unhovered = chip().textContent;
$$(`.graph-node[data-element-id="${commitId}"]`)[0].click();   // la sélection garde l'ancre
const selected = { text: chip().textContent, linked: chip().getAttribute("data-linked") };
chip().focus();
chip().click();
await flush();
console.log(JSON.stringify({ plain, hovered, unhovered, selected, shown: Boolean($('.pane[data-pane="remote"]')?.isConnected),
  revealed: $$(".is-revealed").map(idOf), chips: $$(".chips [data-pane]").length }));
""",
    )
    assert out["plain"] == "+ Distant + PR"
    assert out["hovered"] == "+ Distant + PR · lié"  # au survol, la puce l'annonce déjà
    assert out["unhovered"] == "+ Distant + PR"
    assert out["selected"] == {"text": "+ Distant + PR · lié", "linked": "true"}
    assert out["shown"] and out["chips"] == 0
    assert len(out["revealed"]) == 1 and out["revealed"][0] in {
        snaps["views"]["remote"]["branches"][0]["element_id"],
        "pr:1",
    }


def test_le_defilement_vers_le_correspondant_n_a_lieu_que_sur_clic(
    tmp_path: Path, snaps: dict
) -> None:
    out = _js(
        tmp_path,
        snaps,
        """
const scrolled = [];
for (const n of nodes()) n.scrollIntoView = () => scrolled.push(idOf(n));
const target = $$(`.graph-node[data-element-id="${commitId}"]`)[0];
over(target);
const onHover = scrolled.length;
target.click();
console.log(JSON.stringify({ onHover, onClick: scrolled.length, inRepo: scrolled.filter((id) => id === commitId).length }));
""",
    )
    assert out["onHover"] == 0 and out["onClick"] >= 1
    assert out["inRepo"] == 0  # la vue où l'on clique ne défile pas


def test_les_marques_de_lien_ne_gênent_pas_le_mode_designer() -> None:
    css = (CSS / "linking.css").read_text(encoding="utf-8")
    rules = re.findall(r"([^{}]+)\{[^{}]*\}", re.sub(r"/\*.*?\*/", "", css, flags=re.S))
    for selector in rules:
        for part in selector.split(","):
            if "is-linked" in part or "data-linking" in part:
                assert ":not(.is-designating)" in part or part.strip().startswith(".pane-chip"), (
                    part
                )
    # Jamais d'opacité (règle du dépôt) : les décors du graphe sont estompés par la couleur.
    assert "opacity" not in css.replace("dimmed-decor-opacity", "")


def test_un_terme_d_explication_ouvre_sa_definition_et_sa_barriere(
    tmp_path: Path, snaps: dict
) -> None:
    """Story 9.4 : `glossary-term` dans une explication, puis « Voir la barrière » sans carte."""
    out = _js(
        tmp_path,
        snaps,
        """
let term = null, trigger = null;
for (const candidate of $$(".explain-trigger")) {
  candidate.click();
  await flush();
  term = $('.explain-popover .glossary-term[data-term="quality-gate"]');
  if (term) { trigger = candidate; break; }
  press("Escape", { target: $(".explain-popover") });
}
const cls = term.className;
term.click();
await flush();
const popover = $(".explain-popover");
const see = popover.querySelector(".glossary-see");
const region = document.getElementById(see.getAttribute("aria-controls"));
const before = { title: popover.querySelector(".explain-title").textContent, expanded: see.getAttribute("aria-expanded"), live: region.getAttribute("aria-live"), detail: region.children.length };
see.click();
const after = { expanded: see.getAttribute("aria-expanded"), link: region.querySelector(".glossary-scenario-link").textContent };
press("Escape", { target: popover });
console.log(JSON.stringify({ cls, before, after, popovers: $$(".explain-popover").length, focusOnTrigger: document.activeElement === trigger }));
""",
    )
    assert out["cls"] == "glossary-term"
    assert out["before"] == {"title": "Quality gate", "expanded": "false", "live": "polite", "detail": 0}
    assert out["after"]["expanded"] == "true"
    assert out["after"]["link"].startswith("La voir jouer : scénario ")
    assert out["popovers"] == 0 and out["focusOnTrigger"] is True
