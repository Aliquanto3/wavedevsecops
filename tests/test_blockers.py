# ruff: noqa: E501
"""Encart « Ce qui l'aurait bloqué » (story 5.9) : schéma, lint de contenu, déclarations des
scénarios B, projection serveur selon le jalon (livrée ou non) et rendu du panneau sous Node."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from test_scenario_panel_dom import PRELUDE
from test_shell_js import NODE, _run

from wavedevsecops.config import Settings
from wavedevsecops.engine.steps import StepRunner
from wavedevsecops.scenarios import ScenarioError, load_scenario, parse_scenario, scenario_files
from wavedevsecops.web.blockers import blockers_body, catalogue_scenario_titles, chain_barriers
from wavedevsecops.web.shell import STATION_MILESTONES, station_delivered

BASE = """
schema_version: 1
scenario_id: essai
mode: B
title_text: Essai
tracks: [llm]
"""
BLOCKER = """
blocked_by:
  - barrier_id: {barrier}
    station: {station}
    scenario_id: {scenario}
    reason_text: Parce que.
"""
BARRIERS = {"secret-scan": 1, "protection": 2}
SCENARIOS = {"secret-dans-un-commit", "push-direct-main"}


def _parse(extra: str = "", **kwargs: Any):
    return parse_scenario(BASE + extra, "essai.B.yaml", **kwargs)


def _blocker(barrier="secret-scan", station=1, scenario="secret-dans-un-commit") -> str:
    return BLOCKER.format(barrier=barrier, station=station, scenario=scenario)


# ------------------------------------------------------------------------------- schéma et lint
def test_scenario_sans_liste_reste_valide() -> None:
    assert _parse().blocked_by == []
    assert _parse(barriers=BARRIERS, scenario_ids=SCENARIOS).blocked_by == []


def test_schema_accepte_la_declaration() -> None:
    (blocker,) = _parse(_blocker()).blocked_by
    assert (blocker.barrier_id, blocker.station, blocker.scenario_id) == (
        "secret-scan",
        1,
        "secret-dans-un-commit",
    )
    assert _parse(_blocker(), barriers=BARRIERS, scenario_ids=SCENARIOS)


@pytest.mark.parametrize(
    ("extra", "fragment"),
    [
        (_blocker(barrier="inventee"), "barrière inconnue"),
        (_blocker(station=2), "est en station 1"),
        (_blocker(scenario="fantome"), "scénario inconnu"),
        (
            _blocker()
            + "  - barrier_id: secret-scan\n    station: 1\n    scenario_id: secret-dans-un-commit\n    reason_text: Encore.\n",
            "en double",
        ),
    ],
)
def test_le_lint_refuse_les_declarations_incoherentes(extra: str, fragment: str) -> None:
    with pytest.raises(ScenarioError) as error:
        _parse(extra, barriers=BARRIERS, scenario_ids=SCENARIOS)
    assert fragment in str(error.value)


def test_schema_refuse_un_champ_inconnu_ou_une_phrase_absente() -> None:
    with pytest.raises(ScenarioError):
        _parse(_blocker().replace("    reason_text: Parce que.\n", ""))
    with pytest.raises(ScenarioError):
        _parse(_blocker() + "    lien: x\n")


# ------------------------------------------------------------------- scénarios B du catalogue
def test_declarations_des_scenarios_b() -> None:
    settings = Settings()
    barriers = chain_barriers(settings)
    ids = set(catalogue_scenario_titles(settings))
    declared = {}
    for path in scenario_files(settings):
        scenario = load_scenario(path, settings, barriers=barriers, scenario_ids=ids).scenario
        if scenario.blocked_by:
            declared[scenario.key] = [
                (b.barrier_id, b.station, b.scenario_id) for b in scenario.blocked_by
            ]
    assert declared == {
        "add-commit.B": [("secret-scan", 1, "secret-dans-un-commit")],
        "push-pull.B": [("protection", 2, "push-direct-main")],
    }


def test_stash_et_rebase_ne_declarent_rien() -> None:
    for key in ("stash.B", "rebase.B"):
        assert _scenario(key).blocked_by == []


# --------------------------------------------------------------------- projection selon le jalon
def _scenario(key: str):
    settings = Settings()
    return load_scenario(settings.scenarios_path() / f"{key}.yaml", settings).scenario


def test_station_livree_selon_le_jalon() -> None:
    assert not station_delivered(1, "v0.1")
    assert station_delivered(1, "v0.2") and station_delivered(2, "v0.3")
    assert not station_delivered(4, "v0.2") and not station_delivered(9, "v9.0")
    assert set(STATION_MILESTONES) == {1, 2, 3, 4}


def test_station_non_livree_etiquette_en_tirets_sans_lien() -> None:
    body = blockers_body(_scenario("add-commit.B"), Settings(), "v0.1")
    assert body is not None and body["title_text"] == "Ce qui l'aurait bloqué"
    (item,) = body["items"]
    assert item["barrier_id"] == "secret-scan" and item["station_text"].startswith(
        "Station 1 · Poste local"
    )
    assert item["delivered"] is False
    assert item["soon_text"] == "Arrive en v0.2"
    assert item["scenario"] is None
    assert item["reason_text"].strip()


def test_station_livree_pas_d_etiquette_et_scenario_en_lien() -> None:
    body = blockers_body(_scenario("push-pull.B"), Settings(), "v0.2")
    assert body is not None
    (item,) = body["items"]
    assert item["delivered"] is True and item["soon_text"] is None
    assert item["scenario"] == {
        "id": "push-direct-main",
        "title_text": catalogue_scenario_titles(Settings())["push-direct-main"],
    }


def test_sans_declaration_aucun_encart() -> None:
    assert blockers_body(_scenario("stash.B"), Settings(), "v0.2") is None


def test_le_panneau_porte_l_encart_via_le_resolveur() -> None:
    settings = Settings()
    runner = StepRunner(settings, None, lambda scenario: blockers_body(scenario, settings, "v0.1"))
    assert (
        runner._blockers_of(_scenario("add-commit.B"))["items"][0]["soon_text"] == "Arrive en v0.2"
    )
    assert runner._blockers_of(_scenario("rebase.B")) is None
    assert StepRunner(settings)._blockers_of(_scenario("add-commit.B")) is None


def test_un_resolveur_en_echec_ne_bloque_pas_le_panneau() -> None:
    def boom(_scenario) -> dict:
        raise RuntimeError("illisible")

    assert StepRunner(Settings(), None, boom)._blockers_of(_scenario("add-commit.B")) is None


# ---------------------------------------------------------------------------------- rendu (Node)
@pytest.mark.skipif(NODE is None, reason="Node absent : comportement JS non exécuté")
def test_rendu_de_l_encart(tmp_path: Path) -> None:
    items = [
        {
            "barrier_id": "secret-scan",
            "label": "Pas de secret dans le commit",
            "station": 1,
            "station_text": "Station 1 · Poste local",
            "reason_text": "gitleaks refuse.",
            "delivered": False,
            "soon_text": "Arrive en v0.2",
            "scenario": None,
        },
        {
            "barrier_id": "protection",
            "label": "Protection de main",
            "station": 2,
            "station_text": "Station 2 · PR et CI",
            "reason_text": "main est protégée.",
            "delivered": True,
            "soon_text": None,
            "scenario": {"id": "push-direct-main", "title_text": "Voir la protection"},
        },
    ]
    script = f"""
{PRELUDE}
const finished = {{ ...PANEL, current_step_id: "", summary: null,
  steps: PANEL.steps.map((s) => ({{ ...s, state: "done" }})),
  blockers: {{ title_text: "Ce qui l'aurait bloqué", items: {json.dumps(items)} }} }};
setup(finished);
const rows = $$(".blocker-item").map((r) => ({{
  barrier: r.dataset.barrier, soon: r.querySelector(".blocker-soon") ? r.querySelector(".blocker-soon").textContent : null,
  link: r.querySelector("a") ? r.querySelector("a").textContent : null }}));
console.log(JSON.stringify({{ title: text(".is-blockers .step-explanation-title"), rows }}));
setup({{ ...finished, blockers: null }});
console.log(JSON.stringify({{ none: $$(".is-blockers").length }}));
"""
    first, second = _run(tmp_path, script).strip().splitlines()[-2:]
    out = json.loads(first)
    assert out["title"] == "Ce qui l'aurait bloqué"
    assert out["rows"] == [
        {"barrier": "secret-scan", "soon": "Arrive en v0.2", "link": None},
        {"barrier": "protection", "soon": None, "link": "Voir la protection"},
    ]
    assert json.loads(second)["none"] == 0
