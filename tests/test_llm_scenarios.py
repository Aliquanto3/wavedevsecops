# ruff: noqa: F811
"""Scénarios du parcours LLM (Story 8.6) : clé d'API en dur (gitleaks), config qui enverrait les
données au cloud (test du gabarit dans le check pytest) et injection de prompt nommée dans la
revue humaine.

Les tests lents lancent les vrais outils de l'environnement de développement sur l'arbre préparé
par chaque scénario ; gitleaks seulement s'il est posé dans `WDS_EXERCISE_DATA` (la CI le fournit).
Aucun appel réseau : la config cloud n'est jamais appelée (AD-13).
"""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import pytest
import yaml
from test_quality_gate import _commit, _run, real_tools  # noqa: F401  (fixture)

from wavedevsecops import ci
from wavedevsecops.config import Settings
from wavedevsecops.contracts import RepoState
from wavedevsecops.engine import prepare_workspace
from wavedevsecops.projections import EXPLAIN_REFS
from wavedevsecops.scenarios import load_scenario
from wavedevsecops.scenarios.order import STATION_ORDER
from wavedevsecops.scenarios.steps import pr_state, repo_state
from wavedevsecops.scenarios.steps._base import StepContext
from wavedevsecops.web.explanations import load_explanations

SETTINGS = Settings()
CLE = SETTINGS.scenarios_path() / "cle-api-en-dur.A.yaml"
CLOUD = SETTINGS.scenarios_path() / "donnees-vers-le-cloud.A.yaml"
PIPELINE = ci.load_pipeline(SETTINGS)
LLM_CONFIG = "src/inventory/llm_config.py"
KEY = "m9Kq2LmT7vRb4WnZ8cYd3HsJ6pFa1GeU5xQz"
SHA = "a" * 40


def _scenario(path: Path):
    return load_scenario(path, SETTINGS, explain_keys=EXPLAIN_REFS).scenario


# ------------------------------------------------------------------ contrat des scénarios
@pytest.mark.parametrize(
    ("path", "scenario_id", "steps"),
    [
        (
            CLE,
            "cle-api-en-dur",
            [
                "pousser_feature",
                "ouvrir_pr",
                "lire_le_blocage",
                "retirer_la_cle",
                "sans_exception",
                "rester_au_vert",
            ],
        ),
        (
            CLOUD,
            "donnees-vers-le-cloud",
            [
                "pousser_feature",
                "ouvrir_pr",
                "lire_le_blocage",
                "revenir_a_la_config_locale",
                "voir_le_vert",
            ],
        ),
    ],
)
def test_les_scenarios_declarent_le_parcours_llm_et_la_station_3(
    path: Path, scenario_id: str, steps: list[str]
) -> None:
    scenario = _scenario(path)
    assert (scenario.scenario_id, scenario.mode, scenario.station) == (scenario_id, "A", 3)
    assert scenario.pipeline and list(scenario.tracks) == ["llm"]
    assert scenario_id in STATION_ORDER
    assert STATION_ORDER.index(scenario_id) > STATION_ORDER.index("couverture-sous-le-seuil")
    assert [s.step_id for s in scenario.steps] == steps
    for step in scenario.steps:
        if step.hints:  # le premier palier ne donne pas la réponse
            lead = step.hints.lead_text
            assert "LLM_API_KEY" not in lead and "127.0.0.1" not in lead
            assert "os.environ" not in lead and "checkout" not in lead


def test_chaque_scenario_de_station_exige_son_check_et_la_protection_de_main() -> None:
    for path, job in ((CLE, "gitleaks"), (CLOUD, "pytest")):
        ops = _scenario(path).setup
        (protection,) = [op for op in ops if op.op == "set_protection"]
        assert list(protection.required_checks) == [job]


def test_le_job_gitleaks_lit_ses_reglages_hors_de_l_arbre() -> None:
    job = PIPELINE.job("gitleaks")
    assert job is not None
    for argv in (job.human, job.machine[0].argv):
        assert "--ignore-gitleaks-allow" in argv
        assert argv[argv.index("--config") + 1] == "{config}/gitleaks.toml"
    config = SETTINGS.ci_config_path() / "gitleaks.toml"
    data = config.read_text("utf-8")
    assert "useDefault = true" in data and "allowlist" not in data.replace("`[allowlist]`", "")


