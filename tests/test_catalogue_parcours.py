"""Choix du parcours et catalogue ordonné (Story 6.1) : ordre, états, outils absents."""

from __future__ import annotations

import http.client
import json
from collections.abc import Iterator
from pathlib import Path

import pytest

from wavedevsecops import cli, toolrun
from wavedevsecops.config import Settings
from wavedevsecops.progress.facts import Fact, ProgressStore, ScenarioProgress
from wavedevsecops.web.catalogue import PICKER_QUESTION, catalogue_body, detail_text

TEMPLATE = """\
schema_version: 1
scenario_id: {sid}
mode: {mode}
title_text: {title}
station: 1
tracks: {tracks}
tools: {tools}
template: empty
steps: []
"""

SCENARIOS = [
    # Déclarés dans le désordre : le catalogue suit l'ordre conseillé de FR-9.
    ("pr-merge", "A", "PR et merge", "[llm, no_ai]", "[git]"),
    ("add-commit", "A", "Add et commit", "[llm, no_ai]", "[git]"),
    ("add-commit", "B", "Add et commit", "[llm]", "[git]"),
    ("branche", "A", "Branche", "[llm, no_ai]", "[git, gitleaks]"),
    ("hors-liste", "A", "Hors liste", "[no_ai]", "[git]"),
]


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    content = tmp_path / "content"
    (content / "scenarios").mkdir(parents=True)
    for sid, mode, title, tracks, tools in SCENARIOS:
        text = TEMPLATE.format(sid=sid, mode=mode, title=title, tracks=tracks, tools=tools)
        (content / "scenarios" / f"{sid}.{mode}.yaml").write_text(text, encoding="utf-8")
    return Settings(data_dir=tmp_path / "data", content_dir=content)


@pytest.fixture
def gitleaks_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    real = toolrun.resolve

    def fake(tool_id, *args, **kwargs):
        if tool_id == "gitleaks":
            return toolrun.ToolStatus("gitleaks", "missing", reason="absent")
        return real(tool_id, *args, **kwargs)

    monkeypatch.setattr(toolrun, "resolve", fake)


def fact(kind: str, track: str, sid: str, step: str = "s1", **extra) -> Fact:
    return Fact(
        kind=kind,
        track=track,
        scenario_id=sid,
        mode="A",
        step_id=step,
        workspace_id=f"{track}.{sid}.A",
        epoch=0,
        op_id=f"{kind}-{step}",
        **extra,
    )


def test_premier_passage_n_affiche_que_le_choix_du_parcours(settings: Settings) -> None:
    body = catalogue_body(settings)
    assert body["track"] is None and body["sections"] == []
    assert body["picker"]["question"] == PICKER_QUESTION
    assert [t["key"] for t in body["tracks"]] == ["llm", "no_ai"]
    assert all(t["label"] and t["text"] for t in body["tracks"])


def test_ordre_conseille_numeros_et_colonnes_de_mode(settings: Settings) -> None:
    body = catalogue_body(settings, "llm")
    (section,) = body["sections"]
    assert section["title"] == "Socle git"
    scenarios = section["scenarios"]
    assert [s["scenario_id"] for s in scenarios] == ["add-commit", "branche", "pr-merge"]
    assert [s["number"] for s in scenarios] == [1, 2, 3]
    assert [m["mode"] for m in scenarios[0]["modes"]] == ["A", "B"]
    assert scenarios[0]["modes"][1]["workspace_id"] == "llm.add-commit.B"
    # Un scénario qui n'existe pas dans le parcours choisi est absent (le mode B est LLM seul).
    no_ai = catalogue_body(settings, "no_ai")["sections"][0]["scenarios"]
    assert [s["scenario_id"] for s in no_ai] == ["add-commit", "branche", "pr-merge", "hors-liste"]
    assert [m["mode"] for m in no_ai[0]["modes"]] == ["A"]
    assert no_ai[0]["modes"][0]["workspace_id"] == "no_ai.add-commit.A"


def test_etats_et_scores_sont_ceux_du_parcours_choisi(settings: Settings) -> None:
    store = ProgressStore.for_dir(settings.resolved_data_dir())
    store.submit(
        [
            fact("step_validated", "llm", "add-commit"),
            fact("quiz_first_attempt", "llm", "add-commit", step="q1", correct=True),
            fact("quiz_first_attempt", "llm", "add-commit", step="q2", correct=False),
            fact("hint_opened", "llm", "add-commit", tier=1),
            fact("hint_opened", "llm", "add-commit", tier=2),
            fact("scenario_completed", "llm", "pr-merge", step=""),
            fact("step_validated", "no_ai", "branche"),
        ]
    )
    llm = {
        s["scenario_id"]: s["modes"][0]
        for s in catalogue_body(settings, "llm")["sections"][0]["scenarios"]
    }
    assert (llm["add-commit"]["state"], llm["add-commit"]["state_text"]) == (
        "in_progress",
        "En cours",
    )
    assert llm["add-commit"]["detail_text"] == "1 sur 2 du premier coup · 2 indices"
    assert (llm["pr-merge"]["state_text"], llm["pr-merge"]["detail_text"]) == (
        "Terminé",
        "0 indice",
    )
    assert (llm["branche"]["state_text"], llm["branche"]["detail_text"]) == ("À faire", "")
    # Chaque parcours garde sa progression : rien de tout cela dans le parcours sans IA.
    no_ai = {
        s["scenario_id"]: s["modes"][0]
        for s in catalogue_body(settings, "no_ai")["sections"][0]["scenarios"]
    }
    assert no_ai["add-commit"]["state_text"] == "À faire"
    assert no_ai["branche"]["state_text"] == "En cours"


