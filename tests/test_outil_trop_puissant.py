"""Story 8.5 : le scénario LLM « outil trop puissant » (Flow 4, station 3).

Un outil donné à l'assistant fait évaluer du code (bandit), une dépendance épinglée est
vulnérable (pip-audit, SBOM), le nouveau module n'est pas testé (quality gate), et `main` exige
deux approbations. Aucun vrai modèle de langage ni aucun réseau : le module d'outil n'est jamais
appelé par un modèle, et le point OSV est celui de la plateforme (loopback). Les tests lents
lancent les vrais outils de l'environnement de développement sur l'arbre du scénario.
"""

# ruff: noqa: F811
from __future__ import annotations

import tomllib
from pathlib import Path

import pytest
import yaml
from test_quality_gate import _commit, _run, osv_url, real_tools  # noqa: F401

from wavedevsecops import ci, github_sim
from wavedevsecops.ci import findings as parsers
from wavedevsecops.config import Settings
from wavedevsecops.contracts.github import Check, GithubState, PullRequest
from wavedevsecops.engine import prepare_workspace
from wavedevsecops.engine.designation import correct
from wavedevsecops.gitio import Git
from wavedevsecops.projections import EXPLAIN_REFS
from wavedevsecops.scenarios import load_scenario
from wavedevsecops.scenarios.order import STATION_ORDER
from wavedevsecops.scenarios.steps import pr_state
from wavedevsecops.scenarios.steps._base import StepContext
from wavedevsecops.wsfs import Layout

SETTINGS = Settings()
SCENARIO = SETTINGS.scenarios_path() / "outil-trop-puissant.A.yaml"
PIPELINE = ci.load_pipeline(SETTINGS)
SHA = "a" * 40
JOBS = ("ruff", "pytest", "gitleaks", "bandit", "pip_audit", "uv_lock", "quality_gate")

RESTRICTED = '''\
"""Outil « requête » de l'assistant : des requêtes prévues, jamais du code libre."""

# ruff: noqa: F811
from __future__ import annotations

from typing import Any

from inventory.stock import Stock

QUERY_TOOL: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "run_query",
        "description": "Requête prévue sur le stock : sous_le_seuil.",
        "parameters": {
            "type": "object",
            "properties": {"name": {"type": "string"}},
            "required": ["name"],
        },
    },
}


def run_query(stock: Stock, name: str) -> str:
    """Exécute la requête prévue `name` ; refuse tout autre nom."""
    if name == "sous_le_seuil":
        return ", ".join(stock.below_threshold()) or "aucun"
    raise ValueError(f"Requête inconnue : « {name} ».")
'''
TESTS = """\
import pytest

from inventory import Stock
from inventory.query_tool import run_query


def test_requete_prevue() -> None:
    stock = Stock()
    stock.add("vis", 3, threshold=5)
    assert run_query(stock, "sous_le_seuil") == "vis"


def test_requete_inconnue_refusee() -> None:
    with pytest.raises(ValueError):
        run_query(Stock(), "__import__('os')")
"""


# ------------------------------------------------------------------ le scénario
def test_le_scenario_declare_le_parcours_llm_et_la_station_3() -> None:
    loaded = load_scenario(SCENARIO, SETTINGS, explain_keys=EXPLAIN_REFS)
    scenario = loaded.scenario
    assert (scenario.scenario_id, scenario.mode, scenario.station) == (
        "outil-trop-puissant",
        "A",
        3,
    )
    assert scenario.pipeline is True and list(scenario.tracks) == ["llm"]
    assert (scenario.section, scenario.catalogue) == ("stations", True)
    assert not scenario.authoring_warnings()
    assert STATION_ORDER.index("outil-trop-puissant") > STATION_ORDER.index(
        "couverture-sous-le-seuil"
    )
    assert [s.step_id for s in scenario.steps] == [
        "pousser_feature",
        "ouvrir_pr",
        "lire_le_blocage",
        "restreindre_l_outil",
        "designer_la_dependance",
        "mettre_a_jour_la_dependance",
        "tester_l_outil",
        "constater_les_approbations",
        "merger_la_pr",
    ]
    by_id = {s.step_id: s for s in scenario.steps}
    for step in scenario.steps:
        assert step.hints is not None
    # Le blocage initial : bandit en échec, aucune approbation sur les deux requises.
    blocked = by_id["lire_le_blocage"]
    assert (blocked.check_states, blocked.max_approvals, blocked.mergeable) == (
        {"bandit": "failure"},
        0,
        False,
    )
    # Leçon 6.2 : ni dépendance retirée, ni module supprimé ne valident une étape.
    assert by_id["mettre_a_jour_la_dependance"].sbom_has == {"pip_audit": ["h11"]}
    assert by_id["tester_l_outil"].finding_has == {"quality_gate": ["diff_coverage"]}
    assert by_id["designer_la_dependance"].slots[0].answers == ["sbom:h11@0.14.0"]
    # Tous les checks verts et deux approbations avant le merge.
    final = by_id["constater_les_approbations"]
    assert set(final.check_states) == set(JOBS) and final.min_approvals == 2
    assert by_id["merger_la_pr"].min_approvals == 2


