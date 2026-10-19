# ruff: noqa: E501
"""Export du rapport (Story 6.5) sous Node, sur la doublure de DOM : pied du catalogue,
`report-preview`, deux exports, échec d'enregistrement avec « Réessayer »."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from test_shell_js import NODE, _run
from test_workspace_dom import MINIDOM

pytestmark = pytest.mark.skipif(NODE is None, reason="Node absent : comportement JS non exécuté")

REPORT = {
    "privacy_text": "Rien n'est envoyé : vous choisissez à qui transmettre le fichier.",
    "empty": False,
    "empty_text": "Aucun scénario terminé pour l'instant. Le rapport contiendra seulement les dates d'installation et de premier lancement.",
    "installed_text": "01/10/2026 09:00",
    "first_launch_text": "02/10/2026 08:15",
    "tracks": [
        {
            "track": "no_ai",
            "label": "Parcours sans IA",
            "rows": [
                {
                    "scenario_id": "add-commit", "title": "Add et commit", "mode": "A",
                    "state_text": "Terminé", "score_text": "1 sur 2 du premier coup",
                    "hints_text": "1 indice", "resets_text": "2 remises à zéro",
                    "completed_text": "19/10/2026 10:30",
                }
            ],
        }
    ],
}

PRELUDE = f"""
import {{ installDom, makeEvent }} from "{MINIDOM}";
const {{ document, main }} = installDom();
const {{ renderReportEntry, renderPreview, exportReport, failureText, saveBlob }} = await import("@JS@/report.js");
const $ = (s) => document.querySelector(s);
const $$ = (s) => [...document.querySelectorAll(s)];
const REPORT = {json.dumps(REPORT)};
const tick = () => new Promise((r) => setTimeout(r, 0));
const okResponse = (body) => ({{ ok: true, status: 200, json: async () => body }});
"""


def _js(tmp_path: Path, body: str) -> dict:
    return json.loads(_run(tmp_path, f"{PRELUDE}\n{body}"))


def test_pied_du_catalogue_et_apercu(tmp_path: Path) -> None:
    out = _js(
        tmp_path,
        """
const fetchImpl = async () => okResponse(REPORT);
renderReportEntry(main, { fetchImpl });
const before = { button: $(".report-entry button").textContent, privacy: $(".report-entry .report-privacy").textContent, preview: !!$(".report-preview") };
$(".report-entry button").dispatchEvent(makeEvent("click"));
await tick(); await tick();
console.log(JSON.stringify({
  before,
  rows: $$(".report-row").map((r) => r.textContent),
  buttons: $$(".report-actions button").map((b) => b.textContent),
  heading: $(".report-track-title").textContent,
  empty: !!$(".report-empty"),
}));
""",
    )
    assert out["before"] == {
        "button": "Exporter mon rapport",
        "privacy": REPORT["privacy_text"],
        "preview": False,
    }
    assert out["rows"][:2] == [
        "Installation : 01/10/2026 09:00",
        "Premier lancement : 02/10/2026 08:15",
    ]
    assert out["rows"][2] == (
        "Add et commit (mode A) · Terminé · 1 sur 2 du premier coup · 1 indice · 2 remises à zéro · terminé le 19/10/2026 10:30"
    )
    assert out["buttons"] == ["Exporter en HTML", "Exporter en CSV"]
    assert out["heading"] == "Parcours sans IA" and out["empty"] is False


def test_sans_progression_le_texte_vide(tmp_path: Path) -> None:
    out = _js(
        tmp_path,
        """
renderPreview(main, { ...REPORT, empty: true, tracks: [] });
console.log(JSON.stringify({ empty: $(".report-empty").textContent, rows: $$(".report-rows li").length }));
""",
    )
    assert out["empty"] == REPORT["empty_text"] and out["rows"] == 0


def test_export_demande_le_format_et_enregistre(tmp_path: Path) -> None:
    out = _js(
        tmp_path,
        """
const calls = []; const saved = [];
const fetchImpl = async (url) => { calls.push(url); return { ok: true, status: 200, headers: { get: () => 'attachment; filename="rapport-wavedevsecops.csv"' }, blob: async () => "BLOB" }; };
renderPreview(main, REPORT, { fetchImpl, save: async (blob, name) => { saved.push([blob, name]); return true; } });
$$(".report-actions button")[1].dispatchEvent(makeEvent("click"));
await tick(); await tick();
console.log(JSON.stringify({ calls, saved, notice: $$(".notice-card").length }));
""",
    )
    assert out["calls"] == ["/api/report/export?format=csv"]
    assert out["saved"] == [["BLOB", "rapport-wavedevsecops.csv"]]
    assert out["notice"] == 0


def test_echec_d_ecriture_notice_et_reessayer(tmp_path: Path) -> None:
    out = _js(
        tmp_path,
        """
let attempts = 0;
const fetchImpl = async () => ({ ok: true, status: 200, headers: { get: () => null }, blob: async () => "B" });
const save = async () => { attempts += 1; if (attempts === 1) throw new Error("Accès refusé"); return true; };
renderPreview(main, REPORT, { fetchImpl, save });
$$(".report-actions button")[0].dispatchEvent(makeEvent("click"));
await tick(); await tick();
const first = { text: $(".notice-card p").textContent, role: $(".notice-card").getAttribute("role"), retry: $(".notice-card button").textContent };
$(".notice-card button").dispatchEvent(makeEvent("click"));
await tick(); await tick();
console.log(JSON.stringify({ first, attempts, notice: $$(".notice-card").length, plain: failureText("Disque plein.") }));
""",
    )
    assert out["first"] == {
        "text": "Le fichier n'a pas pu être enregistré : Accès refusé.",
        "role": "alert",
        "retry": "Réessayer",
    }
    assert out["attempts"] == 2 and out["notice"] == 0
    assert out["plain"] == "Le fichier n'a pas pu être enregistré : Disque plein."


def test_refus_du_serveur_devient_la_cause(tmp_path: Path) -> None:
    out = _js(
        tmp_path,
        """
const fetchImpl = async () => ({ ok: false, status: 500, json: async () => ({ reason_text: "Le fichier progress.json est illisible." }) });
let error = "";
try { await exportReport("html", { fetchImpl, save: async () => true }); } catch (err) { error = err.message; }
console.log(JSON.stringify({ error }));
""",
    )
    assert out["error"] == "Le fichier progress.json est illisible."


def test_ouverture_met_le_focus_sur_l_apercu(tmp_path: Path) -> None:
    out = _js(
        tmp_path,
        """
renderReportEntry(main, { fetchImpl: async () => okResponse(REPORT) });
$(".report-entry button").dispatchEvent(makeEvent("click"));
await tick(); await tick();
console.log(JSON.stringify({ focused: document.activeElement.className }));
""",
    )
    assert out["focused"] == "report-title"


def test_ecriture_echouee_abandonne_le_flux(tmp_path: Path) -> None:
    out = _js(
        tmp_path,
        """
const log = [];
const writable = { write: async () => { throw new Error("Disque plein"); }, close: async () => log.push("close"), abort: async () => log.push("abort") };
const win = { showSaveFilePicker: async () => ({ createWritable: async () => writable }) };
let error = "";
try { await saveBlob("B", "r.html", { win }); } catch (err) { error = err.message; }
console.log(JSON.stringify({ log, error }));
""",
    )
    assert out == {"log": ["abort"], "error": "Disque plein"}