def test_texte_de_detail() -> None:
    assert detail_text(ScenarioProgress()) == ""
    assert detail_text(ScenarioProgress(state="in_progress", hints=1)) == "1 indice"
    one = ScenarioProgress(state="done", quiz_total=4, quiz_correct=3, hints=0)
    assert detail_text(one) == "3 sur 4 du premier coup · 0 indice"


def test_outil_absent_rend_la_carte_indisponible(
    settings: Settings, gitleaks_missing: None
) -> None:
    cards = {
        s["scenario_id"]: s for s in catalogue_body(settings, "llm")["sections"][0]["scenarios"]
    }
    ok = cards["add-commit"]["modes"][0]
    assert ok["available"] is True and "unavailable" not in ok
    off = cards["branche"]["modes"][0]
    assert off["available"] is False
    assert off["unavailable"]["text"] == "⊘ Indisponible"
    assert off["unavailable"]["needs_text"] == "Nécessite gitleaks"
    assert off["unavailable"]["diagnostic_text"] == "Voir le diagnostic"
    assert off["unavailable"]["diagnostic_path"] == "/diagnostic"


@pytest.fixture
def instance(settings: Settings, git_path: Path) -> Iterator[cli.Instance]:
    inst = cli.start_instance(settings)
    try:
        yield inst
    finally:
        inst.stop()


def _call(inst: cli.Instance, method: str, path: str, body: object = None):
    conn = http.client.HTTPConnection(cli.HOST, inst.port, timeout=60)
    conn.request("GET", f"/?t={inst.token}")
    first = conn.getresponse()
    first.read()
    headers = {"Cookie": first.getheader("Set-Cookie", "").split(";")[0]}
    data = None
    if method == "POST":
        headers["Origin"] = f"http://{cli.HOST}:{inst.port}"
        headers["Content-Type"] = "application/json"
        data = json.dumps(body).encode("utf-8")
    conn.request(method, path, body=data, headers=headers)
    resp = conn.getresponse()
    raw = resp.read()
    conn.close()
    return resp.status, json.loads(raw)


def test_api_choix_du_parcours_et_refus(instance: cli.Instance, gitleaks_missing: None) -> None:
    status, body = _call(instance, "GET", "/api/catalogue")
    assert status == 200 and body["sections"] == [] and body["track"] is None
    status, body = _call(instance, "GET", "/api/catalogue?track=llm")
    assert status == 200 and body["track"] == "llm"
    status, body = _call(instance, "GET", "/api/catalogue?track=inconnu")
    assert status == 422 and "parcours" in body["reason_text"]
    status, shell = _call(instance, "GET", "/api/shell")
    assert [t["key"] for t in shell["tracks"]] == ["llm", "no_ai"]
    # Une carte indisponible ne s'ouvre pas.
    status, body = _call(
        instance, "POST", "/api/open", {"scenario_id": "branche", "mode": "A", "track": "llm"}
    )
    assert (
        status == 409 and "gitleaks" in body["reason_text"] and "diagnostic" in body["reason_text"]
    )


def test_chaque_parcours_a_son_espace_et_chaque_scenario_son_etat_initial(
    instance: cli.Instance,
) -> None:
    # Ouvrir un scénario sans avoir ouvert le précédent, dans les deux parcours : deux espaces.
    status, llm = _call(
        instance, "POST", "/api/open", {"scenario_id": "pr-merge", "mode": "A", "track": "llm"}
    )
    assert status in (200, 202) and llm["workspace_id"] == "llm.pr-merge.A"
    status, no_ai = _call(
        instance, "POST", "/api/open", {"scenario_id": "pr-merge", "mode": "A", "track": "no_ai"}
    )
    assert status in (200, 202) and no_ai["workspace_id"] == "no_ai.pr-merge.A"


def test_progress_illisible_rend_un_motif_et_non_une_erreur_nue(
    instance: cli.Instance, settings: Settings
) -> None:
    data = settings.resolved_data_dir()
    data.mkdir(parents=True, exist_ok=True)
    (data / "progress.json").write_text("{ pas du json", encoding="utf-8")
    status, body = _call(instance, "GET", "/api/catalogue?track=llm")
    assert status == 500
    assert "progress.json" in body["reason_text"] and "renommez" in body["reason_text"]


def test_scenarios_du_socle_livres_figurent_dans_l_ordre_conseille() -> None:
    """Garde contre la dérive de `SOCLE_ORDER` : un scénario du socle livré dans `content/`
    doit y être nommé (seul le bac à sable libre vient après, hors ordre)."""
    from wavedevsecops.scenarios.order import SOCLE_ORDER, SOCLE_SECTION
    from wavedevsecops.web.catalogue import load_catalogue

    hors_ordre = {"bac-a-sable-libre"}
    content = Path(__file__).resolve().parents[1] / "content"
    socle = {
        loaded.scenario.scenario_id
        for loaded in load_catalogue(Settings(content_dir=content))
        if loaded.scenario.catalogue and loaded.scenario.section in (None, SOCLE_SECTION)
    }
    assert socle - hors_ordre <= set(SOCLE_ORDER)
