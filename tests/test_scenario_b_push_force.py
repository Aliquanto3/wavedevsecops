"""Story 5.7 : le scénario B « push / pull » (`push --force` d'un agent qui écrase un collègue).

Joué de bout en bout sur un vrai git, dans les deux parcours : setup, désignation (commit écrasé,
commit forcé, fausse), restauration par plusieurs suites de commandes, contournements refusés.
"""

from __future__ import annotations

import warnings
from collections.abc import Callable, Iterator
from pathlib import Path

import pytest

from wavedevsecops import terminal
from wavedevsecops.config import Settings
from wavedevsecops.engine import (
    WorkspaceEngine,
    WorkspaceManager,
    build_operation,
    designation,
    load_run,
)
from wavedevsecops.events import Envelope, Kind
from wavedevsecops.gitio import Git
from wavedevsecops.projections import EXPLAIN_REFS
from wavedevsecops.scenarios import load_scenario
from wavedevsecops.scenarios.steps._base import BLANK

WAIT = 60.0
TRACKS = ("llm", "no_ai")
COLLEGUE = "Ajoute le guide de contribution"
AGENT = "Ajoute les tests de bonjour"
DEPART = "Ajoute la fonction bonjour"
SCENARIO = "push-pull.B.yaml"
STEP = "restaurer"


class Box:
    def __init__(self, manager: WorkspaceManager, engine: WorkspaceEngine, git: Git, events):
        self.manager, self.engine, self.git, self.events = manager, engine, git, events

    @property
    def repo(self) -> Path:
        return self.engine.layout.repo

    def line(self, text: str) -> list[Envelope]:
        start = len(self.events)
        op = terminal.build_terminal_line(self.engine, terminal.TerminalLine(line=text))
        self.engine.submit(op).result(WAIT)
        return self.events[start:]

    def step_id(self) -> str | None:
        return load_run(self.engine.layout).get("step_id")

    def verdicts(self, step_id: str) -> list[dict]:
        return [
            e.payload
            for e in self.events
            if e.kind == Kind.STEP_VERDICT and e.payload["step_id"] == step_id
        ]

    def commits(self) -> dict[str, dict]:
        return {c["subject"]: c for c in self.engine.last_projection.views["repo"]["commits"]}

    def sha(self, subject: str) -> str:
        return self.commits()[subject]["sha"]

    def answer(self, element: str, step_id: str = "designer") -> dict:
        start = len(self.events)
        op = build_operation(self.engine, "answer_submit", {"slots": [element], "step_id": step_id})
        self.engine.submit(op).result(WAIT)
        corrected = next(e for e in self.events[start:] if e.kind == Kind.ANSWER_CORRECTED)
        return corrected.payload

    def git_out(self, *args: str) -> str:
        return self.git.internal(*args, cwd=self.repo)

    def origin_log(self) -> list[str]:
        out = self.git.internal("log", "--format=%s", "main", cwd=self.engine.layout.origin)
        return out.splitlines()


@pytest.fixture
def make_box(tmp_path: Path, git_path: Path) -> Iterator[Callable[..., Box]]:
    boxes: list[Box] = []
    terminal.AFTER_COMMAND_HOOKS.clear()
    terminal.register_intents()
    designation.register_intents()

    def make(track: str = "llm") -> Box:
        settings = Settings(data_dir=tmp_path / f"data-{len(boxes)}")
        loaded = load_scenario(settings.scenarios_path() / SCENARIO, settings)
        manager = WorkspaceManager(settings, git_path=git_path, watch=False)
        events: list[Envelope] = []
        manager.events(f"{track}.push-pull.B").attach(None, events.append)
        engine, setup = manager.create(loaded, track)
        setup.result(WAIT)
        box = Box(
            manager, engine, Git.for_workspace(git_path, engine.layout.root, settings), events
        )
        boxes.append(box)
        return box

    yield make
    for box in boxes:
        box.manager.close()
    terminal.AFTER_COMMAND_HOOKS.clear()


