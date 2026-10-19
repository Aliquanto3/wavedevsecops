"""Story 8.4 : la quality gate de couverture du nouveau code, le verrou `uv lock --check` et le
bandit lu hors de l'arbre de l'apprenant.

Contrat du job `quality_gate` (AD-10) : `pytest --cov` (réglages de `content/ci/coverage.ini`),
puis `diff-cover` contre `{base_sha}` avec `--fail-under=80` ; constats tirés de `coverage json` et
de `diff-cover --format json:`. Les tests lents lancent les vrais outils de l'environnement de
développement sur l'arbre du scénario `couverture-sous-le-seuil` (aucun réseau, sauf le point OSV
local du test de performance).
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
import tomllib
import warnings
from collections.abc import Iterator
from pathlib import Path

import pytest

from wavedevsecops import ci, cli, github_sim, procs, toolrun
from wavedevsecops.ci import findings as parsers
from wavedevsecops.config import Settings
from wavedevsecops.contracts.github import Check, Finding, GithubState, PullRequest
from wavedevsecops.engine import prepare_workspace
from wavedevsecops.scenarios import load_scenario
from wavedevsecops.scenarios.order import STATION_ORDER
from wavedevsecops.scenarios.steps import pr_state
from wavedevsecops.scenarios.steps._base import StepContext
from wavedevsecops.wsfs import Layout

ROOT = Path(__file__).resolve().parent.parent
SETTINGS = Settings()
SCENARIO = SETTINGS.scenarios_path() / "couverture-sous-le-seuil.A.yaml"
EXERCISE = SETTINGS.content_path() / "exercise"
PIPELINE = ci.load_pipeline(SETTINGS)
GATE = PIPELINE.job("quality_gate")
BANDIT = PIPELINE.job("bandit")
UV_LOCK = PIPELINE.job("uv_lock")
SHA = "a" * 40
THRESHOLD = 80

TESTS_OK = """\
from inventory import Stock
from inventory.alertes import order_lines, quantity_to_order


def test_quantity_to_order_is_never_negative() -> None:
    stock = Stock()
    stock.add("vis", 10)
    assert quantity_to_order(stock, "vis", 15) == 5
    assert quantity_to_order(stock, "vis", 4) == 0


def test_order_lines_are_sorted_and_skip_full_articles() -> None:
    stock = Stock()
    stock.add("vis", 10)
    stock.add("clous", 1)
    assert order_lines(stock, {"vis": 15, "clous": 3}) == ["clous : 2", "vis : 5"]
    assert order_lines(stock, {"vis": 4}) == []
