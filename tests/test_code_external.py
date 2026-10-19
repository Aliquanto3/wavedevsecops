# ruff: noqa: E501
"""Story 2.9 sous Node : `external-change-notice` et choix « Garder ma version » / « Recharger »
quand le disque change sous un fichier ouvert (modification faite hors de l'application)."""

from __future__ import annotations

from pathlib import Path

import pytest
from test_code_dom import _js, diffs  # noqa: F401 - `diffs` est une fixture réutilisée
from test_shell_js import NODE

pytestmark = pytest.mark.skipif(NODE is None, reason="Node absent : comportement JS non exécuté")

EVENTS = """
const evt = (n, kind, op, payload) => ({ boot_id: "b", seq: 100 + n, kind, epoch: 0, op_id: op, payload });
store.applyEvent(evt(1, "external_change", "op2", { fingerprint: "y" }));
store.applyEvent(evt(2, "state_projected", "op2", { views: { a: 1 }, fingerprint: "z" }));
await flush();
"""


def test_notice_et_rechargement_d_un_fichier_propre(tmp_path: Path, diffs: Path) -> None:  # noqa: F811
    out = _js(
        tmp_path,
        diffs,
        f"""
$$(".code-file")[0].click();
await flush();
const before = {{ hidden: $(".external-change-notice").hidden, role: $(".external-change-notice").getAttribute("role") }};
disk.set("a.txt", "écrit dans mon éditeur\\n");
{EVENTS}
console.log(JSON.stringify({{ before, hidden: $(".external-change-notice").hidden, text: $(".external-change-notice").textContent, value: $(".editor-area").value, conflict: $(".code-conflict").hidden }}));
""",
    )
    assert out["before"] == {"hidden": True, "role": "status"}
    assert out["hidden"] is False and out["text"] == "Modifié hors de l'application"
    assert out["value"] == "écrit dans mon éditeur\n" and out["conflict"] is True


def test_fichier_non_enregistre_propose_le_choix(tmp_path: Path, diffs: Path) -> None:  # noqa: F811
    out = _js(
        tmp_path,
        diffs,
        f"""
$$(".code-file")[0].click();
await flush();
type("ma version\\n");
disk.set("a.txt", "version du disque\\n");
{EVENTS}
const bar = {{ hidden: $(".code-conflict").hidden, text: $(".code-conflict-text").textContent, buttons: $$(".code-conflict button").map((b) => b.textContent), mine: $(".editor-area").value }};
$(".code-reload").click();
await flush();
console.log(JSON.stringify({{ bar, after: $(".editor-area").value, hidden: $(".code-conflict").hidden, saves: calls.filter((c) => c.path === "save_file").length }}));
""",
    )
    assert out["bar"] == {
        "hidden": False,
        "text": "Le fichier a changé sur le disque.",
        "buttons": ["Garder ma version", "Recharger"],
        "mine": "ma version\n",
    }
    assert out["after"] == "version du disque\n" and out["hidden"] is True and out["saves"] == 0


def test_conflit_efface_quand_le_tampon_redevient_propre(tmp_path: Path, diffs: Path) -> None:  # noqa: F811
    """Revue : un conflit resté posé sur un tampon redevenu propre ferait « Recharger » une
    version du disque plus ancienne que celle affichée."""
    out = _js(
        tmp_path,
        diffs,
        f"""
$$(".code-file")[0].click();
await flush();
const orig = $(".editor-area").value;
type("ma version\\n");
disk.set("a.txt", "version du disque\\n");
{EVENTS}
const shown = $(".code-conflict").hidden;
type(orig);
disk.set("a.txt", "troisième version\\n");
store.applyEvent(evt(3, "external_change", "op3", {{ fingerprint: "w" }}));
store.applyEvent(evt(4, "state_projected", "op3", {{ views: {{ a: 2 }}, fingerprint: "v" }}));
await flush();
console.log(JSON.stringify({{ shown, value: $(".editor-area").value, hidden: $(".code-conflict").hidden }}));
""",
    )
    assert out == {"shown": False, "value": "troisième version\n", "hidden": True}


def test_notice_masquee_au_changement_d_espace(tmp_path: Path, diffs: Path) -> None:  # noqa: F811
    out = _js(
        tmp_path,
        diffs,
        f"""
{EVENTS}
const shown = $(".external-change-notice").hidden;
store.reset("w2");
await flush();
console.log(JSON.stringify({{ shown, hidden: $(".external-change-notice").hidden }}));
""",
    )
    assert out == {"shown": False, "hidden": True}


def test_notice_effacee_a_l_enregistrement(tmp_path: Path, diffs: Path) -> None:  # noqa: F811
    """Arbitrage 2.9 : la notice « Modifié hors de l'application » s'efface quand l'apprenant
    enregistre le fichier, sans attendre la commande suivante."""
    out = _js(
        tmp_path,
        diffs,
        f"""
$$(".code-file")[0].click();
await flush();
disk.set("a.txt", "écrit dans mon éditeur\\n");
{EVENTS}
const shown = $(".external-change-notice").hidden;
type("ma version\\n");
$(".code-save").click();
await flush();
console.log(JSON.stringify({{ shown, hidden: $(".external-change-notice").hidden, saved: disk.get("a.txt") }}));
""",
    )
    assert out == {"shown": False, "hidden": True, "saved": "ma version\n"}