# ------------------------------------------------------------------------------------- contenu
def test_contenu_complet_et_sans_avertissement() -> None:
    settings = Settings()
    scenario = load_scenario(
        settings.scenarios_path() / SCENARIO, settings, explain_keys=EXPLAIN_REFS
    ).scenario
    assert scenario.mode == "B" and sorted(scenario.tracks) == ["llm", "no_ai"]
    assert scenario.catalogue and scenario.section is None
    assert [s.type for s in scenario.steps] == ["designate", "origin_contains"]
    with warnings.catch_warnings():
        assert not scenario.authoring_warnings()
    for step in scenario.steps:
        assert step.instruction_text.strip() and step.explanation_text.strip()
        assert step.hints is not None and BLANK in step.hints.partial_text
        # Le premier palier ne donne pas la réponse.
        assert "cherry-pick" not in step.hints.lead_text


def test_les_textes_visibles_sont_au_vouvoiement() -> None:
    settings = Settings()
    scenario = load_scenario(settings.scenarios_path() / SCENARIO, settings).scenario
    for step in scenario.steps:
        for text in (step.instruction_text, step.explanation_text, step.hints.lead_text):
            words = f" {text.lower()} ".replace("'", " ")
            assert " tu " not in words and " ton " not in words and " ta " not in words


# ------------------------------------------------------------------------------------ setup
@pytest.mark.slow
@pytest.mark.parametrize("track", TRACKS)
def test_le_commit_du_collegue_n_est_plus_sur_origin_mais_visible_par_reflog(
    make_box, track: str
) -> None:
    box = make_box(track)
    commits = box.commits()
    # Plus sur `origin/main` : l'agent l'a écrasé.
    assert box.origin_log() == [AGENT, DEPART, "Ajoute le README"]
    # Visible en local, en tirets : plus aucune ref n'y mène, le reflog le cite.
    assert commits[COLLEGUE]["lost"] is True and commits[COLLEGUE]["actor"] == "colleague"
    assert commits[AGENT]["lost"] is False and commits[AGENT]["actor"] == "agent"
    refs = {r["name"]: r["commit"] for r in box.engine.last_projection.views["repo"]["refs"]}
    assert refs["refs/remotes/origin/main"] == commits[AGENT]["sha"]
    assert refs["refs/heads/main"] == commits[DEPART]["sha"]
    reflog = box.git_out("reflog", "show", "--format=%H", "refs/remotes/origin/main").split()
    assert commits[COLLEGUE]["sha"] in reflog
    assert box.step_id() == "designer"
    panel = box.engine.snapshot()["step_panel"]
    current = next(s for s in panel["steps"] if s["state"] == "current")
    assert current["designate"]["accept"] == ["commit"]


# ------------------------------------------------------------------------------ désignation
@pytest.mark.slow
@pytest.mark.parametrize("which", [COLLEGUE, AGENT])
def test_le_commit_ecrase_est_le_principal_et_le_commit_force_l_equivalent(
    make_box, which: str
) -> None:
    box = make_box()
    payload = box.answer(f"commit:{box.sha(which)}")
    mark = payload["slots"][0]
    assert payload["correct"] is True and mark["correct"] is True
    assert mark["expected_element_id"] == f"commit:{box.sha(COLLEGUE)}"
    assert set(mark["accepted_element_ids"]) == {
        f"commit:{box.sha(COLLEGUE)}",
        f"commit:{box.sha(AGENT)}",
    }
    assert mark["equivalent"] is (which == AGENT)
    assert box.step_id() == STEP


@pytest.mark.slow
def test_une_designation_fausse_est_corrigee_une_fois_et_ferme_l_etape(make_box) -> None:
    box = make_box("no_ai")
    payload = box.answer(f"commit:{box.sha(DEPART)}")
    mark = payload["slots"][0]
    assert payload["correct"] is False and mark["correct"] is False
    assert mark["expected_element_id"] == f"commit:{box.sha(COLLEGUE)}"
    assert box.step_id() == STEP
    assert load_run(box.engine.layout)["answers"]["designer"]["correct"] is False


# ----------------------------------------------------------------------------- restauration
def _to_repair(box: Box) -> str:
    box.answer(f"commit:{box.sha(COLLEGUE)}")
    assert box.step_id() == STEP
    return box.sha(COLLEGUE)


def _restored(box: Box) -> None:
    assert box.step_id() is None
    assert box.engine.snapshot()["step_panel"]["summary"] is not None
    assert box.verdicts(STEP)[-1]["passed"] is True