"""


# ------------------------------------------------------------------ contrat des jobs
def test_le_job_quality_gate_suit_le_contrat_d_ad_10() -> None:
    assert GATE is not None
    assert (GATE.tool, GATE.barrier, GATE.required) == ("diff-cover", "coverage", True)
    assert GATE.exit_codes.meaning(0) == "success" and GATE.exit_codes.meaning(1) == "failure"
    assert GATE.exit_codes.meaning(2) == "error"
    # pytest --cov d'abord, avec les réglages hors de l'arbre et sans les `addopts` du dépôt.
    (before,) = GATE.before
    assert before.tool == "pytest"
    assert "--cov" in before.argv and "-o" in before.argv and "addopts=" in before.argv
    # `--option=valeur` : une valeur détachée serait prise pour un chemin à collecter.
    assert "--cov-config={config}/coverage.ini" in before.argv
    assert "--cov-report=xml:{reports}/coverage.xml" in before.argv  # hors de l'arbre
    # diff-cover contre la base de la PR, au seuil de 80 %, le même chiffre que l'affichage.
    assert GATE.human == [
        "{reports}/coverage.xml",
        "--compare-branch={base_sha}",
        "--fail-under=80",
    ]
    assert f"--fail-under={parsers.QUALITY_GATE_THRESHOLD}" in GATE.human
    assert parsers.QUALITY_GATE_THRESHOLD == THRESHOLD
    # Constats : `diff-cover --format json:` et `coverage json`, lus même quand le check est vert.
    assert [(m.tool, m.parse, m.when) for m in GATE.machine] == [
        (None, "diff_cover_json", "always"),
        ("coverage", "coverage_json", "always"),
    ]
    assert "--format" in GATE.machine[0].argv and "json:{report}" in GATE.machine[0].argv
    assert GATE.machine[1].argv[:1] == ["json"]
    # Aucune option qui baisserait le seuil ou écarterait des lignes.
    flat = " ".join([*GATE.human, *(a for m in GATE.machine for a in m.argv)])
    for forbidden in ("--exclude", "--ignore", "--config-file", "--no-cov"):
        assert forbidden not in flat


def test_bandit_est_lance_avec_un_fichier_ini_hors_de_l_arbre() -> None:
    assert BANDIT is not None
    for argv in (BANDIT.human, BANDIT.machine[0].argv):
        assert argv[argv.index("--ini") + 1] == "{config}/bandit.ini"
        assert "--ignore-nosec" in argv
    assert (SETTINGS.ci_config_path() / "bandit.ini").is_file()


def test_le_job_uv_lock_verifie_la_coherence_de_pyproject_et_du_verrou() -> None:
    assert UV_LOCK is not None
    assert (UV_LOCK.tool, UV_LOCK.human, UV_LOCK.required) == ("uv", ["lock", "--check"], True)
    assert UV_LOCK.barrier == "dependencies" and not UV_LOCK.machine
    assert UV_LOCK.exit_codes.meaning(1) == "failure" and UV_LOCK.exit_codes.meaning(2) == "error"
    assert PIPELINE.job_ids[-2:] == ["uv_lock", "quality_gate"]
    assert PIPELINE.job_ids == [
        "ruff",
        "pytest",
        "gitleaks",
        "bandit",
        "pip_audit",
        "uv_lock",
        "quality_gate",
    ]


def test_les_reglages_hors_de_l_arbre_ne_laissent_rien_a_l_apprenant() -> None:
    text = (SETTINGS.ci_config_path() / "coverage.ini").read_text("utf-8")
    code = "\n".join(line for line in text.splitlines() if not line.lstrip().startswith("#"))
    assert "omit" not in code and "fail_under" not in code
    assert "source = ." in code and "include_namespace_packages = True" in code
    # Les motifs d'exclusion par défaut (dont `# pragma: no cover`) sont remplacés, pas complétés.
    assert "exclude_lines =" in code and "pragma" not in code


@pytest.mark.parametrize("name", ["pytest-cov", "coverage", "diff-cover"])
def test_les_outils_ajoutes_sont_epingles_partout_et_presents_en_ci(name: str) -> None:
    """Versions identiques dans pyproject.toml, uv.lock, tools.toml et les deux gabarits ; le
    groupe `chain` que la CI installe (`uv sync --locked --group chain`) les contient."""
    chain = tomllib.loads((ROOT / "pyproject.toml").read_text("utf-8"))["dependency-groups"][
        "chain"
    ]
    pinned = {spec.split("==")[0]: spec.split("==")[1] for spec in chain}
    version = pinned[name]
    lock = tomllib.loads((ROOT / "uv.lock").read_text("utf-8"))
    assert {p["name"]: p["version"] for p in lock["package"]}[name] == version
    tools = tomllib.loads((ROOT / "tools.toml").read_text("utf-8"))["tool"]
    assert {t["id"]: t["provisioned_version"] for t in tools}[name] == version
    for track in ("no_ai", "llm"):
        deps = tomllib.loads((EXERCISE / track / "pyproject.toml").read_text("utf-8"))
        assert f"{name}=={version}" in deps["dependency-groups"]["chain"]
        locked = tomllib.loads((EXERCISE / track / "uv.lock").read_text("utf-8"))
        assert {p["name"]: p["version"] for p in locked["package"]}[name] == version
    workflow = (ROOT / ".github" / "workflows" / "ci.yml").read_text("utf-8")
    assert "uv sync --locked --group chain" in workflow


# ------------------------------------------------------------------ lecteurs
def _diff(total: int, covered: list[int], missing: list[int], path: str = "src/a.py") -> str:
    stats = {path: {"violation_lines": missing, "covered_lines": covered}} if total else {}
    percent = int(100 * len(covered) / total) if total else 100
    return json.dumps(
        {
            "src_stats": stats,
            "total_num_lines": total,
            "total_num_violations": len(missing),
            "total_percent_covered": percent,
        }
    )


def test_le_lecteur_diff_cover_sous_le_seuil_affiche_la_valeur_et_le_seuil(tmp_path: Path) -> None:
    found = parsers.parse_diff_cover_json(_diff(5, [1], [2, 3, 4, 5]), tmp_path)
    summary, files = found
    assert summary.rule_id == "diff_coverage" and summary.severity == "error"
    assert summary.message_text == "Couverture du nouveau code 20 % · seuil 80 % · ✗"
    assert (files.rule_id, files.path, files.line) == ("uncovered_lines", "src/a.py", 2)
    assert files.message_text == "4 lignes du nouveau code sans test : 2-5"


def test_le_lecteur_diff_cover_au_seuil_ou_au_dessus_est_vert(tmp_path: Path) -> None:
    (summary,) = parsers.parse_diff_cover_json(_diff(5, [1, 2, 3, 4], []), tmp_path)
    assert summary.message_text == "Couverture du nouveau code 80 % · seuil 80 % · ✓"
    assert summary.severity == "info"
    # 79 % reste sous le seuil : pas d'arrondi vers le haut (même règle que --fail-under).
    just_below = json.loads(_diff(100, list(range(79)), list(range(79, 100))))
    just_below["total_percent_covered"] = 79
    assert "79 % · seuil 80 % · ✗" in parsers.parse_diff_cover_json(
        json.dumps(just_below), tmp_path
    )[0].message_text


def test_le_lecteur_diff_cover_sans_ligne_mesuree_n_est_pas_un_constat_de_couverture(
    tmp_path: Path,
) -> None:
    (summary,) = parsers.parse_diff_cover_json(_diff(0, [], []), tmp_path)
    assert summary.rule_id == parsers.NO_DIFF_RULE != parsers.DIFF_COVERAGE_RULE
    assert summary.message_text == (
        "Couverture du nouveau code aucune ligne à mesurer · seuil 80 % · ✓"
    )


def test_le_lecteur_diff_cover_normalise_les_chemins_et_refuse_l_illisible(tmp_path: Path) -> None:
    found = parsers.parse_diff_cover_json(_diff(2, [], [7, 9], "src\\inventory\\a.py"), tmp_path)
    assert found[1].path == "src/inventory/a.py" and found[1].line == 7
    assert "7, 9" in found[1].message_text
    for bad in ("", "pas du json", "[]", "{}", '{"src_stats": {}, "total_num_lines": "x"}'):
        with pytest.raises(ValueError):
            parsers.parse_diff_cover_json(bad, tmp_path)


def test_le_lecteur_coverage_donne_la_couverture_totale_et_refuse_une_mesure_vide(
    tmp_path: Path,
) -> None:
    text = json.dumps({"files": {"a.py": {}}, "totals": {"percent_covered": 87.6}})
    (total,) = parsers.parse_coverage_json(text, tmp_path)
    assert total.rule_id == "total_coverage" and "87 %" in total.message_text
    for bad in ("", "[]", '{"files": {}, "totals": {"percent_covered": 0}}', '{"files": {"a": 1}}'):
        with pytest.raises(ValueError):
            parsers.parse_coverage_json(bad, tmp_path)


# ------------------------------------------------------------------ le scénario et l'étape
def test_le_scenario_declare_le_parcours_sans_ia_et_la_station_3() -> None:
    loaded = load_scenario(SCENARIO, SETTINGS)
    scenario = loaded.scenario
    assert (scenario.scenario_id, scenario.mode, scenario.station) == (
        "couverture-sous-le-seuil",
        "A",
        3,
    )
    assert scenario.pipeline and list(scenario.tracks) == ["no_ai"]
    assert "couverture-sous-le-seuil" in STATION_ORDER
    assert STATION_ORDER.index("couverture-sous-le-seuil") > STATION_ORDER.index(
        "dependance-vulnerable"
    )
    assert [s.step_id for s in scenario.steps] == [
        "pousser_feature",
        "ouvrir_pr",
        "lire_le_blocage",
        "ajouter_les_tests",
    ]


def _layout(tmp_path: Path, findings: list[Finding], state: str = "success") -> Layout:
    layout = Layout(tmp_path / "ws")
    layout.root.mkdir(parents=True)
    check = Check(
        job_id="quality_gate",
        head_sha=SHA,
        base_sha=SHA,
        state=state,  # type: ignore[arg-type]
        findings=findings,
    )
    pr = PullRequest(
        number=1, head="feature", base="main", head_sha=SHA, base_sha=SHA, checks=[check]
    )
    github_sim._save(layout, GithubState(pulls=[pr], next_number=2))
    return layout


def _step(**extra: object) -> pr_state.Args:
    return pr_state.Args(
        type="pr_state",
        step_id="essai",
        title_text="t",
        instruction_text="i",
        explanation_text="e",
        head="feature",
        check_states={"quality_gate": "success"},
        finding_has={"quality_gate": ["diff_coverage"]},
        **extra,
    )


def _status(layout: Layout) -> str:
    return pr_state.check(None, StepContext(step=_step(), layout=layout)).status


def test_l_etape_exige_des_lignes_mesurees_pas_un_diff_vide(tmp_path: Path) -> None:
    """Leçon 6.2 : supprimer le code non testé donne un check vert, pas une étape validée."""
    measured = [Finding(rule_id="diff_coverage", severity="info")]
    assert _status(_layout(tmp_path / "a", measured)) == "passed"
    empty = [Finding(rule_id=parsers.NO_DIFF_RULE, severity="info")]
    assert _status(_layout(tmp_path / "b", empty)) == "pending"
    assert _status(_layout(tmp_path / "c", [])) == "pending"
    assert _status(_layout(tmp_path / "d", measured, state="failure")) == "pending"


def test_la_porte_de_fusion_attend_le_job_quality_gate() -> None:
    text = (SETTINGS.scenarios_path() / "pr-sans-revue.A.yaml").read_text("utf-8")
    assert "quality_gate: success" in text and "uv_lock: success" in text


# ------------------------------------------------------------------ les vrais outils
MODULES = {
    "ruff": ["-m", "ruff"],
    "pytest": ["-m", "pytest"],
    "bandit": ["-m", "bandit"],
    "pip-audit": ["-m", "pip_audit"],
    "diff-cover": ["-m", "diff_cover.diff_cover_tool"],
    "coverage": ["-m", "coverage"],
}


@pytest.fixture
def real_tools(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> list[str]:
    """`ci` lance les outils épinglés de l'environnement de développement (pas de réseau) ;
    gitleaks seulement s'il est posé dans `WDS_EXERCISE_DATA` (la CI le fournit). Rend les outils
    qui ne tournent pas."""
    for name in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("NO_PROXY", "127.0.0.1,localhost")
    # Les rapports de couverture de l'arbre testé ne se mélangent pas à ceux de ce test.
    for name in ("COVERAGE_FILE", "COVERAGE_RCFILE", "PYTEST_ADDOPTS", "PYTEST_CURRENT_TEST"):
        monkeypatch.delenv(name, raising=False)
    skipped: list[str] = []
    gitleaks = None
    data = os.environ.get("WDS_EXERCISE_DATA")
    if data:
        status = toolrun.resolve("gitleaks", Settings(data_dir=Path(data)))
        gitleaks = status.path if status.ok else None
    if gitleaks is None:
        skipped.append("gitleaks")
    real_spawn = procs.spawn

    def spawn(tool_id, args, *, cwd, venv, timeout, settings=None):  # noqa: ANN001, ANN202
        if tool_id == "gitleaks":
            command = [str(gitleaks) if gitleaks else sys.executable, *args]
        elif tool_id == "uv":
            command = [shutil.which("uv") or "uv", *args]
        else:
            command = [sys.executable, *MODULES[tool_id], *args]
        env = dict(os.environ)
        env["PYTHONUTF8"] = "1"
        env["UV_OFFLINE"] = "1"
        return real_spawn(command, env=env, cwd=cwd, timeout=timeout)

    monkeypatch.setattr(toolrun, "spawn_tool", spawn)
    return skipped


def _scenario_repo(tmp_path: Path, git_path: Path) -> tuple[Path, str]:
    """L'arbre du scénario (branche `feature`, un commit sur `main`) et le SHA de la base."""
    prepared = prepare_workspace(
        load_scenario(SCENARIO, SETTINGS),
        "no_ai",
        settings=Settings(data_dir=tmp_path / "data"),
        git_path=git_path,
    )
    repo = prepared.layout.repo
    base = subprocess.run(
        [str(git_path), "rev-parse", "HEAD~1"], cwd=repo, capture_output=True, text=True, check=True
    ).stdout.strip()
    return repo, base


