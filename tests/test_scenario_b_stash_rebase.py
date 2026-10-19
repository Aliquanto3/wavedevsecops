"""Story 5.8 : les scénarios B « stash » (stash oublié par l'agent) et « rebase » (rebase laissé
en conflit par l'agent).

Joués de bout en bout sur un vrai git, dans les deux parcours : setup, désignation (juste,
équivalente, fausse), réparation par plusieurs suites de commandes, contournements refusés.
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
FILES = {"stash": "stash.B.yaml", "rebase": "rebase.B.yaml"}
AGENT_COMMIT = "Raccourcit le salut"
SOLVED = (
    'echo "def bonjour(nom: str) -> str:" > src/bonjour.py',
    "echo \"    return f'Salut, {nom} ! Bienvenue.'\" >> src/bonjour.py",
)


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

    def views(self) -> dict:
        return self.engine.last_projection.views

    def commits(self) -> dict[str, dict]:
        return {c["subject"]: c for c in self.views()["repo"]["commits"]}

    def answer(self, element: str, step_id: str = "designer") -> dict:
        start = len(self.events)
        op = build_operation(self.engine, "answer_submit", {"slots": [element], "step_id": step_id})
        self.engine.submit(op).result(WAIT)
        corrected = next(e for e in self.events[start:] if e.kind == Kind.ANSWER_CORRECTED)
        return corrected.payload

    def git_out(self, *args: str) -> str:
        return self.git.internal(*args, cwd=self.repo)


@pytest.fixture
def make_box(tmp_path: Path, git_path: Path) -> Iterator[Callable[..., Box]]:
    boxes: list[Box] = []
    terminal.AFTER_COMMAND_HOOKS.clear()
    terminal.register_intents()
    designation.register_intents()

    def make(scenario: str, track: str = "llm") -> Box:
        settings = Settings(data_dir=tmp_path / f"data-{len(boxes)}")
        loaded = load_scenario(settings.scenarios_path() / FILES[scenario], settings)
        manager = WorkspaceManager(settings, git_path=git_path, watch=False)
        events: list[Envelope] = []
        manager.events(f"{track}.{scenario}.B").attach(None, events.append)
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
@pytest.mark.parametrize("scenario", FILES)
def test_contenu_complet_et_sans_avertissement(scenario: str) -> None:
    settings = Settings()
    loaded = load_scenario(
        settings.scenarios_path() / FILES[scenario], settings, explain_keys=EXPLAIN_REFS
    ).scenario
    assert loaded.mode == "B" and sorted(loaded.tracks) == ["llm", "no_ai"]
    assert loaded.catalogue and loaded.section is None
    with warnings.catch_warnings():
        assert not loaded.authoring_warnings()
    for step in loaded.steps:
        assert step.instruction_text.strip() and step.explanation_text.strip()
        assert step.hints is not None and BLANK in step.hints.partial_text
        for text in (step.instruction_text, step.explanation_text, step.hints.lead_text):
            words = f" {text.lower()} ".replace("'", " ")
            assert " tu " not in words and " ton " not in words and " ta " not in words


def test_les_etapes_de_chaque_scenario() -> None:
    settings = Settings()
    types = {
        name: [
            s.type for s in load_scenario(settings.scenarios_path() / file, settings).scenario.steps
        ]
        for name, file in FILES.items()
    }
    assert types == {
        "stash": ["designate", "repo_state"],
        "rebase": ["designate", "quiz", "repo_state", "repo_state"],
    }


def test_les_commandes_enseignees_sont_dans_la_liste_du_terminal() -> None:
    text = (Settings().content_path() / "terminal-allowlist.yaml").read_text(encoding="utf-8")
    for fragment in ("  stash:", "  rebase:", '"pop"', '"--abort"', '"--continue"', '"-a"'):
        assert fragment in text


# ------------------------------------------------------------------------------- stash : setup
@pytest.mark.slow
@pytest.mark.parametrize("track", TRACKS)
def test_stash_le_stash_de_l_agent_existe_et_le_dossier_est_propre(make_box, track: str) -> None:
    box = make_box("stash", track)
    listing = box.git_out("stash", "list", "--format=%gs")
    assert "WIP : fonction au_revoir" in listing
    assert box.git_out("status", "--porcelain") == ""
    stash = box.views()["staging"]["stash"]
    assert len(stash) == 1 and stash[0]["letter"] == "S"
    assert stash[0]["element_id"] == f"commit:{box.git_out('rev-parse', 'refs/stash').strip()}"
    assert box.step_id() == "designer"
    panel = box.engine.snapshot()["step_panel"]
    current = next(s for s in panel["steps"] if s["state"] == "current")
    assert current["designate"]["accept"] == ["commit"]


@pytest.mark.slow
def test_stash_designation_juste_puis_fausse(make_box) -> None:
    box = make_box("stash")
    sha = box.git_out("rev-parse", "refs/stash").strip()
    payload = box.answer(f"commit:{sha}")
    assert payload["correct"] is True and payload["slots"][0]["equivalent"] is False
    assert box.step_id() == "reprendre"
    other = make_box("stash", "no_ai")
    depart = other.commits()["Ajoute la fonction bonjour"]["sha"]
    wrong = other.answer(f"commit:{depart}")
    assert wrong["correct"] is False
    assert (
        wrong["slots"][0]["expected_element_id"]
        == f"commit:{other.git_out('rev-parse', 'refs/stash').strip()}"
    )
    assert other.step_id() == "reprendre"


# ------------------------------------------------------------------------------ stash : reprise
def _to_resume(box: Box) -> None:
    sha = box.git_out("rev-parse", "refs/stash").strip()
    box.answer(f"commit:{sha}")
    assert box.step_id() == "reprendre"


def _done(box: Box, step_id: str) -> None:
    assert box.step_id() != step_id
    assert box.verdicts(step_id)[-1]["passed"] is True


def _open(box: Box, step_id: str) -> dict:
    assert box.step_id() == step_id
    verdict = box.verdicts(step_id)[-1]
    assert verdict["passed"] is False
    return verdict


@pytest.mark.slow
@pytest.mark.parametrize("track", TRACKS)
def test_stash_pop_puis_commit_valide(make_box, track: str) -> None:
    box = make_box("stash", track)
    _to_resume(box)
    box.line("git stash pop")
    assert box.step_id() == "reprendre"  # appliqué, pas encore committé
    box.line("git add src/bonjour.py")
    box.line('git commit -m "Ajoute au_revoir"')
    _done(box, "reprendre")
    assert box.git_out("stash", "list") == ""
    assert "def au_revoir" in (box.repo / "src" / "bonjour.py").read_text(encoding="utf-8")


@pytest.mark.slow
def test_stash_apply_et_commit_a_valide_meme_si_la_pile_garde_l_entree(make_box) -> None:
    box = make_box("stash")
    _to_resume(box)
    for line in ("git stash apply", 'git commit -a -m "Ajoute au_revoir"'):
        box.line(line)
    _done(box, "reprendre")
    assert box.git_out("stash", "list") != ""


@pytest.mark.slow
def test_stash_applique_sans_commit_ne_valide_pas(make_box) -> None:
    box = make_box("stash")
    _to_resume(box)
    box.line("git stash pop")
    box.line("git add src/bonjour.py")
    verdict = _open(box, "reprendre")
    assert verdict["reason_text"].strip()


@pytest.mark.slow
def test_stash_drop_puis_reecriture_differente_ne_valide_pas(make_box) -> None:
    box = make_box("stash")
    _to_resume(box)
    box.line("git stash drop")
    box.line('echo "# autre chose" >> src/bonjour.py')
    box.line('git commit -a -m "Travail refait"')
    _open(box, "reprendre")


@pytest.mark.slow
def test_stash_drop_sans_rien_refaire_ne_valide_pas(make_box) -> None:
    box = make_box("stash")
    _to_resume(box)
    box.line("git stash drop")
    box.line('git commit --allow-empty -m "Rien"')
    _open(box, "reprendre")


@pytest.mark.slow
def test_stash_lecture_seule_ne_dit_rien(make_box) -> None:
    box = make_box("stash")
    _to_resume(box)
    before = len(box.verdicts("reprendre"))
    box.line("git stash list")
    assert len(box.verdicts("reprendre")) == before


# ------------------------------------------------------------------------------ rebase : setup
@pytest.mark.slow
@pytest.mark.parametrize("track", TRACKS)
def test_rebase_le_depot_est_au_milieu_d_un_rebase_en_conflit(make_box, track: str) -> None:
    box = make_box("rebase", track)
    assert box.views()["repo"]["in_progress"] == "rebase"
    assert "<<<<<<<" in (box.repo / "src" / "bonjour.py").read_text(encoding="utf-8")
    assert box.git_out("diff", "--name-only", "--diff-filter=U").strip() == "src/bonjour.py"
    commits = box.commits()
    assert commits[AGENT_COMMIT]["actor"] == "agent"
    assert box.step_id() == "designer"
    panel = box.engine.snapshot()["step_panel"]
    current = next(s for s in panel["steps"] if s["state"] == "current")
    assert sorted(current["designate"]["accept"]) == ["commit", "path"]


@pytest.mark.slow
@pytest.mark.parametrize("answer", ["commit", "path"])
def test_rebase_designation_du_commit_principal_ou_du_fichier_equivalent(
    make_box, answer: str
) -> None:
    box = make_box("rebase")
    sha = box.commits()[AGENT_COMMIT]["sha"]
    element = f"commit:{sha}" if answer == "commit" else "path:worktree:src/bonjour.py"
    payload = box.answer(element)
    assert payload["correct"] is True
    assert payload["slots"][0]["equivalent"] is (answer == "path")
    assert box.step_id() == "sortir"


@pytest.mark.slow
def test_rebase_designation_fausse(make_box) -> None:
    box = make_box("rebase", "no_ai")
    depart = box.commits()["Ajoute la fonction bonjour"]["sha"]
    payload = box.answer(f"commit:{depart}")
    assert payload["correct"] is False
    assert box.step_id() == "sortir"


# ------------------------------------------------------------------------------ rebase : sortie
def _resolve_gestures() -> tuple[str, ...]:
    return (*SOLVED, "git add src/bonjour.py", "git rebase --continue")


@pytest.mark.slow
def test_rebase_resoudre_puis_continue_valide(make_box) -> None:
    box = make_box("rebase")
    _skip_quiz(box)
    for gesture in _resolve_gestures():
        box.line(gesture)
    _done(box, "resoudre")
    assert box.views()["repo"]["in_progress"] == ""
    log = box.git_out("log", "--format=%s", "feature").splitlines()
    assert log[:2] == [AGENT_COMMIT, "Ajoute une formule de bienvenue"]


def _skip_quiz(box: Box) -> None:
    box.answer(f"commit:{box.commits()[AGENT_COMMIT]['sha']}")
    assert box.step_id() == "sortir"
    op = build_operation(box.engine, "quiz_choice", {"choice_id": "abort"})
    box.engine.submit(op).result(WAIT)
    assert box.step_id() == "relancer"
    box.line("git rebase origin/main")
    assert box.step_id() == "resoudre"


# ------------------------------------------------------------------------- rebase : contournements
@pytest.mark.slow
def test_rebase_continue_avec_marqueurs_ne_valide_pas(make_box) -> None:
    box = make_box("rebase")
    _skip_quiz(box)
    box.line("git add src/bonjour.py")  # marqueurs encore présents
    box.line("git rebase --continue")
    verdict = _open(box, "resoudre")
    assert "marqueurs" in verdict["reason_text"]


@pytest.mark.slow
def test_rebase_abort_puis_fusion_ne_valide_pas(make_box) -> None:
    box = make_box("rebase")
    _skip_quiz(box)
    box.line("git rebase --abort")
    box.line("git merge origin/main")
    for gesture in SOLVED:
        box.line(gesture)
    box.line("git add src/bonjour.py")
    box.line('git commit -m "Fusionne origin/main"')
    verdict = _open(box, "resoudre")
    assert "fusion" in verdict["reason_text"]


@pytest.mark.slow
def test_rebase_skip_ecarte_le_travail_de_l_agent_et_ne_valide_pas(make_box) -> None:
    box = make_box("rebase")
    _skip_quiz(box)
    box.line("git rebase --skip")
    _open(box, "resoudre")
    assert AGENT_COMMIT not in box.git_out("log", "--format=%s", "feature")


@pytest.mark.slow
def test_rebase_abandon_seul_ne_valide_pas(make_box) -> None:
    box = make_box("rebase")
    _skip_quiz(box)
    box.line("git rebase --abort")
    _open(box, "resoudre")  # feature est revenue à son état d'avant : il faut relancer le rebase
    assert box.views()["repo"]["in_progress"] == ""


@pytest.mark.slow
def test_rebase_abort_du_quiz_rend_la_branche_puis_demande_de_relancer(make_box) -> None:
    box = make_box("rebase")
    box.answer(f"commit:{box.commits()[AGENT_COMMIT]['sha']}")
    before = box.git_out("rev-parse", "feature").strip()
    op = build_operation(box.engine, "quiz_choice", {"choice_id": "abort"})
    box.engine.submit(op).result(WAIT)
    assert box.views()["repo"]["in_progress"] == ""
    assert box.git_out("rev-parse", "feature").strip() == before
    assert box.step_id() == "relancer"


@pytest.mark.slow
def test_rebase_le_quiz_skip_perd_le_travail_et_ne_passe_pas(make_box) -> None:
    box = make_box("rebase")
    box.answer(f"commit:{box.commits()[AGENT_COMMIT]['sha']}")
    op = build_operation(box.engine, "quiz_choice", {"choice_id": "skip"})
    box.engine.submit(op).result(WAIT)
    assert box.step_id() == "sortir"
    assert box.verdicts("sortir")[-1]["passed"] is False
