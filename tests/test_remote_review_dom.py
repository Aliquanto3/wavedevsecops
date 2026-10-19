# ruff: noqa: E501
"""« Demander une revue » de la vue « Distant + PR » (Story 7.5) sous Node, sur la doublure de DOM.

Les vues partent de vraies projections (fixture `snapshots` de `test_remote_dom.py`) ; le champ
`review.can_request` que projette le serveur est posé à la main pour les deux états du bouton.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from test_remote_dom import _js, snapshots  # noqa: F401 - la fixture sert à ce module
from test_shell_js import NODE

pytestmark = pytest.mark.skipif(NODE is None, reason="Node absent : comportement JS non exécuté")

WAITING_TEXT = "Le collègue relit une PR dont la CI passe : attendez que les checks soient verts."


def _request_snaps(snapshots: dict) -> dict:  # noqa: F811
    """La vue « blocked » où le collègue attend qu'on lui demande la revue : d'abord inactif
    (checks pas verts), puis actif."""
    waiting = json.loads(json.dumps(snapshots["blocked"]))
    review = waiting["remote"]["pulls"][0]["review"]
    review["can_request"] = True
    review["request_enabled"] = False
    review["request_disabled_text"] = WAITING_TEXT
    ready = json.loads(json.dumps(waiting))
    ready["remote"]["pulls"][0]["review"].update(request_enabled=True, request_disabled_text="")
    return {**snapshots, "waiting": waiting, "ready": ready}


def test_demander_une_revue_inactif_puis_actif(tmp_path: Path, snapshots: dict) -> None:  # noqa: F811
    out = _js(
        tmp_path,
        _request_snaps(snapshots),
        """
const button = () => $('[data-action="request-review"]');
load("blocked");
const absent = button() === null;
load("waiting");
const inactive = { label: button().textContent, disabled: button().getAttribute("aria-disabled"),
  reason: button().nextElementSibling.textContent };
button().dispatchEvent(makeEvent("click"));
await new Promise((r) => setTimeout(r, 0));
const blockedPosts = posts.length;
load("ready");
const active = { disabled: button().getAttribute("aria-disabled"), number: button().getAttribute("data-number") };
button().dispatchEvent(makeEvent("click"));
await new Promise((r) => setTimeout(r, 0));
console.log(JSON.stringify({ absent, inactive, blockedPosts, active, posts, problems: store.state.problems }));
""",
    )
    assert out["absent"] is True  # sans réaction en attente, aucun bouton
    assert out["inactive"] == {
        "label": "Demander une revue",
        "disabled": "true",
        "reason": WAITING_TEXT,
    }
    assert out["blockedPosts"] == 0
    assert out["active"]["disabled"] is None
    assert out["posts"] == [{"url": "/api/ws/w/pr_request_review", "body": {"number": 1}}]
    assert out["problems"] == []