def _commit(repo: Path, git_path: Path, message: str) -> None:
    for args in (["add", "-A"], ["commit", "-q", "-m", message]):
        subprocess.run(
            [str(git_path), "-c", "user.name=T", "-c", "user.email=t@example.invalid", *args],
            cwd=repo,
            check=True,
            capture_output=True,
        )


def _run(job: ci.Job | None, repo: Path, base: str, tmp_path: Path, **tokens: str) -> ci.JobResult:
    assert job is not None
    return ci.run_job(
        job,
        tree=repo,
        venv=None,
        tokens={"repo": str(repo), "base_sha": base, **tokens},
        settings=Settings(data_dir=tmp_path / "run"),
    )


def _gate(repo: Path, base: str, tmp_path: Path) -> ci.JobResult:
    return _run(GATE, repo, base, tmp_path)


def _summary(result: ci.JobResult) -> str:
    texts = [
        f.message_text
        for f in result.findings
        if f.rule_id in (parsers.DIFF_COVERAGE_RULE, parsers.NO_DIFF_RULE)
    ]
    assert len(texts) == 1, (result.findings, result.output)
    return texts[0]


@pytest.mark.slow
def test_la_vraie_quality_gate_refuse_le_code_sans_test_puis_accepte_les_tests(
    tmp_path: Path, git_path: Path, real_tools: list[str]
) -> None:
    repo, base = _scenario_repo(tmp_path, git_path)
    refused = _gate(repo, base, tmp_path)
    assert refused.state == "failure", refused.output
    assert _summary(refused) == "Couverture du nouveau code 0 % · seuil 80 % · ✗"
    uncovered = [f for f in refused.findings if f.rule_id == "uncovered_lines"]
    assert [f.path for f in uncovered] == ["src/inventory/alertes.py"]
    assert any(f.rule_id == "total_coverage" for f in refused.findings)
    # Sortie humaine verbatim : celle de pytest --cov, puis celle de diff-cover.
    assert "passed" in refused.output and "Diff Coverage" in refused.output
    assert "Coverage: 0%" in refused.output
    # Des tests pour les deux fonctions : le check repasse au vert et affiche la valeur.
    (repo / "tests" / "test_alertes.py").write_text(TESTS_OK, "utf-8")
    _commit(repo, git_path, "Teste les alertes")
    accepted = _gate(repo, base, tmp_path)
    assert accepted.state == "success", accepted.output
    summary = _summary(accepted)
    assert summary.startswith("Couverture du nouveau code ") and summary.endswith(
        " % · seuil 80 % · ✓"
    )
    assert int(summary.split()[4]) >= THRESHOLD
    # Au vert, la quality gate remesure aussi après un nouveau test partiel : le seuil ne bouge pas.
    layout = _layout(tmp_path / "pr", accepted.findings)
    assert _status(layout) == "passed"


