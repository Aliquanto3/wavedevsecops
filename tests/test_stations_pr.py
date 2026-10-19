"""Story 7.5 : les scénarios de la station 2 « check-en-echec », « pr-sans-revue » et
« push-direct-main » : un check obligatoire en échec, la revue obligatoire et la protection de
`main` bloquent pour de vrai, dans les deux parcours.

Les scénarios sont joués de bout en bout sur un vrai git (setup, commandes du terminal, intentions
de la vue « Distant + PR »). Seuls les outils du pipeline (ruff, pytest, gitleaks) sont remplacés
par de petits Python qui lisent l'arbre testé : pytest échoue tant que le test du scénario attend
une liste vide.
"""

from __future__ import annotations

import os
import re
import sys
import time
import warnings
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from pathlib import Path

import pytest
import yaml

from wavedevsecops import ci, github_sim, procs, terminal, toolrun
from wavedevsecops.config import Settings
from wavedevsecops.engine import (
    WorkspaceEngine,
    WorkspaceManager,
    build_operation,
    load_run,
    pipeline,
    pr_intents,
)
from wavedevsecops.engine.operations import OperationRefused
from wavedevsecops.events import Envelope, Kind
from wavedevsecops.gitio import Git
from wavedevsecops.progress.facts import ProgressStore
from wavedevsecops.projections import EXPLAIN_REFS
from wavedevsecops.scenarios import load_scenario
from wavedevsecops.scenarios.steps._base import BLANK

WAIT = 90.0
IDS = ("check-en-echec", "pr-sans-revue", "push-direct-main")
TRACKS = ("llm", "no_ai")
PYTHON = getattr(sys, "_base_executable", sys.executable)
BROKEN_TEST = "tests/test_reapprovisionnement.py"
REFUSAL = "Refusé par la protection de `main` : tout passe par une PR."


# ------------------------------------------------------------------------------ outils remplacés
class Fakes:
    """Comportement des outils du pipeline : lu dans l'arbre testé."""

    pytest_pause = 0.0

    def behave(self, tool_id: str, cwd: Path) -> tuple[str, int]:
        if tool_id != "pytest":
            return "Tout est en ordre.\n", 0
        broken = cwd / BROKEN_TEST
        if broken.is_file() and "== []" in broken.read_text("utf-8"):
            text = (
                f"FAILED {BROKEN_TEST}::test_article_sous_le_seuil_est_a_recommander\n"
                "E   assert ['vis'] == []\n1 failed\n"
            )
            return text, 1
        return "1 passed\n", 0


