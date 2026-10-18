"""Page Diagnostic côté front : découpe des commandes en code, pastille, icônes (Node requis)."""

from __future__ import annotations

from pathlib import Path

import pytest
from test_shell_js import JS, NODE, _run

pytestmark = pytest.mark.skipif(NODE is None, reason="Node absent : comportement JS non exécuté")


def test_commandes_en_code_et_icones(tmp_path: Path) -> None:
    out = _run(
        tmp_path,
        """
import { splitCode, ICONS } from "@JS@/diagnostic.js";
const parts = splitCode("Lancez `uv sync` puis `uv run x`, merci.");
console.log(JSON.stringify(parts.map((p) => [p.text, p.code])));
console.log(JSON.stringify(splitCode("sans code")));
console.log(ICONS.ok + ICONS.too_old + ICONS.missing);
""",
    )
    lines = out.splitlines()
    assert lines[0] == (
        '[["Lancez ",false],["uv sync",true],[" puis ",false],["uv run x",true],[", merci.",false]]'
    )
    assert lines[1] == '[{"text":"sans code","code":false}]'
    assert lines[2] == "✓⚠✗"


def test_pastille_decompte_et_nom_du_lien(tmp_path: Path) -> None:
    out = _run(
        tmp_path,
        """
import { renderBadge } from "@JS@/diagnostic.js";
globalThis.document = { createElement: () => {
  const el = { attrs: {}, children: [], className: "", textContent: "",
    setAttribute(k, v) { this.attrs[k] = v; }, append(c) { this.children.push(c); },
    remove() { link.children = link.children.filter((c) => c !== this); } };
  return el;
} };
const link = { attrs: {}, children: [],
  setAttribute(k, v) { this.attrs[k] = v; },
  removeAttribute(k) { delete this.attrs[k]; },
  append(c) { this.children.push(c); },
  querySelector() { return this.children[0] || null; } };
renderBadge(link, { badge_text: "Diagnostic, 2 outils absents ou trop anciens", problem_count: 2 });
console.log(link.attrs["aria-label"], link.children.length, link.children[0].textContent);
renderBadge(link, { badge_text: "", problem_count: 0 });
console.log(link.children.length, "aria-label" in link.attrs);
""",
    )
    assert out.splitlines() == [
        "Diagnostic, 2 outils absents ou trop anciens 1 2",
        "0 false",
    ]


def test_le_front_ne_calcule_rien_et_n_injecte_pas_de_html() -> None:
    source = (JS / "diagnostic.js").read_text(encoding="utf-8")
    assert "innerHTML" not in source and "insertAdjacentHTML" not in source