@pytest.mark.slow
def test_les_contournements_de_la_couverture_ne_font_pas_passer_la_quality_gate(
    tmp_path: Path, git_path: Path, real_tools: list[str]
) -> None:
    """Leçon 6.2 : seul le geste enseigné (tester le code) fait passer le check."""
    repo, base = _scenario_repo(tmp_path, git_path)
    alertes = repo / "src" / "inventory" / "alertes.py"
    source = alertes.read_text("utf-8")
    # 1. Exclure le fichier de la mesure : `[tool.coverage]`, `.coveragerc`, `setup.cfg`, `tox.ini`.
    pyproject = repo / "pyproject.toml"
    pyproject.write_text(
        pyproject.read_text("utf-8")
        + '\n[tool.coverage.run]\nomit = ["src/*"]\n[tool.coverage.report]\nfail_under = 0\n'
        + '\n[tool.diff_cover]\nfail_under = 0\nexclude = ["src/*"]\n',
        "utf-8",
    )
    (repo / ".coveragerc").write_text("[run]\nomit = src/*\n", "utf-8")
    (repo / "setup.cfg").write_text("[coverage:run]\nomit = src/*\n[diff_cover]\nfail_under=0\n")
    (repo / "tox.ini").write_text("[coverage:run]\nomit = src/*\n", "utf-8")
    # 2. Désactiver la mesure par les options de pytest du dépôt.
    pyproject.write_text(
        pyproject.read_text("utf-8").replace(
            "[tool.pytest.ini_options]", '[tool.pytest.ini_options]\naddopts = "--no-cov -p no:cov"'
        ),
        "utf-8",
    )
    # 3. Un rapport de couverture parfait déposé dans le dépôt.
    (repo / "coverage.xml").write_text(
        '<?xml version="1.0"?><coverage line-rate="1"><packages/></coverage>', "utf-8"
    )
    _commit(repo, git_path, "Contourne la couverture")
    result = _gate(repo, base, tmp_path)
    assert result.state == "failure", result.output
    assert _summary(result) == "Couverture du nouveau code 0 % · seuil 80 % · ✗"
    # 4. `# pragma: no cover` sur chaque fonction : ignoré, les lignes restent non couvertes.
    alertes.write_text(
        source.replace("-> int:", "-> int:  # pragma: no cover").replace(
            "-> list[str]:", "-> list[str]:  # pragma: no cover"
        ),
        "utf-8",
    )
    _commit(repo, git_path, "Pragma")
    assert _gate(repo, base, tmp_path).state == "failure"
    # 5. Supprimer le module : le check est vert mais ne mesure plus rien, l'étape ne valide pas.
    alertes.unlink()
    _commit(repo, git_path, "Supprime le module")
    removed = _gate(repo, base, tmp_path)
    assert removed.state == "success", removed.output
    assert _summary(removed).startswith("Couverture du nouveau code aucune ligne à mesurer")
    assert _status(_layout(tmp_path / "pr", removed.findings)) == "pending"


