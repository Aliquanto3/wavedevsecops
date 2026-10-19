"""Story 5.6 : le scénario B « add / commit » (`.env` committé par l'agent).

Joué de bout en bout sur un vrai git, dans les deux parcours : setup de l'agent, désignation
(juste par chaque élément accepté, fausse), réparation de l'historique par plusieurs suites de
commandes, bilan.
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
LEAK = "Ajoute la configuration de l'API"
CLIENT = "Ajoute le client de l'API"
FIX = (
    "git reset --soft HEAD~1",
    "git rm --cached .env",
    'echo ".env" >> .gitignore',
    "git add .gitignore",
    f'git commit -m "{LEAK}"',
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

    def commits(self) -> dict[str, dict]:
        return {c["subject"]: c for c in self.engine.last_projection.views["repo"]["commits"]}

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

    def make(track: str = "llm") -> Box:
        settings = Settings(data_dir=tmp_path / f"data-{len(boxes)}")
        loaded = load_scenario(settings.scenarios_path() / "add-commit.B.yaml", settings)
        manager = WorkspaceManager(settings, git_path=git_path, watch=False)
        events: list[Envelope] = []
        manager.events(f"{track}.add-commit.B").attach(None, events.append)
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
        settings.scenarios_path() / "add-commit.B.yaml", settings, explain_keys=EXPLAIN_REFS
    ).scenario
    assert scenario.mode == "B" and sorted(scenario.tracks) == ["llm", "no_ai"]
    assert scenario.catalogue and scenario.section is None
    assert [s.type for s in scenario.steps] == ["designate", "history_clean"]
    with warnings.catch_warnings():
        assert not scenario.authoring_warnings()
    for step in scenario.steps:
        assert step.instruction_text.strip() and step.explanation_text.strip()
        assert step.hints is not None and BLANK in step.hints.partial_text
        # Le premier palier ne donne pas la réponse.
        assert ".env" not in step.hints.lead_text and "--soft" not in step.hints.lead_text


def test_les_textes_visibles_sont_au_vouvoiement() -> None:
    settings = Settings()
    scenario = load_scenario(settings.scenarios_path() / "add-commit.B.yaml", settings).scenario
    for step in scenario.steps:
        for text in (step.instruction_text, step.explanation_text, step.hints.lead_text):
            words = f" {text.lower()} ".replace("'", " ")
            assert " tu " not in words and " ton " not in words and " ta " not in words


# ------------------------------------------------------------------------------------ setup
@pytest.mark.slow
@pytest.mark.parametrize("track", TRACKS)
def test_l_agent_a_fait_deux_commits_dont_l_un_ajoute_env(make_box, track: str) -> None:
    box = make_box(track)
    commits = box.commits()
    assert commits[CLIENT]["actor"] == commits[LEAK]["actor"] == "agent"
    assert commits[LEAK]["parents"] == [commits[CLIENT]["sha"]]
    agents = [c for c in commits.values() if c["actor"] == "agent"]
    assert len(agents) == 2
    added = box.git_out("show", "--name-only", "--format=", commits[LEAK]["sha"]).split()
    assert added == [".env"]
    assert "API_KEY=" in box.git_out("show", f"{commits[LEAK]['sha']}:.env")
    # La clé n'a pas quitté le poste : `origin` n'a que le départ de l'apprenant.
    origin = box.git.internal("log", "--format=%s", "main", cwd=box.engine.layout.origin)
    assert origin.splitlines()[0] == "Ajoute la fonction bonjour"
    assert box.step_id() == "designer"
    panel = box.engine.snapshot()["step_panel"]
    current = next(s for s in panel["steps"] if s["state"] == "current")
    assert current["designate"]["accept"] == ["commit", "path", "diffline"]
    assert current["designate"]["question_text"] == "Qu'a fait l'agent ?"


# ------------------------------------------------------------------------------ désignation
def _elements(box: Box) -> dict[str, str]:
    sha = box.commits()[LEAK]["sha"]
    return {
        "commit": f"commit:{sha}",
        "fichier": "path:head:.env",
        "ligne": f"diffline:{sha}:.env:new:1",
    }


@pytest.mark.slow
@pytest.mark.parametrize("which", ["commit", "fichier", "ligne"])
def test_chaque_element_accepte_est_juste_et_le_commit_est_le_principal(
    make_box, which: str
) -> None:
    box = make_box()
    elements = _elements(box)
    payload = box.answer(elements[which])
    mark = payload["slots"][0]
    assert payload["correct"] is True and mark["correct"] is True
    assert mark["expected_element_id"] == elements["commit"]
    assert set(mark["accepted_element_ids"]) == set(elements.values())
    assert mark["equivalent"] is (which != "commit")
    assert box.step_id() == "retirer_de_l_historique"


@pytest.mark.slow
def test_le_sha_saisi_se_resout_en_commit_accepte(make_box) -> None:
    """La liste ou le SHA désignent un `commit:<sha>` : la même bonne réponse (5.2, 5.4)."""
    box = make_box()
    full = box.commits()[LEAK]["sha"]
    status, resolved = designation.resolve_sha(box.engine.last_projection.views, full[:10])
    assert status == 200 and resolved["element_id"] == f"commit:{full}"
    assert box.answer(resolved["element_id"])["correct"] is True


@pytest.mark.slow
def test_la_ligne_du_diff_est_celle_de_la_cle(make_box) -> None:
    box = make_box()
    sha = box.commits()[LEAK]["sha"]
    run = load_run(box.engine.layout)
    assert run["aliases"]["ligne-cle"] == f"diffline:{sha}:.env:new:1"
    assert box.git_out("show", f"{sha}:.env").splitlines()[0].startswith("API_KEY=")


@pytest.mark.slow
def test_une_designation_fausse_est_corrigee_une_fois_et_ferme_l_etape(make_box) -> None:
    box = make_box("no_ai")
    elements = _elements(box)
    wrong = f"commit:{box.commits()[CLIENT]['sha']}"
    payload = box.answer(wrong)
    mark = payload["slots"][0]
    assert payload["correct"] is False and mark["correct"] is False
    assert mark["expected_element_id"] == elements["commit"]
    assert "Ajoute la configuration de l'API" in mark["text"]
    assert box.step_id() == "retirer_de_l_historique"
    assert load_run(box.engine.layout)["answers"]["designer"]["correct"] is False


# ----------------------------------------------------------------------------- réparation
def _to_repair(box: Box) -> None:
    box.answer(_elements(box)["commit"])
    assert box.step_id() == "retirer_de_l_historique"


def _fixed(box: Box) -> None:
    assert box.step_id() is None
    summary = box.engine.snapshot()["step_panel"]["summary"]
    assert summary is not None


@pytest.mark.slow
@pytest.mark.parametrize("track", TRACKS)
def test_la_solution_valide_l_etape_et_le_bilan_s_affiche(make_box, track: str) -> None:
    box = make_box(track)
    _to_repair(box)
    for line in FIX[:2]:
        box.line(line)
        assert box.step_id() == "retirer_de_l_historique"
    # Dès que l'historique est propre et que `.env` est ignoré, l'étape est validée : la suite
    # (re-commiter la configuration sans `.env`) est libre.
    box.line(FIX[2])
    _fixed(box)
    for line in FIX[3:]:
        box.line(line)
    assert box.verdicts("retirer_de_l_historique")[-1]["passed"] is True
    assert (box.repo / ".env").is_file()  # la clé reste sur le disque, hors de git
    assert box.git_out("ls-files").split() == [
        ".gitignore",
        "README.md",
        "src/bonjour.py",
        "src/client.py",
    ]
    leaked = box.git_out("log", "--all", "--format=%H", "--", ".env").split()
    assert leaked == []


@pytest.mark.slow
def test_une_autre_suite_de_commandes_valide_aussi(make_box) -> None:
    box = make_box()
    _to_repair(box)
    box.line("git reset --hard HEAD~1")
    assert box.step_id() == "retirer_de_l_historique"  # .env n'est pas encore ignoré
    box.line('echo ".env" > .gitignore')
    box.line("git add .gitignore")
    box.line('git commit -m "Ignore .env"')
    _fixed(box)


@pytest.mark.slow
def test_supprimer_dans_un_nouveau_commit_ne_suffit_pas(make_box) -> None:
    box = make_box()
    _to_repair(box)
    box.line('echo ".env" >> .gitignore')
    box.line("git rm --cached .env")
    box.line("git add .gitignore")
    box.line('git commit -m "Retire .env"')
    verdict = box.verdicts("retirer_de_l_historique")[-1]
    assert verdict["passed"] is False and verdict["status"] == "failed"
    assert "encore dans l'historique" in verdict["reason_text"]
    leak = box.commits()[LEAK]["sha"]
    assert any(o["element_id"] == f"commit:{leak}" for o in verdict["observed"])
    assert box.step_id() == "retirer_de_l_historique"


@pytest.mark.slow
def test_amend_change_le_sha_mais_pas_le_contenu(make_box) -> None:
    box = make_box()
    _to_repair(box)
    old = box.commits()[LEAK]["sha"]
    box.line('git commit --amend -m "Ajoute la config de l\'API"')
    assert old not in {
        c["sha"] for c in box.engine.last_projection.views["repo"]["commits"] if not c["lost"]
    }
    assert box.step_id() == "retirer_de_l_historique"
    assert "encore dans l'historique" in box.verdicts("retirer_de_l_historique")[-1]["reason_text"]


@pytest.mark.slow
def test_le_fichier_retire_mais_non_ignore_est_signale(make_box) -> None:
    box = make_box()
    _to_repair(box)
    box.line("git reset --hard HEAD~1")
    verdict = box.verdicts("retirer_de_l_historique")[-1]
    assert verdict["passed"] is False and "rien ne l'ignore" in verdict["reason_text"]
    assert box.step_id() == "retirer_de_l_historique"


@pytest.mark.slow
def test_le_commit_cache_dans_le_stash_ou_une_branche_compte(make_box) -> None:
    box = make_box()
    _to_repair(box)
    box.line("git branch sauvegarde")
    for line in FIX:
        box.line(line)
    assert box.step_id() == "retirer_de_l_historique"  # `sauvegarde` mène encore à .env
    box.line("git branch -D sauvegarde")
    _fixed(box)


@pytest.mark.slow
def test_lecture_seule_ne_dit_rien(make_box) -> None:
    box = make_box()
    _to_repair(box)
    before = len(box.verdicts("retirer_de_l_historique"))
    box.line("git log --oneline")
    assert len(box.verdicts("retirer_de_l_historique")) == before


@pytest.mark.slow
def test_env_encore_dans_l_index_n_est_pas_valide(make_box) -> None:
    """Revue : après `reset --soft`, `.env` reste indexé ; l'ignorer ne suffit pas, le
    prochain commit le remettrait dans l'historique."""
    box = make_box()
    _to_repair(box)
    box.line("git reset --soft HEAD~1")
    box.line('echo ".env" >> .gitignore')
    assert box.step_id() == "retirer_de_l_historique"
    verdict = box.verdicts("retirer_de_l_historique")[-1]
    assert verdict["passed"] is False and "l'index le suit encore" in verdict["reason_text"]
    box.line("git rm --cached .env")
    _fixed(box)


@pytest.mark.slow
def test_les_refs_qui_menent_au_commit_sont_nommees(make_box) -> None:
    """Revue : une sauvegarde (branche, `refs/original/` de `filter-branch`) qui garde le commit
    est nommée dans la raison de l'échec."""
    box = make_box()
    _to_repair(box)
    leak = box.commits()[LEAK]["sha"]
    box.git_out("update-ref", "refs/original/refs/heads/main", leak)
    box.line("git reset --hard HEAD~1")
    box.line('echo ".env" > .gitignore')
    reason = box.verdicts("retirer_de_l_historique")[-1]["reason_text"]
    assert "`refs/original/refs/heads/main`" in reason and "filter-branch" in reason
    assert "`main`" not in reason
    box.git_out("update-ref", "-d", "refs/original/refs/heads/main")
    box.line("git add .gitignore")
    _fixed(box)