def test_le_gabarit_llm_garde_la_config_par_des_tests() -> None:
    """Le test dont dépend le scénario « données vers le cloud » existe dans le gabarit."""
    text = (SETTINGS.content_path() / "exercise" / "llm" / "tests" / "test_llm.py").read_text(
        "utf-8"
    )
    guard = yaml.safe_load(CLOUD.read_text("utf-8"))["steps"][3]["expect"]["tree"]["contains"]
    for item in guard:
        if item["path"] == "tests/test_llm.py":
            assert item["text"] in text.replace("\r\n", "\n")


def test_la_revue_humaine_nomme_l_injection_de_prompt() -> None:
    catalogue = load_explanations(SETTINGS)
    assert catalogue is not None
    entry = catalogue.entries["remote.review_llm"]
    assert "injection de prompt" in entry.body_text and "revue humaine" in entry.body_text
    sentences = [s for s in re.split(r"(?<=[.!?])\s+", entry.body_text.strip()) if s]
    assert len(sentences) <= 3
    # Sans scénario qui la déclenche : aucun scénario du catalogue ne parle d'injection.
    for path in SETTINGS.scenarios_path().glob("*.yaml"):
        assert "injection" not in path.read_text("utf-8").lower(), path.name


# ------------------------------------------------------------------ étapes de PR
def _checks_layout(tmp_path: Path, states: dict[str, str], findings: dict[str, list[str]]):
    from wavedevsecops import github_sim
    from wavedevsecops.contracts.github import Check, GithubState, PullRequest
    from wavedevsecops.contracts.github import Finding as GhFinding
    from wavedevsecops.wsfs import Layout

    layout = Layout(tmp_path / "ws")
    layout.root.mkdir(parents=True)
    checks = [
        Check(
            job_id=job,
            head_sha=SHA,
            base_sha=SHA,
            state=state,  # type: ignore[arg-type]
            findings=[GhFinding(rule_id=r, severity="error", message_text="m") for r in rules],
        )
        for job, state in states.items()
        for rules in [findings.get(job, [])]
    ]
    pr = PullRequest(
        number=1, head="feature", base="main", head_sha=SHA, base_sha=SHA, checks=checks
    )
    github_sim._save(layout, GithubState(pulls=[pr], next_number=2))
    return layout


def _pr_status(path: Path, step_id: str, layout) -> str:
    (step,) = [s for s in _scenario(path).steps if s.step_id == step_id]
    assert isinstance(step, pr_state.Args)
    return pr_state.check(None, StepContext(step=step, layout=layout)).status


def test_l_etape_cle_exige_la_regle_de_gitleaks_pas_un_echec_quelconque(tmp_path: Path) -> None:
    ok = _checks_layout(tmp_path / "a", {"gitleaks": "failure"}, {"gitleaks": ["generic-api-key"]})
    assert _pr_status(CLE, "lire_le_blocage", ok) == "passed"
    other = _checks_layout(tmp_path / "b", {"gitleaks": "failure"}, {"gitleaks": ["autre"]})
    assert _pr_status(CLE, "lire_le_blocage", other) == "pending"


def test_l_etape_cle_attend_gitleaks_et_pytest_verts(tmp_path: Path) -> None:
    both = _checks_layout(tmp_path / "a", {"gitleaks": "success", "pytest": "success"}, {})
    assert _pr_status(CLE, "retirer_la_cle", both) == "passed"
    # Retirer la clé en cassant le code ne valide pas l'étape.
    broken = _checks_layout(tmp_path / "b", {"gitleaks": "success", "pytest": "failure"}, {})
    assert _pr_status(CLE, "retirer_la_cle", broken) == "pending"
    still = _checks_layout(tmp_path / "c", {"gitleaks": "failure", "pytest": "success"}, {})
    assert _pr_status(CLE, "retirer_la_cle", still) == "pending"


def test_le_scenario_cle_finit_sur_un_check_vert_sans_exception(tmp_path: Path) -> None:
    """Un vert obtenu par un `.gitleaksignore`, retiré à l'étape `sans_exception`, repasse au
    rouge : la dernière étape attend de nouveau gitleaks et pytest verts sur les SHA courants."""
    steps = [s.step_id for s in _scenario(CLE).steps]
    assert steps.index("rester_au_vert") == steps.index("sans_exception") + 1 == len(steps) - 1
    red = _checks_layout(tmp_path / "a", {"gitleaks": "failure", "pytest": "success"}, {})
    assert _pr_status(CLE, "rester_au_vert", red) == "pending"
    green = _checks_layout(tmp_path / "b", {"gitleaks": "success", "pytest": "success"}, {})
    assert _pr_status(CLE, "rester_au_vert", green) == "passed"


