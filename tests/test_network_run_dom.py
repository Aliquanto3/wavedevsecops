# ruff: noqa: E501
"""Bouton « Exécuter le code (réseau possible) » (Story 6.6, UX-DR23), sous Node sur `minidom`."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from test_shell_js import NODE, _run
from test_workspace_dom import PRELUDE

pytestmark = pytest.mark.skipif(NODE is None, reason="Node absent : comportement JS non exécuté")

NETWORK_PRELUDE = """
const sent = [];
let reply = { ok: true, json: async () => ({}) };
const fetchImpl = async (url, init) => { sent.push({ url, init }); return reply; };
const mountLlm = (track = "llm") => {
  main.replaceChildren();
  store.reset("llm.bac-a-sable-libre.A");
  store.applySnapshot({ workspace_id: "llm.bac-a-sable-libre.A", boot_id: "b", seq: 1, epoch: 0,
    state: "idle", reason_text: "", fingerprint: "", views: {} });
  return mountWorkspace(main, { title: "T", store, storage, track, fetchImpl });
};
const button = () => $("#network-run-button");
const confirmBox = () => $(".network-run-confirm");
"""


def _js(tmp_path: Path, body: str) -> dict:
    script = f"globalThis.__width = 1920;\n{PRELUDE}\n{NETWORK_PRELUDE}\n{body}"
    return json.loads(_run(tmp_path, script))


def test_bouton_et_confirmation_en_ligne(tmp_path: Path) -> None:
    out = _js(
        tmp_path,
        """
mountLlm();
const label = button().textContent;
const hiddenAtStart = confirmBox().hidden;
button().click();
const opened = { hidden: confirmBox().hidden, expanded: button().getAttribute("aria-expanded"),
  text: $(".network-run-question").textContent, sentBefore: sent.length };
button().click(); // referme
const closedAgain = confirmBox().hidden;
button().click();
$('[data-action="network-run-cancel"]').click();
const afterCancel = { hidden: confirmBox().hidden, sent: sent.length, focus: document.activeElement === button() };
button().click();
press("Escape"); // le focus est sur « Annuler », dans la confirmation
const afterEscape = { hidden: confirmBox().hidden, sent: sent.length };
console.log(JSON.stringify({ label, hiddenAtStart, opened, closedAgain, afterCancel, afterEscape }));
""",
    )
    assert out["label"] == "Exécuter le code (réseau possible)"
    assert out["hiddenAtStart"] is True
    assert out["opened"]["hidden"] is False and out["opened"]["expanded"] == "true"
    assert out["opened"]["text"] == "Ce code peut appeler un service en ligne. Continuer ?"
    assert out["opened"]["sentBefore"] == 0  # aucun envoi avant l'acceptation
    assert out["closedAgain"] is True
    assert out["afterCancel"] == {"hidden": True, "sent": 0, "focus": True}
    assert out["afterEscape"] == {"hidden": True, "sent": 0}


def test_acceptation_envoie_l_intention_confirmee(tmp_path: Path) -> None:
    out = _js(
        tmp_path,
        """
mountLlm();
button().click();
$('[data-action="network-run-accept"]').click();
await new Promise((r) => setTimeout(r, 0));
const first = sent.map((s) => ({ url: s.url, method: s.init.method, body: s.init.body,
  credentials: s.init.credentials }));
const hidden = confirmBox().hidden;
reply = { ok: false, json: async () => ({ reason_text: "Une commande est en cours." }) };
button().click();
$('[data-action="network-run-accept"]').click();
await new Promise((r) => setTimeout(r, 0));
console.log(JSON.stringify({ first, hidden, error: $(".scenario-error").textContent }));
""",
    )
    assert out["first"] == [
        {
            "url": "/api/ws/llm.bac-a-sable-libre.A/run_exercise_code",
            "method": "POST",
            "body": '{"confirmed":true}',
            "credentials": "same-origin",
        }
    ]
    assert out["hidden"] is True
    assert out["error"] == "Une commande est en cours."


def test_inactif_pendant_une_operation_et_absent_hors_parcours_llm(tmp_path: Path) -> None:
    out = _js(
        tmp_path,
        """
mountLlm();
store.applyEvent({ kind: "engine_state", boot_id: "b", seq: 2, payload: { state: "command",
  reason_text: "Une commande est en cours." } });
const busy = { disabled: button().getAttribute("aria-disabled"),
  reason: $(".network-run .btn-reason").textContent };
button().click();
const stayed = confirmBox().hidden;
store.applyEvent({ kind: "engine_state", boot_id: "b", seq: 3, payload: { state: "idle", reason_text: "" } });
const idle = button().getAttribute("aria-disabled");
mountLlm("no_ai");
console.log(JSON.stringify({ busy, stayed, idle, other: $("#network-run-button") === null }));
""",
    )
    assert out["busy"] == {"disabled": "true", "reason": "Une commande est en cours."}
    assert out["stayed"] is True
    assert out["idle"] is None
    assert out["other"] is True
