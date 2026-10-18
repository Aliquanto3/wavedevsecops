"""Disposition principale (Story 2.3) : contrôles statiques de la page et du registre des vues."""

from __future__ import annotations

import os

import pytest
from static_rules import STATIC
from test_shell_js import NODE

JS = STATIC / "js"
CSS = STATIC / "css"


def _read(path) -> str:
    return path.read_text(encoding="utf-8")


def test_feuille_de_style_de_la_disposition() -> None:
    """Le comportement (poignées, focus, Échap, F6) s'exécute dans `test_workspace_dom.py`."""
    css = _read(CSS / "workspace.css")
    assert "var(--scenario-panel-width)" in css and "@media (max-width: 640px)" in css
    assert "/static/css/workspace.css" in _read(STATIC / "index.html")


def test_node_present_en_ci() -> None:
    """En CI, Node est exigé : les tests du front ne doivent pas y être sautés en silence."""
    if os.environ.get("CI") and NODE is None:
        pytest.fail("Node est absent de la CI : les tests JS du front seraient sautés.")


def test_registre_des_volets_porte_les_vues_et_leurs_textes() -> None:
    views = _read(JS / "views.js")
    for text in (
        "Graphe des commits et index, comme `git log --all` et `git status`",
        "Refs de origin et PR du GitHub simulé",
        "Fichiers du bac à sable, diff et éditeur",
        "Vrai git, dans le bac à sable",
        "Aucun commit pour l'instant.",
        "Poussez une branche, puis ouvrez une PR.",
        "Sélectionnez un fichier, un commit ou une PR pour voir son contenu.",
    ):
        assert text in views, text
    assert "Préparation du bac à sable…" in _read(JS / "workspace.js")


def test_la_disposition_ne_nomme_aucune_vue() -> None:
    """Une vue ajoutée au registre ne touche ni la disposition ni sa logique (FR-32)."""
    for name in ("workspace.js", "layout.js", "store.js"):
        text = _read(JS / name)
        for view in ('"repo"', '"remote"', '"code"', '"terminal"'):
            assert view not in text, (name, view)
