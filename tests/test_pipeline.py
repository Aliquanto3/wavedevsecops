"""Pipeline simulé sur chaque PR (Story 7.4) : contrat de `content/pipeline.yaml`, runs liés
au SHA, résultats par la file, annulation, environnement du run, erreur de l'outil, relance
(AD-1, AD-8, AD-10, AD-12).

Les outils sont remplacés par de petits Python qui impriment la sortie voulue (comme
`test_terminal_tools.py`) ; les vrais ruff, pytest et gitleaks tournent dans
`test_vrais_outils_dans_le_pipeline` quand le cache uv des gabarits est préchargé
(`WDS_EXERCISE_UV=1`, CI).
"""

from __future__ import annotations

import json
import os
import shutil
import sys
import time
import warnings
from collections.abc import Callable, Iterator
from pathlib import Path

import pytest
import yaml
from test_procs_spawn import alive, wait_dead

from wavedevsecops import ci, github_sim, procs, toolrun
from wavedevsecops.ci import findings as parsers
from wavedevsecops.config import Settings
from wavedevsecops.contracts.github import PullRequest
from wavedevsecops.engine import WorkspaceEngine, WorkspaceManager, prepare_workspace
from wavedevsecops.engine import pipeline as engine_pipeline
from wavedevsecops.engine.intents import build_operation
from wavedevsecops.engine.operations import Operation, OperationRefused, StaleOperation
from wavedevsecops.events import Envelope, Kind
from wavedevsecops.gitio import Git
from wavedevsecops.registry import load_registry
from wavedevsecops.scenarios import load_scenario
from wavedevsecops.wsfs import Layout

ROOT = Path(__file__).resolve().parent.parent
CONTENT = ROOT / "content"
WAIT = 60.0
PYTHON = getattr(sys, "_base_executable", sys.executable)
SHA = "a" * 40
SHA2 = "b" * 40

FEATURE = "src/inventory/rapport.py"


# ------------------------------------------------------------------ contrat du pipeline
def test_le_pipeline_declare_ruff_pytest_gitleaks_avec_leur_contrat() -> None:
    pipeline = ci.load_pipeline(Settings())
    assert pipeline.job_ids == ["ruff", "pytest", "gitleaks", "bandit", "pip_audit"]
    registry = load_registry(settings=Settings())
    chain = yaml.safe_load((CONTENT / "chain.yaml").read_text("utf-8"))
    barriers = {
        b["id"]
        for station in chain["stations"]
        for b in station.get("barriers", [])
        if isinstance(b, dict) and "id" in b
    }
    for job in pipeline.jobs:
        assert job.label_text and job.human and job.machine and job.required
        assert registry.get(job.tool)  # résolu par le registre (AD-16)
        assert job.barrier in barriers, job.barrier
        assert job.exit_codes.meaning(0) == "success"
        assert job.exit_codes.meaning(None) == "error"
    gitleaks = pipeline.job("gitleaks")
    assert gitleaks is not None
    assert gitleaks.exit_codes.meaning(3) == "failure" and gitleaks.exit_codes.meaning(1) == "error"


def test_le_pipeline_refuse_un_jeton_inconnu_et_report_hors_machine(tmp_path: Path) -> None:
    base = {
        "schema_version": 1,
        "jobs": [{"job_id": "ruff", "label_text": "Lint", "tool": "ruff", "human": ["check"]}],
    }
    path = tmp_path / "pipeline.yaml"
    for human in (["{inconnu}"], ["--out={report}"]):
        base["jobs"][0]["human"] = human
        path.write_text(yaml.safe_dump(base), "utf-8")
        with pytest.raises(ci.PipelineError):
            ci.load_pipeline(Settings(), path)
    base["jobs"][0]["human"] = ["--compare-branch={base_sha}", "{repo}", "{osv_url}"]
    path.write_text(yaml.safe_dump(base), "utf-8")
    assert ci.load_pipeline(Settings(), path).jobs[0].human[0] == "--compare-branch={base_sha}"
    base["jobs"].append(dict(base["jobs"][0]))
    path.write_text(yaml.safe_dump(base), "utf-8")
    with pytest.raises(ci.PipelineError):
        ci.load_pipeline(Settings(), path)  # job_id en double