def test_l_etape_cloud_exige_les_deux_tests_de_config_en_echec(tmp_path: Path) -> None:
    names = ["test_default_endpoint_is_local_ollama", "test_allowed_endpoints_are_loopback_only"]
    ok = _checks_layout(tmp_path / "a", {"pytest": "failure"}, {"pytest": names})
    assert _pr_status(CLOUD, "lire_le_blocage", ok) == "passed"
    # Un test cassé sans rapport avec la config n'est pas le blocage attendu.
    other = _checks_layout(tmp_path / "b", {"pytest": "failure"}, {"pytest": ["test_stock"]})
    assert _pr_status(CLOUD, "lire_le_blocage", other) == "pending"
    green = _checks_layout(tmp_path / "c", {"pytest": "success"}, {})
    assert _pr_status(CLOUD, "voir_le_vert", green) == "passed"


# ------------------------------------------------------------------ arbres préparés
def _prepared(tmp_path: Path, git_path: Path, path: Path) -> Path:
    prepared = prepare_workspace(
        load_scenario(path, SETTINGS),
        "llm",
        settings=Settings(data_dir=tmp_path / "data"),
        git_path=git_path,
    )
    return prepared.layout.repo


def _key_line(repo: Path) -> int:
    lines = (repo / LLM_CONFIG).read_text("utf-8").splitlines()
    return next(n for n, line in enumerate(lines, 1) if line.startswith("API_KEY"))


def _guard(path: Path, step_id: str, repo: Path) -> str:
    """Verdict de l'étape `repo_state` pour cet arbre, poussé et sans changement en attente."""
    (step,) = [s for s in _scenario(path).steps if s.step_id == step_id]
    assert isinstance(step, repo_state.Args)
    files = sorted(
        p.relative_to(repo).as_posix()
        for p in repo.rglob("*")
        if p.is_file() and ".git" not in p.relative_to(repo).parts
    )
    state = RepoState.model_validate(
        {
            "head": {"detached": False, "ref": "refs/heads/feature", "commit": SHA},
            "commits": [
                {
                    "sha": SHA,
                    "parents": [],
                    "tree": "d" * 40,
                    "author_name": "x",
                    "author_email": "x@x",
                    "author_date": "2026-01-01T00:00:00+00:00",
                    "committer_name": "x",
                    "committer_email": "x@x",
                    "committer_date": "2026-01-01T00:00:00+00:00",
                    "committer_ts": 1,
                    "subject": "s",
                    "message": "s",
                }
            ],
            "refs": [
                {
                    "name": name,
                    "kind": kind,
                    "short_name": short,
                    "target": SHA,
                    "commit": SHA,
                }
                for name, kind, short in (
                    ("refs/heads/feature", "branch", "feature"),
                    ("refs/remotes/origin/feature", "remote", "origin/feature"),
                )
            ],
            "worktree": files,
        }
    )
    from types import SimpleNamespace

    ctx = StepContext(step, {}, None, layout=SimpleNamespace(repo=repo))
    return repo_state.check(state, ctx).status


def test_les_fichiers_du_scenario_cle_sont_ceux_de_l_exercice(
    tmp_path: Path, git_path: Path
) -> None:
    repo = _prepared(tmp_path, git_path, CLE)
    assert f'API_KEY = "{KEY}"' in (repo / LLM_CONFIG).read_text("utf-8")
    assert "AUTH_HEADERS" in (repo / LLM_CONFIG).read_text("utf-8")
    assert not (repo / ".gitleaksignore").exists()
    assert _guard(CLE, "sans_exception", repo) == "passed"
    (repo / ".gitleaksignore").write_text(f"{LLM_CONFIG}:generic-api-key:5\n", "utf-8")
    assert _guard(CLE, "sans_exception", repo) != "passed"


