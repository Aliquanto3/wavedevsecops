"""Scénarios déclaratifs (AD-7) : modèle YAML, registre d'ops de setup, alias.

`scenarios` dépend de `gitio` (git en contexte interne) et de `wsfs` (fichiers en LF) ;
il ne lance aucun processus et n'écrit aucun fichier lui-même.
"""

from wavedevsecops.scenarios.context import PERSONAS, SETUP_EPOCH, SetupContext, SetupError
from wavedevsecops.scenarios.loader import (
    FieldError,
    LoadedScenario,
    ScenarioError,
    load_scenario,
    parse_scenario,
    scenario_files,
)
from wavedevsecops.scenarios.model import SCHEMA_VERSION, Scenario, StepSpec
from wavedevsecops.scenarios.ops import REGISTRY
from wavedevsecops.scenarios.setup import run_setup
from wavedevsecops.scenarios.steps import STEP_TYPES

__all__ = [
    "PERSONAS",
    "REGISTRY",
    "SCHEMA_VERSION",
    "SETUP_EPOCH",
    "STEP_TYPES",
    "FieldError",
    "LoadedScenario",
    "Scenario",
    "ScenarioError",
    "SetupContext",
    "SetupError",
    "StepSpec",
    "load_scenario",
    "parse_scenario",
    "run_setup",
    "scenario_files",
]