def test_les_jetons_sont_remplaces_par_ci() -> None:
    tokens = {"repo": "/ci/1-abc", "base_sha": SHA, "osv_url": "http://127.0.0.1:1/osv/v1/query"}
    argv = ["--compare-branch={base_sha}", "{repo}", "--osv-url", "{osv_url}"]
    assert ci.expand(argv, tokens) == [
        f"--compare-branch={SHA}",
        "/ci/1-abc",
        "--osv-url",
        tokens["osv_url"],
    ]
    with pytest.raises(KeyError):
        ci.expand(["{osv_url}"], {"osv_url": ""})


def test_constats_tires_des_sorties_machine(tmp_path: Path) -> None:
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_a.py").write_text("", "utf-8")
    ruff = json.dumps(
        [
            {
                "code": "F401",
                "message": "`os` imported but unused",
                "filename": str(tmp_path / "src" / "a.py"),
                "location": {"row": 3, "column": 8},
            }
        ]
    )
    (found,) = parsers.parse_ruff_json(ruff, tmp_path)
    assert (found.rule_id, found.path, found.line) == ("F401", "src/a.py", 3)
    junit = (
        '<testsuites><testsuite><testcase classname="tests.test_a" name="test_x">'
        '<failure message="assert 1 == 2">trace</failure></testcase>'
        '<testcase classname="tests.test_a" name="test_ok"/></testsuite></testsuites>'
    )
    (failed,) = parsers.parse_junit(junit, tmp_path)
    assert (failed.rule_id, failed.path, failed.message_text) == (
        "test_x",
        "tests/test_a.py",
        "assert 1 == 2",
    )
    leaks = json.dumps(
        [{"RuleID": "generic-api-key", "Description": "Clé", "File": "./cfg.py", "StartLine": 2}]
    )
    (leak,) = parsers.parse_gitleaks_json(leaks, tmp_path)
    assert (leak.rule_id, leak.path, leak.line) == ("generic-api-key", "cfg.py", 2)
    assert parsers.parse_gitleaks_json("null", tmp_path) == []
    with pytest.raises(ValueError):
        parsers.parse_ruff_json("pas du json", tmp_path)


def test_resultat_d_un_ancien_sha_refuse_par_github_sim(tmp_path: Path) -> None:
    """`set_check_state(expected=…)` refuse un résultat calculé pour d'autres SHA."""
    with pytest.raises(github_sim.StaleCheck):
        _box_free_stale(tmp_path)


def _box_free_stale(tmp_path: Path) -> None:
    from wavedevsecops.contracts.github import Check, GithubState

    layout = Layout(tmp_path / "ws")
    layout.root.mkdir()
    pr = PullRequest(
        number=1,
        head="f",
        base="main",
        head_sha=SHA,
        base_sha=SHA,
        checks=[Check(job_id="ruff", head_sha=SHA, base_sha=SHA)],
    )
    github_sim._save(layout, GithubState(pulls=[pr], next_number=2))
    github_sim.set_check_state(None, layout, 1, "ruff", "success", expected=(SHA2, SHA))  # type: ignore[arg-type]