def test_les_fichiers_du_scenario_cloud_visent_un_service_distant(
    tmp_path: Path, git_path: Path
) -> None:
    repo = _prepared(tmp_path, git_path, CLOUD)
    toml = (repo / "llm.toml").read_text("utf-8")
    assert "api.llm-cloud.example" in toml and "127.0.0.1" not in toml
    assert _guard(CLOUD, "revenir_a_la_config_locale", repo) != "passed"
    toml_main = (SETTINGS.content_path() / "exercise" / "llm" / "llm.toml").read_text("utf-8")
    (repo / "llm.toml").write_text(toml_main, "utf-8")
    assert _guard(CLOUD, "revenir_a_la_config_locale", repo) == "passed"


def test_les_contournements_du_test_de_config_ne_valident_pas_l_etape(
    tmp_path: Path, git_path: Path
) -> None:
    """Leçon 6.2 : un check vert obtenu en supprimant, vidant ou assouplissant le test n'est pas
    la config locale que l'étape attend."""
    repo = _prepared(tmp_path, git_path, CLOUD)
    local = (SETTINGS.content_path() / "exercise" / "llm" / "llm.toml").read_text("utf-8")
    tests = repo / "tests" / "test_llm.py"
    original = tests.read_text("utf-8")
    (repo / "llm.toml").write_text(local, "utf-8")
    assert _guard(CLOUD, "revenir_a_la_config_locale", repo) == "passed"
    # Config cloud gardée, test supprimé.
    (repo / "llm.toml").write_text("base_url = 'https://x.example/v1'\n", "utf-8")
    tests.unlink()
    assert _guard(CLOUD, "revenir_a_la_config_locale", repo) != "passed"
    # Config locale restaurée mais test supprimé, vidé, ou assoupli : l'étape reste ouverte.
    (repo / "llm.toml").write_text(local, "utf-8")
    assert _guard(CLOUD, "revenir_a_la_config_locale", repo) != "passed"  # test supprimé
    for weakened in (
        original.replace(
            'assert config.base_url == "http://127.0.0.1:11434/v1"', "assert config.base_url"
        ),
        original.replace(
            'assert urlsplit(url).hostname in {"127.0.0.1", "localhost", "::1"}, url', "pass"
        ),
        original.replace("def test_default_endpoint", "def _default_endpoint"),
        original.replace("    assert config.base_url ==", "    # assert config.base_url ==", 1),
        # Revue : un décorateur, même séparé par des lignes vides, ou un `return` en tête.
        original.replace(
            "def test_default_endpoint", "@pytest.mark.skip\ndef test_default_endpoint"
        ),
        original.replace(
            "def test_allowed_endpoints", "@pytest.mark.xfail\n\n\ndef test_allowed_endpoints"
        ),
        original.replace(
            "load_config\n\n\ndef test_default",
            "load_config\n\n\n@pytest.mark.skip\n\n\ndef test_default",
        ),
        original.replace(
            "    config = load_config()\n    assert config.base_url",
            "    return\n    config = load_config()\n    assert config.base_url",
        ),
    ):
        assert weakened != original
        tests.write_text(weakened, "utf-8")
        assert _guard(CLOUD, "revenir_a_la_config_locale", repo) != "passed", weakened
    tests.write_text(original, "utf-8")
    assert _guard(CLOUD, "revenir_a_la_config_locale", repo) == "passed"
    # Revue : la valeur locale laissée en commentaire, la config cloud active, ne compte pas.
    commented = (
        "# Configuration du modèle de langage.\n"
        '# base_url = "http://127.0.0.1:11434/v1"\n'
        '# allowed_endpoints = ["http://127.0.0.1:11434/v1"]\n'
        'base_url = "https://api.llm-cloud.example/v1"\n'
        'model = "m"\ntimeout_seconds = 60\n'
        'allowed_endpoints = ["https://api.llm-cloud.example/v1"]\n'
    )
    (repo / "llm.toml").write_text(commented, "utf-8")
    assert _guard(CLOUD, "revenir_a_la_config_locale", repo) != "passed"


# ------------------------------------------------------------------ vrais outils
def _git(repo: Path, git_path: Path, *args: str) -> None:
    subprocess.run(
        [str(git_path), "-c", "user.name=T", "-c", "user.email=t@example.invalid", *args],
        cwd=repo,
        check=True,
        capture_output=True,
    )


def _job(job_id: str) -> ci.Job:
    job = PIPELINE.job(job_id)
    assert job is not None
    return job