@pytest.mark.slow
def test_des_tests_qui_echouent_bloquent_la_quality_gate_sans_mesure(
    tmp_path: Path, git_path: Path, real_tools: list[str]
) -> None:
    repo, base = _scenario_repo(tmp_path, git_path)
    (repo / "tests" / "test_alertes.py").write_text(
        "def test_casse() -> None:\n    assert False\n", "utf-8"
    )
    _commit(repo, git_path, "Test cassé")
    result = _gate(repo, base, tmp_path)
    assert result.state == "failure"
    assert [f.rule_id for f in result.findings] == [ci.BEFORE_FAILED_RULE]
    assert "pytest a échoué" in result.findings[0].message_text and "assert False" in result.output


@pytest.mark.slow
def test_le_vrai_bandit_ignore_un_fichier_bandit_depose_par_l_apprenant(
    tmp_path: Path, git_path: Path, real_tools: list[str]
) -> None:
    repo, base = _scenario_repo(tmp_path, git_path)
    (repo / "src" / "inventory" / "seuil.py").write_text(
        "def lire(texte: str) -> int:\n    return eval(texte)\n", "utf-8"
    )
    assert _run(BANDIT, repo, base, tmp_path).state == "failure"
    # `src/.bandit` (skips) : bandit le lirait sans `--ini` ; avec `--ini`, il est ignoré.
    (repo / "src" / ".bandit").write_text("[bandit]\nskips = B307\n", "utf-8")
    (repo / ".bandit").write_text("[bandit]\nskips = B307\n", "utf-8")
    (repo / "pyproject.toml").write_text(
        (repo / "pyproject.toml").read_text("utf-8") + '\n[tool.bandit]\nskips = ["B307"]\n',
        "utf-8",
    )
    result = _run(BANDIT, repo, base, tmp_path)
    assert result.state == "failure", result.output
    assert [f.rule_id for f in result.findings] == ["B307"]
    # Le code corrigé passe : le réglage hors de l'arbre n'écarte aucun test, il n'en ajoute pas.
    (repo / "src" / "inventory" / "seuil.py").write_text(
        "def lire(texte: str) -> int:\n    return int(texte)\n", "utf-8"
    )
    assert _run(BANDIT, repo, base, tmp_path).state == "success"