def _still_open(box: Box) -> dict:
    assert box.step_id() == STEP
    verdict = box.verdicts(STEP)[-1]
    assert verdict["passed"] is False
    return verdict


@pytest.mark.slow
@pytest.mark.parametrize("track", TRACKS)
def test_merge_puis_push_valide_et_garde_le_travail_de_l_agent(make_box, track: str) -> None:
    box = make_box(track)
    sha = _to_repair(box)
    for line in ("git merge origin/main", f"git merge {sha}"):
        box.line(line)
        assert box.step_id() == STEP  # rien n'est encore sur origin
    box.line("git push")
    _restored(box)
    log = box.origin_log()
    assert COLLEGUE in log and AGENT in log
    files = box.git.internal("ls-tree", "-r", "--name-only", "main", cwd=box.engine.layout.origin)
    assert {"docs/guide.md", "tests/test_bonjour.py"} <= set(files.split())


@pytest.mark.slow
def test_rebase_du_commit_perdu_valide_par_son_patch(make_box) -> None:
    """Le commit rejoué a un autre SHA mais le même patch : le travail du collègue est revenu."""
    box = make_box()
    sha = _to_repair(box)
    for line in (f"git switch -c restaure {sha}", "git rebase origin/main"):
        box.line(line)
    box.line("git push origin restaure:main")
    _restored(box)
    assert sha not in box.git.internal("rev-list", "main", cwd=box.engine.layout.origin).split()


# ------------------------------------------------------------------------- contournements
@pytest.mark.slow
def test_restaurer_l_ancien_sommet_de_force_efface_le_travail_de_l_agent(make_box) -> None:
    box = make_box()
    sha = _to_repair(box)
    box.line(f"git push --force origin {sha}:main")
    verdict = _still_open(box)
    assert (
        box.sha(COLLEGUE)
        in box.git.internal("rev-list", "main", cwd=box.engine.layout.origin).split()
    )
    assert AGENT not in box.origin_log()
    assert f"commit:{box.sha(AGENT)}" in [o["element_id"] for o in verdict["observed"]]


@pytest.mark.slow
def test_integrer_en_local_sans_pousser_ne_valide_pas(make_box) -> None:
    box = make_box()
    sha = _to_repair(box)
    box.line("git merge origin/main")
    box.line(f"git merge {sha}")
    verdict = _still_open(box)
    assert "manque encore" in verdict["reason_text"]
    assert COLLEGUE not in box.origin_log()


@pytest.mark.slow
def test_recuperer_seulement_ne_valide_pas(make_box) -> None:
    box = make_box()
    _to_repair(box)
    box.line("git fetch")
    box.line("git pull")
    assert box.step_id() == STEP
    assert COLLEGUE not in box.origin_log()


@pytest.mark.slow
def test_un_fichier_refait_a_la_main_avec_un_autre_contenu_ne_valide_pas(make_box) -> None:
    box = make_box()
    _to_repair(box)
    box.line("git merge origin/main")
    box.line('echo "autre texte" > docs/guide.md')
    box.line("git add docs/guide.md")
    box.line(f'git commit -m "{COLLEGUE}"')
    box.line("git push")
    _still_open(box)  # même message, mais pas le commit du collègue ni son patch


@pytest.mark.slow
def test_un_commit_au_meme_message_que_celui_du_collegue_ne_suffit_pas(make_box) -> None:
    box = make_box()
    _to_repair(box)
    box.line("git merge origin/main")
    box.line('git commit --allow-empty -m "Ajoute le guide de contribution"')
    box.line("git push")
    _still_open(box)


@pytest.mark.slow
def test_la_branche_origin_supprimee_est_signalee(make_box) -> None:
    box = make_box()
    _to_repair(box)
    box.line("git push origin :main")
    verdict = box.verdicts(STEP)[-1] if box.verdicts(STEP) else None
    assert box.step_id() == STEP
    if verdict is not None:
        assert verdict["passed"] is False


@pytest.mark.slow
def test_lecture_seule_ne_dit_rien(make_box) -> None:
    box = make_box()
    _to_repair(box)
    before = len(box.verdicts(STEP))
    box.line("git log --oneline")
    assert len(box.verdicts(STEP)) == before
