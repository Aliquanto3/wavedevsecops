"""Lint de contenu (AD-13) : aucune étape de scénario ne déclare `run_exercise_code`."""

from __future__ import annotations

import pytest
from test_scenarios import VALID, _errors

from wavedevsecops.config import Settings
from wavedevsecops.scenarios import load_scenario, scenario_files


@pytest.mark.parametrize(
    "hidden",
    [
        "    intent: run_exercise_code\n",
        "    actions:\n      - run_exercise_code\n",
        "    run_exercise_code: true\n",
    ],
)
def test_etape_qui_ajoute_un_champ_est_refusee(hidden: str) -> None:
    """Les types d'étape sont fermés (AD-7) : un champ ajouté est refusé par le schéma."""
    errors = _errors(VALID.rstrip("\n") + "\n" + hidden, tool_ids={"git"})
    assert errors and errors[0].field.startswith("steps[0]")


def test_etape_qui_nomme_l_intention_est_refusee() -> None:
    """Le lint sémantique attrape l'intention nommée dans une valeur, à toute profondeur."""
    text = VALID.replace("name: feature\n          at", "name: run_exercise_code\n          at")
    errors = _errors(text, tool_ids={"git"})
    assert any(e.field == "steps[0]" and "run_exercise_code" in e.message for e in errors)


def test_aucun_scenario_du_depot_ne_la_declare() -> None:
    for path in scenario_files(Settings()):
        assert "run_exercise_code" not in path.read_text("utf-8"), path.name
        load_scenario(path, Settings())