@pytest.mark.slow
def test_uv_lock_check_refuse_un_pyproject_sans_verrou_a_jour(
    tmp_path: Path, git_path: Path, real_tools: list[str]
) -> None:
    """Un pyproject.toml modifié sans uv.lock à jour fait échouer le pipeline (`uv lock --check`),
    même quand `uv sync --frozen` s'en accommode."""
    if shutil.which("uv") is None:
        pytest.skip("uv n'est pas dans le PATH")
    repo, base = _scenario_repo(tmp_path, git_path)
    assert _run(UV_LOCK, repo, base, tmp_path).state == "success"  # le gabarit est cohérent
    pyproject = repo / "pyproject.toml"
    text = pyproject.read_text("utf-8")
    pyproject.write_text(
        text.replace('requires-python = ">=3.14,<3.15"', 'requires-python = ">=3.14,<3.15"\n#')
        .replace("pytest==9.1.1", "pytest==9.1.0"),
        "utf-8",
    )
    stale = _run(UV_LOCK, repo, base, tmp_path)
    assert stale.state == "failure", stale.output
    assert stale.output.strip()  # la sortie de uv reste affichée, verbatim


# ------------------------------------------------------------------ performance du pipeline
BUDGET_WARN_S = 90.0
BUDGET_FAIL_S = 180.0
"""Alerte au-delà de 90 s, échec au-delà de 180 s, sur chacun des trois OS (story 8.4). Le budget
de 45 s se mesure sur le poste de référence d'Anaël, avant la release v0.2.0 (story 9.5)."""