def _rules(result: ci.JobResult) -> list[str]:
    return [f.rule_id for f in result.findings]


def _gitleaks_or_skip(real_tools: list[str]) -> None:
    if "gitleaks" in real_tools:
        pytest.skip("gitleaks n'est pas posé sur ce poste (WDS_EXERCISE_DATA)")


@pytest.mark.slow
def test_le_vrai_gitleaks_refuse_la_cle_puis_accepte_la_lecture_dans_l_environnement(
    tmp_path: Path,
    git_path: Path,
    real_tools: list[str],
) -> None:
    _gitleaks_or_skip(real_tools)
    repo = _prepared(tmp_path, git_path, CLE)
    refused = _run(_job("gitleaks"), repo, SHA, tmp_path)
    assert refused.state == "failure", refused.output
    (found,) = refused.findings
    assert (found.rule_id, found.path) == ("generic-api-key", LLM_CONFIG)
    assert KEY not in refused.output  # `--redact` : la valeur ne s'affiche pas
    # Le code et les tests restent verts avec la clé (seul gitleaks bloque).
    assert _run(_job("pytest"), repo, SHA, tmp_path).state == "success"
    # La correction de la solution de l'étape.
    path = repo / LLM_CONFIG
    text = path.read_text("utf-8").replace(
        f'API_KEY = "{KEY}"', 'API_KEY = os.environ.get("LLM_API_KEY", "")'
    )
    path.write_text(text.replace("import tomllib", "import os\nimport tomllib"), "utf-8")
    fixed = _run(_job("gitleaks"), repo, SHA, tmp_path)
    assert fixed.state == "success", fixed.output
    assert _run(_job("pytest"), repo, SHA, tmp_path).state == "success"
    assert _run(_job("ruff"), repo, SHA, tmp_path).state == "success"


@pytest.mark.slow
@pytest.mark.parametrize(
    "bypass",
    [
        "allow_comment",
        "gitleaks_toml_allowlist",
        "key_in_other_file",
        "key_in_toml",
    ],
)
def test_les_contournements_de_gitleaks_ne_font_pas_passer_le_check(
    tmp_path: Path,
    git_path: Path,
    real_tools: list[str],
    bypass: str,
) -> None:
    _gitleaks_or_skip(real_tools)
    repo = _prepared(tmp_path, git_path, CLE)
    path = repo / LLM_CONFIG
    if bypass == "allow_comment":
        path.write_text(
            path.read_text("utf-8").replace(KEY + '"', KEY + '"  # gitleaks:allow'), "utf-8"
        )
    elif bypass == "gitleaks_toml_allowlist":
        (repo / ".gitleaks.toml").write_text(
            f'[allowlist]\npaths = ["{LLM_CONFIG}"]\nregexes = ["sk-.*"]\n', "utf-8"
        )
    elif bypass == "key_in_other_file":
        text = path.read_text("utf-8").replace(f'API_KEY = "{KEY}"', 'API_KEY = ""')
        path.write_text(text, "utf-8")
        (repo / "src" / "inventory" / "secrets_.py").write_text(f'KEY = "{KEY}"\n', "utf-8")
    else:
        text = path.read_text("utf-8").replace(f'API_KEY = "{KEY}"', 'API_KEY = ""')
        path.write_text(text, "utf-8")
        (repo / "llm.toml").write_text(
            (repo / "llm.toml").read_text("utf-8") + f'api_key = "{KEY}"\n', "utf-8"
        )
    result = _run(_job("gitleaks"), repo, SHA, tmp_path)
    assert result.state == "failure", (bypass, result.output)
    assert "generic-api-key" in _rules(result)


@pytest.mark.slow
def test_gitleaksignore_fait_taire_gitleaks_mais_pas_l_etape(
    tmp_path: Path,
    git_path: Path,
    real_tools: list[str],
) -> None:
    """gitleaks lit encore `.gitleaksignore` à la racine : l'étape finale le refuse."""
    _gitleaks_or_skip(real_tools)
    repo = _prepared(tmp_path, git_path, CLE)
    fingerprint = f"{LLM_CONFIG}:generic-api-key:{_key_line(repo)}\n"
    (repo / ".gitleaksignore").write_text(fingerprint, "utf-8")
    assert _run(_job("gitleaks"), repo, SHA, tmp_path).state == "success"
    assert _guard(CLE, "sans_exception", repo) != "passed"
    (repo / ".gitleaksignore").unlink()
    assert _run(_job("gitleaks"), repo, SHA, tmp_path).state == "failure"
    assert _guard(CLE, "sans_exception", repo) == "passed"


