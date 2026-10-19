"""Scénario « code vulnérable » (Story 8.1) : le job bandit du pipeline, son lecteur de constats
et l'étape de PR qui juge l'état d'un check.

Le vrai bandit (celui de l'environnement de développement, version épinglée) tourne sur le dépôt
préparé par le scénario : il refuse `eval`, puis accepte la correction.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from wavedevsecops import ci, github_sim
from wavedevsecops.ci import findings as parsers
from wavedevsecops.config import Settings
from wavedevsecops.contracts.github import Check, GithubState, PullRequest
from wavedevsecops.engine import prepare_workspace
from wavedevsecops.scenarios import load_scenario
from wavedevsecops.scenarios.steps import pr_state
from wavedevsecops.scenarios.steps._base import StepContext
from wavedevsecops.wsfs import Layout

SCENARIO = Settings().scenarios_path() / "code-vulnerable.A.yaml"
FILE = "src/inventory/alertes.py"
SHA, SHA2 = "a" * 40, "b" * 40


def test_le_scenario_declare_le_pipeline_dans_le_parcours_sans_ia() -> None:
    scenario = load_scenario(SCENARIO, Settings()).scenario
    assert scenario.pipeline is True
    assert scenario.tracks == ["no_ai"] and scenario.station == 3
    assert "bandit" in scenario.tools
    assert [s.step_id for s in scenario.steps] == [
        "pousser_feature",
        "ouvrir_pr",
        "lire_le_blocage",
        "corriger_et_pousser",
    ]
    for step in scenario.steps:
        if step.hints:  # le premier palier ne donne pas la réponse
            assert "literal_eval" not in step.hints.lead_text
            assert "eval" not in step.hints.lead_text


def test_le_job_bandit_suit_le_contrat_du_pipeline() -> None:
    job = ci.load_pipeline(Settings()).job("bandit")
    assert job is not None
    assert (job.tool, job.barrier, job.required) == ("bandit", "static-analysis", True)
    assert job.exit_codes.meaning(0) == "success" and job.exit_codes.meaning(1) == "failure"
    assert job.exit_codes.meaning(2) == "error"
    assert [m.parse for m in job.machine] == ["bandit_json"]


def test_le_lecteur_bandit_tire_fichier_ligne_regle_du_json(tmp_path: Path) -> None:
    text = json.dumps(
        {
            "errors": [],
            "results": [
                {
                    "filename": str(tmp_path / "src" / "a.py"),
                    "issue_text": "Use of possibly insecure function",
                    "line_number": 6,
                    "test_id": "B307",
                }
            ],
        }
    )
    (found,) = parsers.parse_bandit_json(text, tmp_path)
    assert (found.rule_id, found.path, found.line) == ("B307", "src/a.py", 6)
    assert parsers.parse_bandit_json("", tmp_path) == []
    assert parsers.parse_bandit_json('{"results": []}', tmp_path) == []
    with pytest.raises(ValueError):
        parsers.parse_bandit_json("pas du json", tmp_path)
    with pytest.raises(ValueError):
        parsers.parse_bandit_json("[]", tmp_path)


def _bandit(tree: Path, *extra: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603 - bandit épinglé de l'environnement de développement
        [sys.executable, "-m", "bandit", "-r", "src", "-q", *extra],
        cwd=tree,
        capture_output=True,
        text=True,
        check=False,
    )


def test_le_vrai_bandit_refuse_eval_puis_accepte_la_correction(
    tmp_path: Path, git_path: Path
) -> None:
    prepared = prepare_workspace(
        load_scenario(SCENARIO, Settings()),
        "no_ai",
        settings=Settings(data_dir=tmp_path),
        git_path=git_path,
    )
    tree = prepared.layout.repo
    refused = _bandit(tree, "-f", "json")
    assert refused.returncode == 1, refused.stderr
    (found,) = parsers.parse_bandit_json(refused.stdout, tree)
    assert (found.rule_id, found.path, found.line) == ("B307", FILE, 6)
    human = _bandit(tree)
    assert "B307" in human.stdout and f"{FILE}:6" in human.stdout.replace("\\", "/")
    # Le correctif de la solution de l'étape.
    (tree / FILE).write_text(
        "import ast\n\n\ndef seuil_depuis_texte(texte: str) -> int:\n"
        "    return ast.literal_eval(texte)\n",
        "utf-8",
    )
    accepted = _bandit(tree, "-f", "json")
    assert accepted.returncode == 0, accepted.stdout
    assert parsers.parse_bandit_json(accepted.stdout, tree) == []


# ------------------------------------------------------------------ étape de PR et checks
def _layout(tmp_path: Path, checks: list[Check], *, head: str = SHA) -> Layout:
    layout = Layout(tmp_path / "ws")
    layout.root.mkdir(parents=True)
    pr = PullRequest(
        number=1, head="feature", base="main", head_sha=head, base_sha=SHA, checks=checks
    )
    github_sim._save(layout, GithubState(pulls=[pr], next_number=2))
    return layout


def _step(state: str) -> pr_state.Args:
    return pr_state.Args(
        type="pr_state",
        step_id="essai",
        title_text="t",
        instruction_text="i",
        explanation_text="e",
        head="feature",
        checks={"bandit": state},
    )


def _status(layout: Layout, state: str) -> str:
    return pr_state.check(None, StepContext(step=_step(state), layout=layout)).status


def test_l_etape_juge_l_etat_du_check_sur_les_sha_courants(tmp_path: Path) -> None:
    def bandit(state: str, head: str = SHA) -> Check:
        return Check(job_id="bandit", head_sha=head, base_sha=SHA, state=state)  # type: ignore[arg-type]

    failed = _layout(tmp_path / "a", [bandit("failure")])
    assert _status(failed, "failure") == "passed"
    assert _status(failed, "success") == "pending"
    assert _status(_layout(tmp_path / "b", [bandit("success")]), "success") == "passed"
    assert _status(_layout(tmp_path / "c", [bandit("running")]), "success") == "pending"
    # Un résultat calculé pour un ancien SHA de tête ne valide rien.
    assert _status(_layout(tmp_path / "d", [bandit("success", SHA2)]), "success") == "pending"
    assert _status(_layout(tmp_path / "e", []), "failure") == "pending"


def test_l_etape_refuse_un_job_id_invalide() -> None:
    with pytest.raises(ValueError, match="job_id invalide"):
        pr_state.Args(
            type="pr_state",
            step_id="essai",
            title_text="t",
            instruction_text="i",
            explanation_text="e",
            head="feature",
            checks={"Bandit-1": "failure"},
        )