@pytest.fixture(scope="module")
def osv_url(tmp_path_factory: pytest.TempPathFactory) -> Iterator[str]:
    pytest.importorskip("pip_audit")
    inst = cli.start_instance(Settings(data_dir=tmp_path_factory.mktemp("osv")))
    try:
        yield Settings().osv_url(inst.port)
    finally:
        inst.stop()


@pytest.mark.slow
def test_le_pipeline_complet_tient_dans_le_budget_de_temps(
    tmp_path: Path, git_path: Path, osv_url: str, real_tools: list[str]
) -> None:
    """Le pipeline des sept jobs, avec les vrais outils, sur l'arbre du scénario une fois testé :
    alerte (avertissement pytest) au-delà de 90 s, échec au-delà de 180 s."""
    repo, base = _scenario_repo(tmp_path, git_path)
    (repo / "tests" / "test_alertes.py").write_text(TESTS_OK, "utf-8")
    _commit(repo, git_path, "Teste les alertes")
    started = time.monotonic()
    states: dict[str, str] = {}
    for job in PIPELINE.jobs:
        if job.job_id in real_tools or (job.tool in real_tools):
            continue  # outil absent de ce poste (gitleaks hors CI) : le temps mesuré est partiel
        if job.job_id == "uv_lock" and shutil.which("uv") is None:
            continue
        result = _run(job, repo, base, tmp_path, osv_url=osv_url)
        states[job.job_id] = result.state
    elapsed = time.monotonic() - started
    assert set(states.values()) == {"success"}, states
    if elapsed > BUDGET_WARN_S:
        warnings.warn(
            f"Pipeline complet : {elapsed:.0f} s, au-delà de l'alerte de {BUDGET_WARN_S:.0f} s "
            f"(budget cible : 45 s sur le poste de référence).",
            stacklevel=1,
        )
    assert elapsed <= BUDGET_FAIL_S, f"{elapsed:.0f} s > {BUDGET_FAIL_S:.0f} s : {states}"