def test_le_pipeline_a_les_sept_jobs_que_le_scenario_attend() -> None:
    assert {job.job_id for job in PIPELINE.jobs} == set(JOBS)


# ------------------------------------------------------------------ le dépôt de départ
@pytest.fixture
def prepared(tmp_path: Path, git_path: Path):
    settings = Settings(data_dir=tmp_path / "data")
    prepared = prepare_workspace(
        load_scenario(SCENARIO, settings), "llm", settings=settings, git_path=git_path
    )
    git = Git.for_workspace(git_path, prepared.layout.root, settings)
    return prepared.layout, git


def test_le_depart_porte_l_outil_dangereux_et_la_dependance_vulnerable(prepared) -> None:
    layout, git = prepared
    changed = git.run("diff", "--name-only", "HEAD~1", "HEAD", cwd=layout.repo)
    assert sorted(changed.stdout.split()) == ["requirements.txt", "src/inventory/query_tool.py"]
    assert "eval(expression" in (layout.repo / "src/inventory/query_tool.py").read_text("utf-8")
    pins = (layout.repo / "requirements.txt").read_text("utf-8").splitlines()
    assert "h11==0.14.0" in pins and "h11==0.16.0" not in pins
    # pyproject.toml et uv.lock ne bougent pas : `uv_lock` reste vert (h11 est transitif).
    lock = tomllib.loads((layout.repo / "uv.lock").read_text("utf-8"))
    assert {p["name"]: p["version"] for p in lock["package"]}["h11"] == "0.16.0"


def test_main_exige_sept_checks_et_deux_approbations_les_revues_arrivent_au_vert(
    prepared,
) -> None:
    layout, git = prepared
    (protection,) = github_sim.load(layout).protections
    assert protection.required_approvals == 2
    assert set(protection.required_checks) == set(JOBS)
    git.run("push", "-u", "origin", "feature", cwd=layout.repo)
    pr = github_sim.open_pr(git, layout, "feature", "main")
    github_sim.ensure_checks(git, layout, pr.number, [(job, True) for job in JOBS])
    for job in JOBS[:-1]:
        github_sim.set_check_state(git, layout, pr.number, job, "success", output="ok")
    pr = github_sim.load(layout).pulls[0]
    assert (pr.count_approvals(), pr.mergeable) == (0, False)
    reasons = " ".join(b.text for b in pr.blocking_reasons)
    assert "Approbations : 0 sur 2" in reasons
    github_sim.set_check_state(git, layout, pr.number, JOBS[-1], "success", output="ok")
    pr = github_sim.load(layout).pulls[0]
    assert pr.count_approvals() == 2 and pr.mergeable is True
    assert sorted({r.author for r in pr.reviews}) == ["Agent B", "Sacha Martin"]


# ------------------------------------------------------------------ étapes de PR
def _layout(tmp_path: Path, checks: list[Check]) -> Layout:
    layout = Layout(tmp_path / "ws")
    layout.root.mkdir(parents=True)
    pr = PullRequest(
        number=1, head="feature", base="main", head_sha=SHA, base_sha=SHA, checks=checks
    )
    github_sim._save(layout, GithubState(pulls=[pr], next_number=2))
    return layout


def _step(step_id: str) -> pr_state.Args:
    scenario = load_scenario(SCENARIO, SETTINGS).scenario
    return next(s for s in scenario.steps if s.step_id == step_id)  # type: ignore[return-value]


def _status(layout: Layout, step_id: str) -> str:
    return pr_state.check(None, StepContext(step=_step(step_id), layout=layout)).status


def _check(job: str, state: str, **extra: object) -> Check:
    return Check(job_id=job, head_sha=SHA, base_sha=SHA, state=state, **extra)  # type: ignore[arg-type]


def test_l_etape_de_test_refuse_le_module_supprime(tmp_path: Path) -> None:
    from wavedevsecops.contracts.github import Finding

    measured = [Finding(rule_id="diff_coverage", severity="info")]
    empty = [Finding(rule_id=parsers.NO_DIFF_RULE, severity="info")]

    def checks(findings: list[Finding]) -> list[Check]:
        return [
            _check("bandit", "success"),
            _check("pytest", "success"),
            _check("quality_gate", "success", findings=findings),
        ]

    step = "tester_l_outil"
    assert _status(_layout(tmp_path / "a", checks(measured)), step) == "passed"
    assert _status(_layout(tmp_path / "b", checks(empty)), step) == "pending"
    assert _status(_layout(tmp_path / "c", checks([])), step) == "pending"


def test_la_designation_du_composant_vulnerable_est_corrigee() -> None:
    step = next(
        s for s in load_scenario(SCENARIO, SETTINGS).scenario.steps if s.type == "designate"
    )
    assert correct(step, {}, ["sbom:h11@0.14.0"], None).correct
    assert not correct(step, {}, ["sbom:anyio@4.15.1"], None).correct


