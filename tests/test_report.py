"""Rapport de progression exportable (Story 6.5) : contenu, HTML autonome, CSV, routes."""

from __future__ import annotations

import csv
import http.client
import json
import re
from collections.abc import Iterator
from datetime import datetime
from pathlib import Path

import pytest

from wavedevsecops import cli
from wavedevsecops.config import Settings
from wavedevsecops.progress import FILENAME, write_json_atomic
from wavedevsecops.progress.facts import RESTART_KIND, Fact, ProgressStore
from wavedevsecops.progress.report import (
    EMPTY_TEXT,
    build_report,
    render_csv,
    render_html,
    resets_text,
)
from wavedevsecops.web.catalogue import report_font_css

NOW = datetime.fromisoformat("2026-10-19T14:03:00+02:00")


def fact(kind: str, step: str = "s1", scenario: str = "add-commit", track: str = "no_ai", **kw):
    return Fact(
        kind=kind,
        track=track,
        scenario_id=scenario,
        mode="A",
        step_id=step,
        workspace_id=f"{track}.{scenario}.A",
        epoch=0,
        op_id=f"{kind}-{step}",
        at="2026-10-19T10:30:00+02:00",
        **kw,
    )


def base(data: Path) -> None:
    write_json_atomic(
        data / FILENAME,
        {
            "schema_version": 1,
            "installed_at": "2026-10-01T09:00:00+02:00",
            "first_launch_at": "2026-10-02T08:15:00+02:00",
            "facts": [],
        },
    )


def fill(data: Path) -> None:
    base(data)
    ProgressStore.for_dir(data).submit(
        [
            fact("quiz_first_attempt", "q1", correct=True),
            fact("quiz_first_attempt", "q2", correct=False),
            fact("hint_opened", "q2", tier=1),
            fact("scenario_completed", ""),
            fact("step_validated", "s1", scenario="branche", track="llm"),
        ]
    )
    # Le fait « remise à zéro » appartient à la story 4.4 : le rapport le compte déjà.
    path = data / FILENAME
    stored = json.loads(path.read_text(encoding="utf-8"))
    for n in range(2):
        stored["facts"].append(
            {**stored["facts"][0], "kind": RESTART_KIND, "op_id": f"r{n}", "step_id": ""}
        )
    write_json_atomic(path, stored)


def test_rapport_par_parcours_scores_indices_remises_et_dates(tmp_path: Path) -> None:
    fill(tmp_path)
    report = build_report(
        tmp_path,
        titles={"add-commit": "Add et commit"},
        tracks={"no_ai": "Parcours sans IA", "llm": "Parcours LLM"},
        now=NOW,
    )
    assert [t["track"] for t in report["tracks"]] == ["llm", "no_ai"]
    (row,) = [t for t in report["tracks"] if t["track"] == "no_ai"][0]["rows"]
    assert row["title"] == "Add et commit"
    assert row["state_text"] == "Terminé"
    assert row["score_text"] == "1 sur 2 du premier coup"
    assert row["hints_text"] == "1 indice"
    assert row["resets"] == 2 and row["resets_text"] == "2 remises à zéro"
    assert row["completed_text"] == "19/10/2026 10:30"
    assert report["installed_text"] == "01/10/2026 09:00"
    assert report["first_launch_text"] == "02/10/2026 08:15"
    assert report["empty"] is False


def test_sans_progression_seulement_les_dates(tmp_path: Path) -> None:
    base(tmp_path)
    report = build_report(tmp_path, now=NOW)
    assert report["empty"] is True and report["empty_text"] == EMPTY_TEXT
    assert report["tracks"] == []
    assert report["installed_text"] == "01/10/2026 09:00"


def test_aucun_fichier_rien_n_est_cree(tmp_path: Path) -> None:
    report = build_report(tmp_path, now=NOW)
    assert report["empty"] is True
    assert report["installed_text"] == "Non renseigné"
    assert not (tmp_path / FILENAME).exists()


def test_une_seule_remise_au_singulier() -> None:
    assert [resets_text(n) for n in (0, 1, 2)] == [
        "0 remise à zéro",
        "1 remise à zéro",
        "2 remises à zéro",
    ]


def test_html_autonome_sans_ressource_externe_et_echappe(tmp_path: Path) -> None:
    fill(tmp_path)
    report = build_report(tmp_path, titles={"add-commit": "<b>Add</b> & commit"}, now=NOW)
    html = render_html(report, report_font_css())
    assert "Rien n&#39;est envoyé : vous choisissez à qui transmettre le fichier." in html
    assert "&lt;b&gt;Add&lt;/b&gt; &amp; commit" in html and "<b>Add</b>" not in html
    assert "@font-face" in html and "data:font/woff2;base64," in html
    assert not re.findall(r"""(?:src|href)\s*=\s*["'](?!#)""", html)
    assert not re.findall(r"url\((?!\s*[\"']?data:)", html)
    assert "http://" not in html and "https://" not in html
    assert "@media print" in html


def test_csv_utf8_bom_point_virgule_et_accents(tmp_path: Path) -> None:
    fill(tmp_path)
    report = build_report(tmp_path, titles={"add-commit": "=Étape; « un »"}, now=NOW)
    raw = render_csv(report)
    assert raw.startswith(b"\xef\xbb\xbf")
    text = raw.decode("utf-8-sig")
    assert "Premier lancement;02/10/2026 08:15" in text
    assert text.count("\r\n") == len(text.splitlines())
    line = next(x for x in text.splitlines() if "Étape" in x)
    cells = next(csv.reader([line], delimiter=";"))
    assert cells[1].startswith("'=")  # formule neutralisée
    assert cells[3] == "Terminé" and cells[7] == "2"