@pytest.mark.slow
def test_le_vrai_pytest_refuse_la_config_cloud_puis_accepte_la_config_locale(
    tmp_path: Path,
    git_path: Path,
    real_tools: list[str],
) -> None:
    repo = _prepared(tmp_path, git_path, CLOUD)
    refused = _run(_job("pytest"), repo, SHA, tmp_path)
    assert refused.state == "failure", refused.output
    assert sorted(_rules(refused)) == [
        "test_allowed_endpoints_are_loopback_only",
        "test_default_endpoint_is_local_ollama",
    ]
    assert {f.path for f in refused.findings} == {"tests/test_llm.py"}
    # La config cloud n'est jamais appelée : aucune erreur de réseau dans la sortie.
    assert "ConnectError" not in refused.output and "Name or service" not in refused.output
    local = (SETTINGS.content_path() / "exercise" / "llm" / "llm.toml").read_text("utf-8")
    (repo / "llm.toml").write_text(local, "utf-8")
    accepted = _run(_job("pytest"), repo, SHA, tmp_path)
    assert accepted.state == "success", accepted.output


@pytest.mark.slow
def test_une_liste_autorisee_elargie_au_cloud_echoue_aussi(
    tmp_path: Path,
    git_path: Path,
    real_tools: list[str],
) -> None:
    """Défaut local gardé, mais un endpoint distant ajouté à la liste : le test de liste échoue."""
    repo = _prepared(tmp_path, git_path, CLOUD)
    local = (SETTINGS.content_path() / "exercise" / "llm" / "llm.toml").read_text("utf-8")
    (repo / "llm.toml").write_text(
        local.replace(
            'allowed_endpoints = ["http://127.0.0.1:11434/v1"]',
            'allowed_endpoints = ["http://127.0.0.1:11434/v1", "https://api.llm-cloud.example/v1"]',
        ),
        "utf-8",
    )
    result = _run(_job("pytest"), repo, SHA, tmp_path)
    assert result.state == "failure"
    assert _rules(result) == ["test_allowed_endpoints_are_loopback_only"]


@pytest.mark.slow
@pytest.mark.parametrize("which", ["cle", "cloud"])
def test_les_etats_corriges_passent_les_sept_jobs_du_pipeline(
    tmp_path: Path,
    git_path: Path,
    real_tools: list[str],
    which: str,
) -> None:
    """Le correctif de chaque scénario laisse tous les autres checks verts (porte de fusion à
    sept jobs, quality gate comprise) ; gitleaks et uv seulement s'ils sont posés."""
    repo = _prepared(tmp_path, git_path, CLE if which == "cle" else CLOUD)
    base = subprocess.run(
        [str(git_path), "rev-parse", "HEAD~1"], cwd=repo, capture_output=True, text=True, check=True
    ).stdout.strip()
    if which == "cle":
        path = repo / LLM_CONFIG
        text = path.read_text("utf-8").replace(
            f'API_KEY = "{KEY}"', 'API_KEY = os.environ.get("LLM_API_KEY", "")'
        )
        path.write_text(text.replace("import tomllib", "import os\nimport tomllib"), "utf-8")
    else:
        local = (SETTINGS.content_path() / "exercise" / "llm" / "llm.toml").read_text("utf-8")
        (repo / "llm.toml").write_text(local, "utf-8")
    _commit(repo, git_path, "Corrige")

    states: dict[str, str] = {}
    outs: dict = {}
    for job in PIPELINE.jobs:
        if job.tool in real_tools or job.job_id in real_tools:
            continue
        if job.job_id == "uv_lock" and shutil.which("uv") is None:
            continue
        if job.job_id == "pip_audit":
            continue  # le point OSV local est vérifié par test_quality_gate
        outs[job.job_id] = _run(job, repo, base, tmp_path)
        states[job.job_id] = outs[job.job_id].state
    assert set(states.values()) == {"success"}, (
        states,
        [(j, r.output[-1500:]) for j, r in outs.items() if r.state != "success"],
    )
    assert "quality_gate" in states and "ruff" in states