def test_le_scenario_n_ajoute_ni_job_ni_gabarit_llm() -> None:
    """Le scénario n'ajoute aucun job (sept jobs) et n'écrit que par ses propres ops de setup."""
    data = yaml.safe_load(SCENARIO.read_text("utf-8"))
    ops = [op["op"] for op in data["setup"]]
    assert set(ops) <= {
        "exercise_stage",
        "commit",
        "push",
        "set_protection",
        "colleague_reaction",
        "switch",
        "write_file",
        "replace_in_file",
    }
    assert data["setup"][0] == {"op": "exercise_stage", "stage": "loop"}


# ------------------------------------------------------------------ les vrais outils
@pytest.fixture
def tree(tmp_path: Path, git_path: Path) -> tuple[Path, str]:
    import subprocess

    prepared = prepare_workspace(
        load_scenario(SCENARIO, SETTINGS),
        "llm",
        settings=Settings(data_dir=tmp_path / "data"),
        git_path=git_path,
    )
    repo = prepared.layout.repo
    base = subprocess.run(
        [str(git_path), "rev-parse", "HEAD~1"], cwd=repo, capture_output=True, text=True, check=True
    ).stdout.strip()
    return repo, base


def _job(name: str) -> ci.Job:
    job = PIPELINE.job(name)
    assert job is not None
    return job


@pytest.mark.slow
def test_les_vrais_outils_refusent_le_depart_puis_acceptent_la_correction(
    tmp_path: Path,
    git_path: Path,
    tree: tuple[Path, str],
    osv_url: str,
    real_tools: list[str],
) -> None:
    repo, base = tree
    run = lambda name: _run(_job(name), repo, base, tmp_path, osv_url=osv_url)  # noqa: E731
    # Au départ : bandit (B307), pip-audit (h11 0.14.0) et la quality gate (0 %) échouent ;
    # le lint, les tests et le verrou sont verts.
    bandit = run("bandit")
    assert bandit.state == "failure" and "B307" in bandit.output
    assert {f.path for f in bandit.findings} == {"src/inventory/query_tool.py"}
    audit = run("pip_audit")
    assert audit.state == "failure" and {c.name for c in audit.sbom if c.vulns} == {"h11"}
    gate = run("quality_gate")
    assert gate.state == "failure"
    for name in ("ruff", "pytest", "uv_lock"):
        assert run(name).state == "success", name
    # Correction : outil restreint, dépendance à jour, tests.
    (repo / "src/inventory/query_tool.py").write_text(RESTRICTED, "utf-8")
    requirements = repo / "requirements.txt"
    requirements.write_text(
        requirements.read_text("utf-8").replace("h11==0.14.0", "h11==0.16.0"), "utf-8"
    )
    (repo / "tests" / "test_query_tool.py").write_text(TESTS, "utf-8")
    _commit(repo, git_path, "Restreint l'outil, met h11 à jour et teste")
    for name in JOBS:
        if name == "gitleaks" and "gitleaks" in real_tools:
            continue  # absent hors CI
        result = run(name)
        assert result.state == "success", (name, result.output)
    assert {f.rule_id for f in run("quality_gate").findings} >= {"diff_coverage"}
    assert next(c for c in run("pip_audit").sbom if c.name == "h11").version == "0.16.0"


@pytest.mark.slow
def test_les_contournements_ne_valident_aucune_etape(
    tmp_path: Path,
    git_path: Path,
    tree: tuple[Path, str],
    osv_url: str,
    real_tools: list[str],
) -> None:
    """Leçon 6.2 : supprimer l'outil, l'exempter, ou retirer la dépendance ne valide pas."""
    repo, base = tree
    run = lambda name: _run(_job(name), repo, base, tmp_path, osv_url=osv_url)  # noqa: E731
    module = repo / "src/inventory/query_tool.py"
    original = module.read_text("utf-8")
    # `# nosec` est refusé (--ignore-nosec).
    module.write_text(
        original.replace("eval(expression", "eval(  # nosec\n    expression"), "utf-8"
    )
    assert run("bandit").state == "failure"
    # Un fichier `.bandit` ou `[tool.bandit]` du dépôt est ignoré (réglages hors de l'arbre).
    module.write_text(original, "utf-8")
    (repo / "src" / ".bandit").write_text("[bandit]\nskips = B307\n", "utf-8")
    assert run("bandit").state == "failure"
    (repo / "src" / ".bandit").unlink()
    # Outil supprimé : bandit passe, mais la quality gate ne mesure plus aucune ligne neuve : le
    # constat `diff_coverage` manque, donc l'étape « tester_l_outil » reste en attente.
    module.unlink()
    assert run("bandit").state == "success"
    gate = run("quality_gate")
    assert "diff_coverage" not in {f.rule_id for f in gate.findings}
    # Dépendance retirée : pip-audit passe, mais le SBOM n'a plus h11 (`sbom_has`).
    requirements = repo / "requirements.txt"
    requirements.write_text(
        "".join(
            line
            for line in requirements.read_text("utf-8").splitlines(keepends=True)
            if not line.startswith("h11==")
        ),
        "utf-8",
    )
    audit = run("pip_audit")
    assert audit.state == "success" and "h11" not in {c.name for c in audit.sbom}