@pytest.mark.slow
def test_le_scenario_dependance_vulnerable_echoue_au_verrou_puis_passe_apres_correction(
    tmp_path: Path, git_path: Path, real_tools: list[str]
) -> None:
    """Un pyproject.toml à jinja2 3.1.2 ne correspond pas au verrou (3.1.6) ; la correction du
    scénario (3.1.6 dans pyproject.toml et requirements.txt) remet `uv_lock` au vert."""
    if shutil.which("uv") is None:
        pytest.skip("uv n'est pas dans le PATH")
    prepared = prepare_workspace(
        load_scenario(SETTINGS.scenarios_path() / "dependance-vulnerable.A.yaml", SETTINGS),
        "no_ai",
        settings=Settings(data_dir=tmp_path / "data"),
        git_path=git_path,
    )
    repo = prepared.layout.repo
    assert _run(UV_LOCK, repo, SHA, tmp_path).state == "failure"
    for name in ("pyproject.toml", "requirements.txt"):
        path = repo / name
        path.write_text(path.read_text("utf-8").replace("jinja2==3.1.2", "jinja2==3.1.6"), "utf-8")
    fixed = _run(UV_LOCK, repo, SHA, tmp_path)
    assert fixed.state == "success", fixed.output
    # Corriger seulement requirements.txt ne suffit pas : pyproject.toml reste en désaccord.
    path = repo / "pyproject.toml"
    path.write_text(path.read_text("utf-8").replace("jinja2==3.1.6", "jinja2==3.1.2"), "utf-8")
    assert _run(UV_LOCK, repo, SHA, tmp_path).state == "failure"


# ------------------------------------------------------------------ l'op de setup replace_in_file
def test_l_op_replace_in_file_remplace_un_texte_present_une_seule_fois(tmp_path: Path) -> None:
    from types import SimpleNamespace

    from wavedevsecops.scenarios import SetupError
    from wavedevsecops.scenarios.ops import REGISTRY, replace_in_file

    assert "replace_in_file" in REGISTRY
    ctx = SimpleNamespace(layout=SimpleNamespace(repo=tmp_path))
    (tmp_path / "f.txt").write_text("a\nb\na\n", "utf-8")

    def run(old: str, new: str) -> None:
        replace_in_file.apply(
            replace_in_file.Args(op="replace_in_file", path="f.txt", old=old, new=new),
            ctx,  # type: ignore[arg-type]
        )

    run("b\n", "c\n")
    assert (tmp_path / "f.txt").read_text("utf-8") == "a\nc\na\n"
    with pytest.raises(SetupError):
        run("a\n", "x\n")  # deux fois : ambigu
    with pytest.raises(SetupError):
        run("absent", "x")
    with pytest.raises(ValueError):
        replace_in_file.Args(op="replace_in_file", path="../f.txt", old="a", new="b")