@pytest.fixture
def fakes(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Fakes:
    state = Fakes()
    venv = tmp_path / "venv"
    venv.mkdir()
    monkeypatch.setattr(ci, "prepare_environment", lambda *a, **k: ci.Environment(venv))
    # Ni `uv sync` à l'ouverture de l'espace, ni environnement à vérifier : outils remplacés.
    monkeypatch.setattr(toolrun, "needs_environment", lambda *a, **k: False)
    real_spawn = procs.spawn

    def fake(tool_id, args, *, cwd, venv, timeout, settings=None):  # noqa: ANN001, ANN202
        args = list(args)
        machine = any(f in args for f in ("--output-format", "--junitxml", "--report-format"))
        text, code = state.behave(tool_id, Path(cwd))
        report = next(
            (args[i + 1] for i, a in enumerate(args) if a in ("--junitxml", "--report-path")),
            None,
        )
        script = "import sys, time; "
        if machine and report:
            script += f"open({report!r}, 'w', encoding='utf-8').write(''); "
        else:
            script += f"sys.stdout.buffer.write({text.encode()!r}); sys.stdout.flush(); "
        pause = state.pytest_pause if tool_id == "pytest" else 0
        script += f"time.sleep({pause}); sys.exit({code})"
        return real_spawn([PYTHON, "-c", script], env=dict(os.environ), cwd=cwd, timeout=timeout)

    monkeypatch.setattr(toolrun, "spawn_tool", fake)
    return state


# ------------------------------------------------------------------------------------- banc
@dataclass
class Box:
    settings: Settings
    manager: WorkspaceManager
    engine: WorkspaceEngine
    events: list[Envelope]
    git: Git

    def line(self, text: str) -> None:
        op = terminal.build_terminal_line(self.engine, terminal.TerminalLine(line=text))
        done = self.engine.submit(op).result(WAIT)
        assert done.code is not None

    def intent(self, name: str, **body) -> None:
        self.engine.submit(build_operation(self.engine, name, body)).result(WAIT)

    def current(self) -> str | None:
        return load_run(self.engine.layout).get("step_id")

    def wait_step(self, step_id: str | None) -> None:
        deadline = time.monotonic() + WAIT
        while time.monotonic() < deadline:
            if self.current() == step_id:
                return
            time.sleep(0.05)
        raise AssertionError(f"étape attendue : {step_id}, courante : {self.current()}")

    def pr(self):  # noqa: ANN201
        pr = github_sim.load(self.engine.layout).pull(1)
        assert pr is not None
        return pr

    def card(self) -> dict:
        return self.engine.snapshot()["views"]["remote"]["pulls"][0]

    def evidence(self) -> list[str]:
        facts = ProgressStore.for_dir(self.settings.resolved_data_dir()).facts()
        return [f["barrier_id"] for f in facts if f["kind"] == "evidence_seen"]

    def outputs(self) -> str:
        return "\n".join(
            str(e.payload["text"]) for e in self.events if e.kind == Kind.TERMINAL_OUTPUT
        )

    def verdicts(self, step_id: str) -> list[dict]:
        return [
            e.payload
            for e in self.events
            if e.kind == Kind.STEP_VERDICT and e.payload["step_id"] == step_id
        ]


@pytest.fixture
def make_box(tmp_path: Path, git_path: Path, fakes: Fakes) -> Iterator[Callable[[str, str], Box]]:
    boxes: list[Box] = []
    terminal.AFTER_COMMAND_HOOKS.clear()
    terminal.register_intents()
    pr_intents.register_intents()
    pipeline.register_intents()
    terminal.AFTER_COMMAND_HOOKS.append(pr_intents.refresh_after_command)

    def make(scenario_id: str, track: str) -> Box:
        settings = Settings(data_dir=tmp_path / f"data-{len(boxes)}")
        loaded = load_scenario(settings.scenarios_path() / f"{scenario_id}.A.yaml", settings)
        manager = WorkspaceManager(settings, git_path=git_path, watch=False)
        events: list[Envelope] = []
        manager.events(f"{track}.{scenario_id}.A").attach(None, events.append)
        engine, setup = manager.create(loaded, track)
        setup.result(WAIT)
        git = Git.for_workspace(git_path, engine.layout.root, settings)
        boxes.append(Box(settings, manager, engine, events, git))
        return boxes[-1]

    yield make
    for box in boxes:
        box.manager.close()
    terminal.AFTER_COMMAND_HOOKS.clear()


# ------------------------------------------------------------------------------------- lint
@pytest.mark.parametrize("scenario_id", IDS)
def test_contenu_complet_et_sans_avertissement(scenario_id: str) -> None:
    settings = Settings()
    scenario = load_scenario(
        settings.scenarios_path() / f"{scenario_id}.A.yaml", settings, explain_keys=EXPLAIN_REFS
    ).scenario
    assert scenario.mode == "A" and sorted(scenario.tracks) == ["llm", "no_ai"]
    assert (scenario.section, scenario.station, scenario.catalogue) == ("stations", 2, True)
    with warnings.catch_warnings():
        assert not scenario.authoring_warnings()
    assert scenario.pipeline is (scenario_id != "push-direct-main")
    # Le hook de l'origine protège `main` pour de vrai : il est posé avant la protection.
    ops = [op.op for op in scenario.setup]
    assert ops.index("install_hooks") < ops.index("set_protection")
    for step in scenario.steps:
        where = f"{scenario_id}/{step.step_id}"
        assert step.hints is not None and BLANK in step.hints.partial_text, where
        # Le premier palier ne donne pas la réponse : ni la commande, ni le bouton à cliquer.
        lead = step.hints.lead_text.lower()
        assert step.hints.solution_text.lower() not in lead, where
    # Libellés réels de l'interface, vouvoiement (jamais « tu » ni « ton »).
    text = " ".join(s.instruction_text + " " + s.explanation_text for s in scenario.steps)
    assert not re.search(r"(tu|ton|ta|tes|toi|te)", text.lower())


def test_exigences_propres_a_chaque_scenario() -> None:
    settings = Settings()

    def load(scenario_id: str):  # noqa: ANN202
        return load_scenario(settings.scenarios_path() / f"{scenario_id}.A.yaml", settings).scenario

    echec = load("check-en-echec")
    protect = next(op for op in echec.setup if op.op == "set_protection")
    assert protect.required_checks == ["ruff", "pytest", "gitleaks"]
    assert protect.required_approvals == 0
    revue = load("pr-sans-revue")
    protect = next(op for op in revue.setup if op.op == "set_protection")
    assert protect.required_approvals == 1
    reaction = next(op for op in revue.setup if op.op == "colleague_reaction")
    assert reaction.trigger == "review_requested"  # l'approbation ne vient pas toute seule
    assert [r.state for r in reaction.reviews] == ["commented", "approved"]
    direct = load("push-direct-main")
    refusal = next(s for s in direct.steps if s.type == "push_refused")
    assert refusal.branch == "main"


def test_les_barrieres_de_la_station_2_sont_dans_la_chaine() -> None:
    chain = yaml.safe_load((Settings().content_path() / "chain.yaml").read_text("utf-8"))
    station = next(s for s in chain["stations"] if s["number"] == 2)
    barriers = {b["id"] for b in station["barriers"]}
    assert {"tests", "review", "protection"} <= barriers
    assert pr_intents.REVIEW_BARRIER in barriers and terminal.PROTECTION_BARRIER in barriers


def test_l_etape_du_refus_ne_se_valide_que_par_le_refus_de_la_bonne_branche() -> None:
    from wavedevsecops.scenarios.steps._base import StepContext
    from wavedevsecops.scenarios.steps.push_refused import REFUSED_KEY, Args, check

    step = Args(
        step_id="refus",
        type="push_refused",
        title_text="T",
        instruction_text="I",
        explanation_text="E",
        branch="main",
    )

    def verdict(**data) -> str:
        return check(None, StepContext(step=step, data=data)).status

    assert verdict() == "pending"
    assert verdict(**{REFUSED_KEY: "autre"}) == "pending"
    assert verdict(**{REFUSED_KEY: "main"}) == "passed"


def test_pr_state_juge_les_checks_sur_les_sha_courants(tmp_path: Path) -> None:
    from wavedevsecops.contracts.github import Check, PullRequest
    from wavedevsecops.scenarios.steps.pr_state import _checks_match

    sha, other = "a" * 40, "b" * 40
    pr = PullRequest(
        number=1,
        head="f",
        base="main",
        head_sha=sha,
        base_sha=sha,
        checks=[
            Check(job_id="ruff", head_sha=sha, base_sha=sha, state="success"),
            Check(job_id="pytest", head_sha=other, base_sha=sha, state="success"),  # périmé
        ],
    )
    assert _checks_match(pr, {"ruff": "success"})
    assert not _checks_match(pr, {"ruff": "failure"})
    assert not _checks_match(pr, {"pytest": "success"})  # résultat d'un ancien commit
    assert not _checks_match(pr, {"gitleaks": "success"})  # check absent


# ------------------------------------------------------------------- check en échec
@pytest.mark.parametrize("track", TRACKS)
def test_check_en_echec_bloque_le_merge_puis_se_corrige(make_box, track: str) -> None:
    box = make_box("check-en-echec", track)
    assert box.current() == "pousser_la_branche"
    box.line("git push -u origin seuil-rupture")
    assert box.current() == "ouvrir_la_pr"
    box.intent("pr_open", head="seuil-rupture")
    # Le pipeline écrit ses résultats par la file : l'étape suivante attend le check en échec.
    box.wait_step("corriger_et_pousser")
    pr = box.pr()
    states = {c.job_id: c.state for c in pr.checks}
    assert states["pytest"] == "failure"
    assert not pr.mergeable
    assert [r.kind for r in pr.blocking_reasons if "pytest" in r.text] == ["check"]
    card = box.card()
    assert card["merge"]["enabled"] is False
    assert any("pytest" in r["text"] for r in card["merge"]["reasons"])
    # « Voir la sortie » : la preuve de la barrière « tests » (une seule fois).
    box.intent("check_output_seen", number=1, job_id="pytest")
    box.intent("check_output_seen", number=1, job_id="pytest")
    assert box.evidence() == ["tests"]
    # Un push qui laisse le test en échec ne valide pas l'étape de correction.
    box.line('git commit --allow-empty -m "Essai sans correction"')
    box.line("git push")
    box.pr()
    deadline = time.monotonic() + WAIT
    while time.monotonic() < deadline and {c.state for c in box.pr().checks} != {
        "success",
        "failure",
    }:
        time.sleep(0.05)
    assert box.current() == "corriger_et_pousser"
    # La correction : une vraie modification du test, committée et poussée.
    repo = box.engine.layout.repo
    fixed = (repo / BROKEN_TEST).read_text("utf-8").replace("== []", '== ["vis"]')
    (repo / BROKEN_TEST).write_text(fixed, "utf-8")
    box.line(f"git add {BROKEN_TEST}")
    box.line('git commit -m "Corrige le test du seuil"')
    box.line("git push")
    box.wait_step("merger_la_pr")
    pr = box.pr()
    assert pr.mergeable and {c.state for c in pr.checks} == {"success"}
    box.intent("pr_merge", number=1)
    box.wait_step(None)  # fin du scénario : plus d'étape courante
    assert box.pr().state == "merged"


@pytest.mark.parametrize("track", TRACKS)
def test_merger_est_refuse_tant_que_le_check_echoue(make_box, track: str) -> None:
    box = make_box("check-en-echec", track)
    box.line("git push -u origin seuil-rupture")
    box.intent("pr_open", head="seuil-rupture")
    box.wait_step("corriger_et_pousser")
    with pytest.raises(OperationRefused, match="pytest"):
        box.intent("pr_merge", number=1)
    assert box.pr().state == "open"


# ------------------------------------------------------------------- PR sans revue
@pytest.mark.parametrize("track", TRACKS)
def test_pr_sans_revue_checks_verts_mais_merge_bloque_jusqu_a_la_revue(
    make_box, track: str
) -> None:
    box = make_box("pr-sans-revue", track)
    box.line("git push -u origin test-quantite")
    box.intent("pr_open", head="test-quantite")
    box.wait_step("demander_la_revue")
    pr = box.pr()
    assert {c.job_id: c.state for c in pr.checks} == {
        "ruff": "success",
        "pytest": "success",
        "gitleaks": "success",
        "bandit": "success",
    }
    # Checks verts, mais la revue obligatoire manque : seule cette raison bloque.
    assert not pr.mergeable and pr.approvals == 0
    assert [r.kind for r in pr.blocking_reasons] == ["approvals"]
    card = box.card()
    assert card["merge"]["enabled"] is False
    assert [r["kind"] for r in card["merge"]["reasons"]] == ["approvals"]
    assert "0 sur 1" in card["merge"]["reasons"][0]["text"]
    assert card["review"]["counter_text"] == "Approbations : 0 sur 1"
    # Le collègue n'a rien dit : la revue ne vient pas toute seule, mais elle peut être demandée.
    assert card["review"]["entries"] == []
    assert card["review"]["can_request"] and card["review"]["request_enabled"]
    assert "review" not in box.evidence()
    box.intent("pr_request_review", number=1)
    pr = box.pr()
    assert [r.state for r in pr.reviews] == ["commented", "approved"]
    assert pr.approvals == 1 and pr.mergeable
    card = box.card()
    assert card["merge"]["enabled"] is True
    assert card["review"]["can_request"] is False  # la réaction a joué, une fois
    assert box.evidence() == ["review"]
    box.wait_step("merger_la_pr")
    box.intent("pr_merge", number=1)
    assert box.pr().state == "merged"


def test_la_revue_ne_se_demande_pas_avant_les_checks_verts(
    make_box, fakes: Fakes
) -> None:
    fakes.pytest_pause = 4.0
    box = make_box("pr-sans-revue", "no_ai")
    box.line("git push -u origin test-quantite")
    box.intent("pr_open", head="test-quantite")
    card = box.card()
    assert card["review"]["can_request"] and not card["review"]["request_enabled"]
    assert "checks" in card["review"]["request_disabled_text"]
    box.intent("pr_request_review", number=1)
    assert "ne sont pas tous verts" in box.outputs()
    assert box.pr().reviews == [] and "review" not in box.evidence()
    # La demande aboutit une fois les checks verts, et seulement alors.
    box.wait_step("demander_la_revue")
    box.intent("pr_request_review", number=1)
    assert box.pr().approvals == 1


def test_une_demande_de_revue_sans_pr_ouverte_est_refusee(make_box) -> None:
    box = make_box("pr-sans-revue", "no_ai")
    box.intent("pr_request_review", number=1)
    assert "n'est pas ouverte" in box.outputs()
    assert "review" not in box.evidence()


def test_un_nouveau_commit_rearme_la_demande_de_revue(make_box) -> None:
    box = make_box("pr-sans-revue", "no_ai")
    box.line("git push -u origin test-quantite")
    box.intent("pr_open", head="test-quantite")
    box.wait_step("demander_la_revue")
    box.intent("pr_request_review", number=1)
    assert box.pr().approvals == 1
    box.line('git commit --allow-empty -m "Précise le test"')
    box.line("git push")
    deadline = time.monotonic() + WAIT
    while time.monotonic() < deadline and box.card()["review"]["request_enabled"] is False:
        time.sleep(0.05)
    assert box.card()["review"]["can_request"] and box.card()["review"]["request_enabled"]


# ------------------------------------------------------------------- push direct sur main
@pytest.mark.parametrize("track", TRACKS)
def test_push_direct_sur_main_est_refuse_puis_la_pr_passe(make_box, track: str) -> None:
    box = make_box("push-direct-main", track)
    box.line("git add CHANGELOG.md")
    assert box.current() == "committer_sur_main"
    box.line('git commit -m "Ajoute le journal des changements"')
    assert box.current() == "pousser_sur_main"
    # Les autres commandes ne valident pas l'étape : seul le refus le fait.
    box.line("git fetch")
    box.line("git status")
    assert box.current() == "pousser_sur_main"
    assert box.evidence() == []
    origin_main = github_sim.origin_branches(box.git, box.engine.layout)["main"]
    box.line("git push origin main")
    out = box.outputs()
    assert "protégée" in out  # la sortie réelle du refus (hook pre-receive de l'origine)
    assert REFUSAL in out
    assert out.rindex(REFUSAL) > out.index("protégée")  # le résumé suit la sortie réelle
    assert box.current() == "pousser_une_branche"
    assert box.evidence() == ["protection"]
    # `main` de l'origine n'a pas bougé.
    assert github_sim.origin_branches(box.git, box.engine.layout)["main"] == origin_main
    box.line("git switch -c ajout-changelog")
    box.line("git push -u origin ajout-changelog")
    assert box.current() == "ouvrir_la_pr"
    box.intent("pr_open", head="ajout-changelog")
    assert box.current() == "merger_la_pr"
    assert box.pr().mergeable  # aucune règle ne bloque cette PR
    box.intent("pr_merge", number=1)
    assert box.pr().state == "merged"


def test_un_push_accepte_ne_valide_pas_l_etape_du_refus(make_box) -> None:
    """Un push vers une autre branche réussit : ni refus, ni preuve, l'étape reste ouverte."""
    box = make_box("push-direct-main", "no_ai")
    box.line("git add CHANGELOG.md")
    box.line('git commit -m "Ajoute le journal des changements"')
    box.line("git push origin main:ailleurs")
    assert box.current() == "pousser_sur_main"
    assert box.evidence() == []