FORMULAS = ("=HYPERLINK(\"x\")", "=cmd|' /C calc'!A0", "+1", "-1", "@SUM(A1)", "\tx")


@pytest.mark.parametrize("payload", FORMULAS)
@pytest.mark.parametrize(
    "column",
    [
        "label",
        "title",
        "mode",
        "state_text",
        "quiz_correct",
        "quiz_total",
        "hints",
        "resets",
        "completed_text",
    ],
)
def test_csv_chaque_colonne_neutralisee(column: str, payload: str) -> None:
    row = {
        "title": "t", "mode": "A", "state_text": "Terminé", "quiz_correct": 1, "quiz_total": 2,
        "hints": 0, "resets": 0, "completed_text": "",
    }
    track = {"label": "Parcours"}
    (track if column == "label" else row)[column] = payload
    report = {"installed_text": "x", "first_launch_text": "y", "tracks": [{**track, "rows": [row]}]}
    text = render_csv(report).decode("utf-8-sig")
    *_, line = list(csv.reader(text.splitlines(), delimiter=";"))
    assert any(cell == "'" + payload for cell in line), line
    assert not any(cell[:1] in "=+-@\t" for cell in line if cell)


@pytest.mark.parametrize("key", ["installed_at", "first_launch_at"])
def test_csv_dates_brutes_neutralisees(tmp_path: Path, key: str) -> None:
    base(tmp_path)
    path = tmp_path / FILENAME
    stored = json.loads(path.read_text(encoding="utf-8"))
    write_json_atomic(path, {**stored, key: "=HYPERLINK(\"http://x\")"})
    text = render_csv(build_report(tmp_path, now=NOW)).decode("utf-8-sig")
    rows = list(csv.reader(text.splitlines()[:2], delimiter=";"))
    assert "'=HYPERLINK(\"http://x\")" in [cell for r in rows for cell in r]


def test_remise_seule_ne_commence_pas_le_scenario(tmp_path: Path) -> None:
    base(tmp_path)
    path = tmp_path / FILENAME
    stored = json.loads(path.read_text(encoding="utf-8"))
    raw = fact("step_validated").model_dump(mode="json", exclude_none=True)
    stored["facts"].append({**raw, "kind": RESTART_KIND, "op_id": "r0", "step_id": ""})
    write_json_atomic(path, stored)
    (track,) = build_report(tmp_path, now=NOW)["tracks"]
    (row,) = track["rows"]
    assert row["state"] == "todo" and row["state_text"] == "À faire"
    assert row["resets"] == 1 and row["hints"] == 0 and row["quiz_total"] == 0


@pytest.fixture
def instance(tmp_path: Path, git_path: Path) -> Iterator[cli.Instance]:
    fill(tmp_path / "data")
    inst = cli.start_instance(Settings(data_dir=tmp_path / "data"))
    try:
        yield inst
    finally:
        inst.stop()


@pytest.fixture
def cookie(instance: cli.Instance) -> dict[str, str]:
    conn = http.client.HTTPConnection(cli.HOST, instance.port, timeout=10)
    conn.request("GET", f"/?t={instance.token}")
    resp = conn.getresponse()
    resp.read()
    conn.close()
    return {"Cookie": resp.getheader("Set-Cookie", "").split(";")[0]}


def get(inst: cli.Instance, path: str, cookie: dict):
    conn = http.client.HTTPConnection(cli.HOST, inst.port, timeout=30)
    conn.request("GET", path, headers=cookie)
    resp = conn.getresponse()
    raw = resp.read()
    headers = {k.lower(): v for k, v in resp.getheaders()}
    conn.close()
    return resp.status, headers, raw


def test_routes_du_rapport_derriere_le_cookie(instance: cli.Instance) -> None:
    assert get(instance, "/api/report", {})[0] == 401
    assert get(instance, "/api/report/export?format=csv", {})[0] == 401


def test_apercu_et_exports_servis(instance: cli.Instance, cookie: dict) -> None:
    status, _, raw = get(instance, "/api/report", cookie)
    body = json.loads(raw)
    assert status == 200 and body["empty"] is False
    assert {t["track"] for t in body["tracks"]} == {"llm", "no_ai"}
    status, headers, raw = get(instance, "/api/report/export?format=csv", cookie)
    assert status == 200 and raw.startswith(b"\xef\xbb\xbf")
    assert headers["content-type"].startswith("text/csv")
    assert 'filename="rapport-wavedevsecops.csv"' in headers["content-disposition"]
    status, headers, raw = get(instance, "/api/report/export?format=html", cookie)
    assert status == 200 and raw.decode("utf-8").startswith("<!doctype html>")
    assert "attachment" in headers["content-disposition"]
    status, _, raw = get(instance, "/api/report/export?format=pdf", cookie)
    assert status == 422 and "reason_text" in json.loads(raw)


def test_progression_illisible_dit_la_cause(tmp_path: Path, instance: cli.Instance, cookie: dict):
    (tmp_path / "data" / FILENAME).write_text("{pas du json", encoding="utf-8")
    status, _, raw = get(instance, "/api/report", cookie)
    assert status == 500 and "illisible" in json.loads(raw)["reason_text"]