# ------------------------------------------------------------------ environnement du run
def test_environnement_partage_si_meme_uv_lock_sinon_propre_au_run(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    layout = Layout(tmp_path / "ws")
    tree = layout.ci / "1-abcdef0"
    tree.mkdir(parents=True)
    (tree / "uv.lock").write_text("version = 1\n", "utf-8")
    shared = toolrun.venv_dir(layout.root)
    shared.mkdir(parents=True)
    synced: list[tuple[Path, Path]] = []

    def fake_sync(project, venv, settings=None, **kwargs):  # noqa: ANN001, ANN202
        synced.append((project, venv))
        venv.mkdir(parents=True, exist_ok=True)
        (venv / toolrun.LOCK_MARKER).write_text(toolrun.lock_digest(project) or "", "utf-8")
        return procs.ProcResult(0)

    monkeypatch.setattr(toolrun, "sync_environment", fake_sync)
    settings = Settings(data_dir=tmp_path / "data")
    digest = toolrun.lock_digest(tree)
    (shared / toolrun.LOCK_MARKER).write_text(digest + "\n", "utf-8")
    env = ci.prepare_environment(tree, layout, settings)
    assert env.venv == shared and env.shared and not synced
    # uv.lock du SHA testé mis à jour : environnement propre au run, depuis l'arbre testé.
    (tree / "uv.lock").write_text("version = 1\n# httpx\n", "utf-8")
    env = ci.prepare_environment(tree, layout, settings)
    assert env.venv is not None and not env.shared and env.venv.parent == layout.ci
    assert synced == [(tree, env.venv)]
    # Un deuxième run du même uv.lock réutilise cet environnement.
    assert ci.prepare_environment(tree, layout, settings).venv == env.venv and len(synced) == 1
    (tree / "uv.lock").unlink()
    assert ci.prepare_environment(tree, layout, settings).error


def test_sync_environment_marque_le_uv_lock_d_origine(tmp_path: Path) -> None:
    (tmp_path / "uv.lock").write_text("x", "utf-8")
    venv = tmp_path / "venv"
    assert toolrun.environment_digest(venv) is None
    venv.mkdir()
    (venv / toolrun.LOCK_MARKER).write_text(toolrun.lock_digest(tmp_path) + "\n", "utf-8")
    assert toolrun.environment_digest(venv) == toolrun.lock_digest(tmp_path)


# ------------------------------------------------------------------ dans un espace ouvert
def _scenario(pipeline: bool) -> dict:
    return {
        "schema_version": 1,
        "scenario_id": "pipeline-essai",
        "mode": "A",
        "title_text": "Pipeline simulé (essai)",
        "catalogue": False,
        "tracks": ["no_ai"],
        "tools": ["git"],
        "pipeline": pipeline,
        "setup": [
            {"op": "exercise_stage", "stage": "base"},
            {"op": "commit", "message": "Ajoute le projet"},
            {"op": "push", "branch": "main"},
            {"op": "switch", "branch": "rapport", "create": True},
            {"op": "write_file", "path": FEATURE, "content": "VALEUR = 1\n"},
            {"op": "commit", "message": "Ajoute le rapport"},
            {"op": "push", "branch": "rapport"},
            {"op": "open_pr", "head": "rapport", "title_text": "Rapport"},
        ],
        "steps": [],
    }


def _content(tmp_path: Path, scenario: dict) -> Path:
    content = tmp_path / "content"
    shutil.copytree(CONTENT, content, ignore=shutil.ignore_patterns("osv", "scenarios"))
    (content / "scenarios").mkdir()
    path = content / "scenarios" / "pipeline-essai.A.yaml"
    path.write_text(yaml.safe_dump(scenario, allow_unicode=True, sort_keys=False), "utf-8")
    return content


class Box:
    """Un espace ouvert avec une PR, et le journal de ses événements."""

    def __init__(self, settings: Settings, git_path: Path) -> None:
        self.settings = settings
        self.git_path = git_path
        path = settings.scenarios_path() / "pipeline-essai.A.yaml"
        loaded = load_scenario(path, settings)
        prepare_workspace(loaded, "no_ai", settings=settings, git_path=git_path, replace=True)
        self.ws = f"no_ai.{loaded.scenario.key}"
        self.manager = WorkspaceManager(
            settings, git_path=git_path, watch=False, osv_url=settings.osv_url(1)
        )
        self.events: list[Envelope] = []
        self.manager.events(self.ws).attach(None, self.events.append)
        self.engine: WorkspaceEngine = self.manager.get(self.ws)
        self.layout: Layout = self.manager.layout(self.ws)
        self.runner = engine_pipeline.RUNNERS[self.ws]

    def pr(self) -> PullRequest:
        pr = github_sim.load(self.layout).pull(1)
        assert pr is not None
        return pr

    def states(self) -> dict[str, str]:
        return {c.job_id: c.state for c in self.pr().checks}

    def wait(self, predicate: Callable[[], bool], what: str) -> None:
        deadline = time.monotonic() + WAIT
        while time.monotonic() < deadline:
            if predicate():
                return
            time.sleep(0.05)
        raise AssertionError(f"délai dépassé : {what} ({self.states()})")

    def wait_settled(self) -> None:
        self.wait(
            lambda: (
                len(self.states()) == len(ci.load_pipeline(self.settings).job_ids)
                and all(s not in ("queued", "running") for s in self.states().values())
                and not self.runner.busy
            ),
            "checks terminés",
        )

    def push_new_commit(self, text: str) -> str:
        """Un nouveau commit poussé sur la branche de la PR, par une opération de la file."""
        git = Git.for_workspace(self.git_path, self.layout.root, self.settings)

        def body(ctx):  # noqa: ANN001, ANN202
            (self.layout.repo / FEATURE).write_text(text, "utf-8")
            git.internal("add", "-A", cwd=self.layout.repo)
            git.internal(
                "-c",
                "user.name=Apprenant",
                "-c",
                "user.email=apprenant@example.invalid",
                "commit",
                "-q",
                "-m",
                "Modifie le rapport",
                cwd=self.layout.repo,
            )
            git.internal("push", "-q", "origin", "rapport", cwd=self.layout.repo)
            github_sim.refresh(git, ctx.layout)
            return 0

        done = self.engine.submit(Operation("terminal_line", body)).result(WAIT)
        assert done.code == 0, [e.payload for e in self.events if e.kind == Kind.APP_ERROR]
        return git.internal("rev-parse", "HEAD", cwd=self.layout.repo).strip()

    def close(self) -> None:
        self.manager.close()


Behaviour = dict[str, tuple[str, int, str, float]]
"""outil -> (sortie humaine, code, sortie machine, pause en secondes avant de sortir)."""

DEFAULT_BEHAVIOUR: Behaviour = {
    # pip-audit sans dépendance : rapport et SBOM vides, mais lisibles (sinon le check rougit).
    "pip-audit": (
        "No known vulnerabilities found\n",
        0,
        '{"dependencies": [], "components": []}',
        0,
    ),
}
MACHINE_FLAGS = ("--output-format", "--junitxml", "--report-format", "-f")

RUFF_TEXT = "src/inventory/rapport.py:1:8: F401 [*] `os` imported but unused\nFound 1 error.\n"
RUFF_JSON = json.dumps(
    [
        {
            "code": "F401",
            "message": "`os` imported but unused",
            "filename": FEATURE,
            "location": {"row": 1, "column": 8},
        }
    ]
)


BANDIT_TEXT = (
    ">> Issue: [B307:blacklist] Use of possibly insecure function - consider using safer "
    "ast.literal_eval.\n   Location: ./src/inventory/rapport.py:4:11\n"
)
BANDIT_JSON = json.dumps(
    {
        "errors": [],
        "results": [
            {
                "filename": FEATURE,
                "issue_text": "Use of possibly insecure function - consider using safer "
                "ast.literal_eval.",
                "line_number": 4,
                "test_id": "B307",
                "issue_severity": "MEDIUM",
            }
        ],
    }
)


def _fake_tools(monkeypatch: pytest.MonkeyPatch, behaviour: Behaviour, calls: list) -> None:
    """`toolrun.spawn_tool` remplacé : sortie et code voulus par outil, rapport machine écrit."""
    real_spawn = procs.spawn

    def fake(tool_id, args, *, cwd, venv, timeout, settings=None):  # noqa: ANN001, ANN202
        args = list(args)
        machine = any(flag in args for flag in MACHINE_FLAGS)
        human, code, machine_text, pause = behaviour.get(
            tool_id, DEFAULT_BEHAVIOUR.get(tool_id, ("", 0, "", 0))
        )
        calls.append((tool_id, machine, Path(cwd)))
        text = machine_text if machine else human
        script = "import sys, time; "
        report = next(
            (args[i + 1] for i, a in enumerate(args) if a in ("--junitxml", "--report-path")),
            None,
        )
        if machine and report:
            script += f"open({report!r}, 'w', encoding='utf-8').write({text!r}); "
        else:
            script += f"sys.stdout.buffer.write({text.encode()!r}); sys.stdout.flush(); "
        script += f"time.sleep({pause}); sys.exit({code})"
        return real_spawn([PYTHON, "-c", script], env=dict(os.environ), cwd=cwd, timeout=timeout)

    monkeypatch.setattr(toolrun, "spawn_tool", fake)


@pytest.fixture
def fake_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Pas de `uv sync` : l'environnement du run est un dossier vide (outils remplacés)."""
    venv = tmp_path / "venv"
    venv.mkdir()
    monkeypatch.setattr(ci, "prepare_environment", lambda *a, **k: ci.Environment(venv))


def _settings(tmp_path: Path, pipeline: bool = True) -> Settings:
    return Settings(data_dir=tmp_path / "data", content_dir=_content(tmp_path, _scenario(pipeline)))


@pytest.fixture
def box(tmp_path: Path, git_path: Path, fake_env: None) -> Iterator[Box]:
    created: list[Box] = []

    def make() -> Box:
        created.append(Box(_settings(tmp_path), git_path))
        return created[-1]

    yield make  # type: ignore[misc]
    for opened in created:
        opened.close()


@pytest.mark.slow
def test_chaque_job_donne_un_check_ecrit_par_la_file(box, monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list = []
    _fake_tools(
        monkeypatch,
        {
            "ruff": (RUFF_TEXT, 1, RUFF_JSON, 0),
            "pytest": ("3 passed\n", 0, "", 0),
            "gitleaks": ("panic: config\n", 1, "", 0),
            "bandit": (BANDIT_TEXT, 1, BANDIT_JSON, 0),
        },
        calls,
    )
    opened: Box = box()
    opened.wait_settled()
    pr = opened.pr()
    checks = {c.job_id: c for c in pr.checks}
    assert [c.job_id for c in pr.checks] == ["ruff", "pytest", "gitleaks", "bandit", "pip_audit"]
    # bandit : sortie humaine verbatim, constat (fichier, ligne, règle) de `-f json`.
    bandit = checks["bandit"]
    assert bandit.state == "failure" and bandit.output == BANDIT_TEXT
    assert [(f.rule_id, f.path, f.line) for f in bandit.findings] == [("B307", FEATURE, 4)]
    assert all(c.required for c in pr.checks)
    assert all((c.head_sha, c.base_sha) == (pr.head_sha, pr.base_sha) for c in pr.checks)
    # Sortie humaine verbatim, constats de l'exécution machine (fichier, ligne, règle).
    ruff = checks["ruff"]
    assert ruff.state == "failure" and ruff.output == RUFF_TEXT
    assert [(f.rule_id, f.path, f.line) for f in ruff.findings] == [("F401", FEATURE, 1)]
    assert checks["pytest"].state == "success" and checks["pytest"].findings == []
    # Code « erreur de l'outil » : distinct d'un échec, explication sans accuser le code.
    gitleaks = checks["gitleaks"]
    assert gitleaks.state == "error" and gitleaks.output == "panic: config\n"
    (why,) = gitleaks.findings
    assert why.rule_id == ci.TOOL_ERROR_RULE
    assert why.message_text == (
        "gitleaks s'est arrêté sans résultat (code 1). Ce n'est pas un défaut de votre code."
    )
    assert all(c.duration_ms is not None for c in pr.checks)
    assert not pr.mergeable  # la PR reste bloquée
    # Les jobs tournent dans l'arbre cloné ci/<pr>-<sha7>/, jeté ensuite.
    tree = opened.layout.ci / f"1-{pr.head_sha[:7]}"
    assert {cwd for _tool, _machine, cwd in calls} == {tree}
    assert [(t, m) for t, m, _ in calls] == [
        ("ruff", False),
        ("ruff", True),
        ("pytest", False),
        ("gitleaks", False),
        ("bandit", False),
        ("bandit", True),
        ("pip-audit", False),
        ("pip-audit", True),
    ]
    assert not tree.exists()
    # Chaque changement d'état est une opération de la file : check_updated, puis pr_updated.
    updates = [e.payload for e in opened.events if e.kind == Kind.CHECK_UPDATED]
    assert [(u["job_id"], u["state"]) for u in updates] == [
        ("ruff", "running"),
        ("ruff", "failure"),
        ("pytest", "running"),
        ("pytest", "success"),
        ("gitleaks", "running"),
        ("gitleaks", "error"),
        ("bandit", "running"),
        ("bandit", "failure"),
        ("pip_audit", "running"),
        ("pip_audit", "success"),
    ]
    assert updates[1]["element_id"] == f"check:1:ruff:{pr.head_sha}"
    ops = {e.op_id for e in opened.events if e.kind == Kind.CHECK_UPDATED}
    started = [e for e in opened.events if e.kind == Kind.OP_STARTED and e.op_id in ops]
    assert {e.payload["intent"] for e in started} == {"check_update"}
    (run,) = opened.runner.history
    assert run.duration_ms is not None and run.states == {
        "ruff": "failure",
        "pytest": "success",
        "gitleaks": "error",
        "bandit": "failure",
        "pip_audit": "success",
    }
    # Vue Distant + PR : sortie verbatim liée, ligne de détail fichier:ligne, erreur de l'outil.
    opened.engine.submit(Operation("noop", lambda ctx: 0, writes=False)).result(WAIT)
    rows = {
        c["job_id"]: c
        for c in json.loads(json.dumps(opened.engine.last_projection.views, default=str))["remote"][
            "pulls"
        ][0]["checks"]
    }
    path_id = f"path:worktree:{FEATURE}"
    assert rows["ruff"]["output_text"] == RUFF_TEXT
    assert [s["element_id"] for s in rows["ruff"]["output_spans"]] == [path_id]
    assert rows["ruff"]["details"] == [
        {
            "rule_id": "F401",
            "message_text": "`os` imported but unused",
            "location_text": f"{FEATURE}:1",
            "link": path_id,
        }
    ]
    assert not rows["ruff"]["can_rerun"] and rows["gitleaks"]["can_rerun"]
    assert rows["gitleaks"]["tool_error_text"] == why.message_text
    assert rows["gitleaks"]["details"] == []
    # « Voir la sortie » : la preuve de la barrière du job (une seule fois par parcours).
    engine_pipeline.register_intents()
    seen = build_operation(opened.engine, "check_output_seen", {"number": 1, "job_id": "ruff"})
    opened.engine.submit(seen).result(WAIT)
    facts = [e.payload["facts"] for e in opened.events if e.kind == Kind.PROGRESS_UPDATED]
    assert ["evidence_seen"] in facts


@pytest.mark.slow
def test_un_nouveau_sha_annule_le_run_et_rejette_ses_resultats(
    box, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list = []
    behaviour = {
        "ruff": ("lent\n", 0, "", 60.0),
        "pytest": ("ok\n", 0, "", 0),
        "gitleaks": ("ok\n", 0, "", 0),
    }
    _fake_tools(monkeypatch, behaviour, calls)
    spawned: list[procs.Handle] = []
    fake = toolrun.spawn_tool

    def tracking(*args, **kwargs):  # noqa: ANN002, ANN003, ANN202
        handle = fake(*args, **kwargs)
        spawned.append(handle)
        return handle

    monkeypatch.setattr(toolrun, "spawn_tool", tracking)
    opened: Box = box()
    opened.wait(lambda: opened.states().get("ruff") == "running", "ruff en cours")
    # Le check passe à `running` avant le lancement de l'outil : on attend le ruff lent lancé,
    # sinon l'ancien run prendrait le ruff rapide et pourrait finir avant le push (test instable).
    opened.wait(lambda: len(spawned) >= 1, "ruff lent lancé")
    old_sha = opened.pr().head_sha
    behaviour["ruff"] = ("vite\n", 0, "", 0)
    new_sha = opened.push_new_commit("VALEUR = 2\n")
    assert new_sha != old_sha
    # L'arbre de l'ancien run est arrêté (procs.terminate_tree).
    assert wait_dead(spawned[0].pid) and not alive(spawned[0].pid)
    opened.wait_settled()
    pr = opened.pr()
    assert pr.head_sha == new_sha
    assert all(c.head_sha == new_sha and c.state == "success" for c in pr.checks)
    assert all(c.output != "lent\n" for c in pr.checks)
    first, second = list(opened.runner.history)
    assert first.cancelled and first.head_sha == old_sha
    assert second.head_sha == new_sha and not second.cancelled


@pytest.mark.slow
def test_recommencer_annule_le_run_en_cours(box, monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list = []
    _fake_tools(
        monkeypatch,
        {"ruff": ("lent\n", 0, "", 60.0), "pytest": ("", 0, "", 0), "gitleaks": ("", 0, "", 0)},
        calls,
    )
    spawned: list[procs.Handle] = []
    fake = toolrun.spawn_tool

    def tracking(*args, **kwargs):  # noqa: ANN002, ANN003, ANN202
        spawned.append(fake(*args, **kwargs))
        return spawned[-1]

    monkeypatch.setattr(toolrun, "spawn_tool", tracking)
    opened: Box = box()
    opened.wait(lambda: opened.states().get("ruff") == "running", "ruff en cours")
    opened.wait(lambda: len(spawned) >= 1, "ruff lent lancé")
    epoch = opened.engine.epoch
    path = opened.settings.scenarios_path() / "pipeline-essai.A.yaml"
    _engine, future = opened.manager.create(
        load_scenario(path, opened.settings), "no_ai", replace=True
    )
    future.result(WAIT)
    assert opened.engine.epoch == epoch + 1
    assert wait_dead(spawned[0].pid) and not alive(spawned[0].pid)
    assert opened.runner.history[0].cancelled


@pytest.mark.slow
def test_un_resultat_d_un_ancien_epoch_est_refuse_par_la_file(box, monkeypatch) -> None:
    calls: list = []
    _fake_tools(
        monkeypatch,
        {"ruff": ("", 0, "", 0), "pytest": ("", 0, "", 0), "gitleaks": ("", 0, "", 0)},
        calls,
    )
    opened: Box = box()
    opened.wait_settled()
    pr = opened.pr()
    run = engine_pipeline.Run(1, pr.head_sha, pr.base_sha, epoch=opened.engine.epoch - 1)
    result = ci.JobResult("ruff", "failure", "tardif\n")
    op = engine_pipeline.check_operation(opened.runner, run, "ruff", "failure", result=result)
    with pytest.raises(StaleOperation):
        opened.engine.submit(op)
    assert opened.states()["ruff"] == "success"


@pytest.mark.slow
def test_relancer_un_check_ne_relance_que_ce_job(box, monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list = []
    behaviour = {
        "ruff": ("", 0, "", 0),
        "pytest": ("", 0, "", 0),
        "gitleaks": ("introuvable\n", 2, "", 0),
    }
    _fake_tools(monkeypatch, behaviour, calls)
    opened: Box = box()
    opened.wait_settled()
    assert opened.states()["gitleaks"] == "error"
    engine_pipeline.register_intents()
    with pytest.raises(OperationRefused, match="pas de job"):
        build_operation(opened.engine, "check_rerun", {"number": 1, "job_id": "inconnu"})
    behaviour["gitleaks"] = ("aucune fuite\n", 0, "", 0)
    calls.clear()
    op = build_operation(opened.engine, "check_rerun", {"number": 1, "job_id": "gitleaks"})
    opened.engine.submit(op).result(WAIT)
    opened.wait(lambda: opened.states()["gitleaks"] == "success", "gitleaks relancé")
    opened.wait_settled()
    assert [t for t, _m, _c in calls] == ["gitleaks"]
    assert opened.states() == {
        "ruff": "success",
        "pytest": "success",
        "gitleaks": "success",
        "bandit": "success",
        "pip_audit": "success",
    }
    assert opened.pr().mergeable


@pytest.mark.slow
def test_une_erreur_interne_du_run_laisse_des_checks_termines(
    box, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list = []
    _fake_tools(
        monkeypatch,
        {"ruff": ("", 0, "", 0), "pytest": ("", 0, "", 0), "gitleaks": ("", 0, "", 0)},
        calls,
    )
    crashes = [1]

    def broken(*args, **kwargs):  # noqa: ANN002, ANN003, ANN202
        if crashes:
            crashes.pop()
            raise RuntimeError("panne interne")
        return real_prepare(*args, **kwargs)

    real_prepare = ci.prepare_tree
    monkeypatch.setattr(ci, "prepare_tree", broken)
    opened: Box = box()
    opened.wait_settled()
    pr = opened.pr()
    assert {c.state for c in pr.checks} == {"error"} and not calls
    for check in pr.checks:
        (why,) = check.findings
        assert why.rule_id == ci.TOOL_ERROR_RULE and "erreur interne" in why.message_text
    # Les checks sont terminés : « Relancer le check » est admis et le job retourne.
    engine_pipeline.register_intents()
    op = build_operation(opened.engine, "check_rerun", {"number": 1, "job_id": "ruff"})
    opened.engine.submit(op).result(WAIT)
    opened.wait(lambda: opened.states()["ruff"] == "success", "ruff relancé")


@pytest.mark.slow
def test_relancer_un_check_reste_en_cours_sans_run(box, monkeypatch) -> None:
    calls: list = []
    _fake_tools(
        monkeypatch,
        {"ruff": ("", 0, "", 0), "pytest": ("", 0, "", 0), "gitleaks": ("", 0, "", 0)},
        calls,
    )
    opened: Box = box()
    opened.wait_settled()
    opened.runner.stop()  # plus aucun run : un check resté `running` (arrêt brutal) est orphelin
    git = Git.for_workspace(opened.git_path, opened.layout.root, opened.settings)
    github_sim.set_check_state(git, opened.layout, 1, "pytest", "running")
    body = engine_pipeline.CheckRerun(number=1, job_id="pytest")
    assert engine_pipeline._rerun_refusal(opened.engine, body) == ""
    pr = opened.pr()
    run = engine_pipeline.Run(1, pr.head_sha, pr.base_sha, epoch=opened.engine.epoch)
    run.todo.append("pytest")
    opened.runner._queue.append(run)  # un run vivant le couvre : la relance est refusée
    assert "déjà en attente" in engine_pipeline._rerun_refusal(opened.engine, body)


def test_ci_borne_la_sortie_et_signale_un_detail_illisible(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    long = "x" * (ci.MAX_OUTPUT_CHARS * 2)
    bounded = ci.bound_output(long)
    assert len(bounded) < ci.MAX_OUTPUT_CHARS + 100 and "caractères de sortie omis" in bounded
    assert ci.bound_output("court\n") == "court\n"
    calls: list = []
    _fake_tools(monkeypatch, {"ruff": (RUFF_TEXT, 1, "pas du json", 0)}, calls)
    settings = Settings(data_dir=tmp_path / "data")
    job = ci.load_pipeline(settings).job("ruff")
    assert job is not None
    result = ci.run_job(
        job, tree=tmp_path, venv=None, tokens={"repo": str(tmp_path)}, settings=settings
    )
    assert result.state == "failure" and result.output == RUFF_TEXT
    (finding,) = result.findings
    assert finding.rule_id == ci.NO_DETAIL_RULE and "la sortie de l'outil" in finding.message_text


@pytest.mark.slow
def test_sans_pipeline_declare_aucun_run(
    tmp_path: Path, git_path: Path, fake_env: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list = []
    _fake_tools(monkeypatch, {}, calls)
    opened = Box(_settings(tmp_path, pipeline=False), git_path)
    try:
        opened.engine.submit(Operation("noop", lambda ctx: 0, writes=False)).result(WAIT)
        time.sleep(0.3)
        assert opened.pr().checks == [] and not calls and not opened.runner.busy
        engine_pipeline.register_intents()
        with pytest.raises(OperationRefused, match="ne tourne pas"):
            build_operation(opened.engine, "check_rerun", {"number": 1, "job_id": "ruff"})
    finally:
        opened.close()


# ------------------------------------------------------------------ vrais outils
USE_TEMPLATE_LOCK = os.environ.get("WDS_EXERCISE_UV") == "1"
ALERT_S, LIMIT_S = 90.0, 180.0
"""Durée d'un run des jobs de l'Epic 7 sur le runner de CI : alerte, puis échec."""


@pytest.mark.slow
@pytest.mark.skipif(not USE_TEMPLATE_LOCK, reason="WDS_EXERCISE_UV=1 : cache uv préchargé")
def test_vrais_outils_dans_le_pipeline(tmp_path: Path, git_path: Path) -> None:
    """Vrais ruff, pytest et gitleaks sur une PR qui met à jour une dépendance du uv.lock :
    le check pytest voit la nouvelle version (environnement propre au run, AD-12)."""
    llm = CONTENT / "exercise" / "llm"
    scenario = _scenario(True)
    httpx_test = (
        "from importlib.metadata import version\n\n\n"
        "def test_httpx_du_uv_lock() -> None:\n"
        '    assert version("httpx") == "0.28.1"\n'
    )
    scenario["setup"][4:5] = [
        {
            "op": "write_file",
            "path": "pyproject.toml",
            "content": (llm / "pyproject.toml").read_text("utf-8"),
        },
        {"op": "write_file", "path": "uv.lock", "content": (llm / "uv.lock").read_text("utf-8")},
        {"op": "write_file", "path": "tests/test_dependance.py", "content": httpx_test},
    ]
    data = Path(os.environ["WDS_EXERCISE_DATA"])
    settings = Settings(data_dir=data, content_dir=_content(tmp_path, scenario))
    opened = Box(settings, git_path)
    try:
        opened.wait_settled()
        checks = {c.job_id: c for c in opened.pr().checks}
        assert checks["pytest"].state == "success", checks["pytest"].output
        assert "passed" in checks["pytest"].output
        assert checks["ruff"].state in ("success", "failure"), checks["ruff"].output
        # gitleaks vient de tools/ (installeur) : absent du runner, le check est en erreur.
        assert checks["gitleaks"].state in ("success", "error")
        (run,) = opened.runner.history
        seconds = (run.duration_ms or 0) / 1000
        if seconds > ALERT_S:
            warnings.warn(
                f"run du pipeline en {seconds:.1f} s (alerte à {ALERT_S:g} s)", stacklevel=1
            )
        assert seconds <= LIMIT_S
    finally:
        opened.close()
