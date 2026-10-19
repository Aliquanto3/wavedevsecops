"""Stories 6.2 et 6.3 : les huit scénarios A du socle git (« add-commit » à « recuperation »).

Contenu : lint (consignes, explications, trois paliers d'indice par étape), et chaque scénario
joué de bout en bout, dans les deux parcours, sur un vrai git : setup, solution de chaque étape
par la file d'opérations, verdict de chaque étape, bilan sans indice.
"""

from __future__ import annotations

import warnings
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from pathlib import Path

import pytest

from wavedevsecops import github_sim, terminal
from wavedevsecops.config import Settings
from wavedevsecops.engine import (
    WorkspaceEngine,
    WorkspaceManager,
    build_operation,
    load_run,
    pr_intents,
)
from wavedevsecops.events import Envelope, Kind
from wavedevsecops.gitio import Git
from wavedevsecops.projections import EXPLAIN_REFS
from wavedevsecops.scenarios import load_scenario, scenario_files
from wavedevsecops.scenarios.order import SOCLE_ORDER
from wavedevsecops.scenarios.steps._base import BLANK

WAIT = 60.0
IDS = SOCLE_ORDER
TRACKS = ("llm", "no_ai")


# ----------------------------------------------------------------------------- jeux de solutions
@dataclass(frozen=True)
class Do:
    """Un geste de l'apprenant : une ligne de terminal, un choix de quiz ou une intention."""

    kind: str  # line | quiz | intent
    value: str
    body: dict = field(default_factory=dict)


def line(text: str) -> Do:
    return Do("line", text)


def quiz(choice_id: str) -> Do:
    return Do("quiz", choice_id)


def intent(name: str, **body) -> Do:
    return Do("intent", name, body)


SOLUTIONS: dict[str, list[tuple[str, list[Do]]]] = {
    "add-commit": [
        ("indexer", [line("git add notes.txt")]),
        ("commiter", [line('git commit -m "Ajoute les notes"')]),
        ("corriger_le_message", [quiz("amend")]),
        (
            "second_commit",
            [
                line('echo "Une ligne en plus" >> README.md'),
                line("git add README.md"),
                line('git commit -m "Complète le README"'),
            ],
        ),
    ],
    "push-pull": [
        ("voir_sans_integrer", [quiz("fetch")]),
        ("recuperer", [line("git pull")]),
        (
            "commiter_a_partager",
            [
                line('echo "À faire" > todo.txt'),
                line("git add todo.txt"),
                line('git commit -m "Ajoute la liste à faire"'),
            ],
        ),
        ("pousser", [line("git push")]),
    ],
    "branche": [
        ("creer_feature", [line("git switch -c feature")]),
        (
            "commiter_sur_feature",
            [
                line('echo "Salut" > salut.txt'),
                line("git add salut.txt"),
                line('git commit -m "Ajoute le salut"'),
            ],
        ),
        ("revenir_sur_main", [quiz("switch_main")]),
        ("fusionner", [quiz("merge_feature")]),
        ("supprimer_feature", [quiz("branch_d")]),
    ],
    "conflit": [
        ("lancer_la_fusion", [line("git merge feature")]),
        (
            "resoudre",
            [
                line('echo "def bonjour(nom: str) -> str:" > src/bonjour.py'),
                line("echo \"    return f'Salut, {nom} ! Bienvenue.'\" >> src/bonjour.py"),
                line("git add src/bonjour.py"),
                line('git commit -m "Fusionne feature"'),
            ],
        ),
    ],
    "stash": [
        ("mettre_de_cote", [quiz("stash")]),
        ("recuperer", [line("git pull")]),
        ("reprendre", [line("git stash pop")]),
    ],
    "rebase": [
        ("recuperer_main", [line("git fetch")]),
        ("lancer_le_rebase", [line("git rebase origin/main")]),
        (
            "resoudre",
            [
                line('echo "def bonjour(nom: str) -> str:" > src/bonjour.py'),
                line("echo \"    return f'Salut, {nom} ! Bienvenue.'\" >> src/bonjour.py"),
                line("git add src/bonjour.py"),
                line("git rebase --continue"),
            ],
        ),
        ("pousser_apres_rebase", [quiz("force_with_lease")]),
    ],
    "recuperation": [
        ("perdre_le_commit", [line("git reset --hard HEAD~1")]),
        ("retrouver", [quiz("reflog")]),
        ("restaurer", [line("git reset --hard HEAD@{1}")]),
    ],
    "pr-merge": [
        (
            "commiter_sur_feature",
            [
                line("git switch -c feature"),
                line('echo "Salut" > salut.txt'),
                line("git add salut.txt"),
                line('git commit -m "Ajoute le salut"'),
            ],
        ),
        ("pousser_feature", [line("git push -u origin feature")]),
        ("ouvrir_pr", [intent("pr_open", head="feature")]),
        ("merger_pr", [intent("pr_merge", number=1)]),
        ("recuperer_main", [line("git switch main"), line("git pull")]),
    ],
}


# ------------------------------------------------------------------------------------- banc
@dataclass
class Box:
    manager: WorkspaceManager
    engine: WorkspaceEngine
    git: Git
    events: list[Envelope]

    def play(self, step: Do) -> None:
        if step.kind == "line":
            op = terminal.build_terminal_line(self.engine, terminal.TerminalLine(line=step.value))
        elif step.kind == "quiz":
            op = build_operation(self.engine, "quiz_choice", {"choice_id": step.value})
        else:
            op = build_operation(self.engine, step.value, step.body)
        self.engine.submit(op).result(WAIT)

    def current(self) -> str | None:
        return load_run(self.engine.layout).get("step_id")

    def verdicts(self, step_id: str) -> list[dict]:
        return [
            e.payload
            for e in self.events
            if e.kind == Kind.STEP_VERDICT and e.payload["step_id"] == step_id
        ]

    def summary(self) -> dict | None:
        return self.engine.snapshot()["step_panel"]["summary"]

    def log(self, *args: str) -> str:
        return self.git.internal("log", "--format=%s", *args, cwd=self.engine.layout.repo)


@pytest.fixture
def make_box(tmp_path: Path, git_path: Path) -> Iterator[Callable[[str, str], Box]]:
    boxes: list[Box] = []
    terminal.AFTER_COMMAND_HOOKS.clear()
    terminal.register_intents()
    pr_intents.register_intents()
    terminal.AFTER_COMMAND_HOOKS.append(pr_intents.refresh_after_command)

    def make(scenario_id: str, track: str) -> Box:
        settings = Settings(data_dir=tmp_path / f"data-{len(boxes)}")
        loaded = load_scenario(settings.scenarios_path() / f"{scenario_id}.A.yaml", settings)
        manager = WorkspaceManager(settings, git_path=git_path, watch=False)
        events: list[Envelope] = []
        manager.events(f"{track}.{scenario_id}.A").attach(None, events.append)
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


# ------------------------------------------------------------------------------------- lint
@pytest.mark.parametrize("scenario_id", IDS)
def test_contenu_complet_et_sans_avertissement(scenario_id: str) -> None:
    settings = Settings()
    scenario = load_scenario(
        settings.scenarios_path() / f"{scenario_id}.A.yaml", settings, explain_keys=EXPLAIN_REFS
    ).scenario
    assert scenario.mode == "A"
    assert sorted(scenario.tracks) == ["llm", "no_ai"]
    assert scenario.catalogue and scenario.section is None
    assert scenario.steps
    with warnings.catch_warnings():
        assert not scenario.authoring_warnings()
    for step in scenario.steps:
        where = f"{scenario_id}/{step.step_id}"
        assert step.instruction_text.strip() and step.explanation_text.strip(), where
        assert step.hints is not None, where
        assert step.hints.lead_text.strip(), where
        assert BLANK in step.hints.partial_text, where
        assert step.hints.solution_text.strip(), where
    # Le jeu de solutions du test couvre toutes les étapes, dans l'ordre.
    assert [s for s, _ in SOLUTIONS[scenario_id]] == [s.step_id for s in scenario.steps]


def test_les_identifiants_sont_ceux_de_l_ordre_conseille() -> None:
    assert len(IDS) == 8
    shipped = {p.name for p in scenario_files(Settings())}
    assert {f"{i}.A.yaml" for i in IDS} <= shipped


def test_exigences_propres_a_chaque_scenario() -> None:
    settings = Settings()

    def load(scenario_id: str):
        return load_scenario(settings.scenarios_path() / f"{scenario_id}.A.yaml", settings).scenario

    # « push / pull » : le commit d'un collègue simulé est à récupérer par `git pull`.
    push_pull = load("push-pull")
    assert any(op.op == "colleague_commit" for op in push_pull.setup)
    assert any(s.step_id == "recuperer" for s in push_pull.steps)
    # « branche » : trois quiz, dont un propose `git reset --hard HEAD~1` (Flow 1).
    quizzes = [s for s in load("branche").steps if s.type == "quiz"]
    assert len(quizzes) == 3
    assert any(c.command_text == "git reset --hard HEAD~1" for q in quizzes for c in q.choices)
    assert all(c.effect_text for q in quizzes for c in q.choices if not c.correct)
    # « PR / merge » : branche poussée, PR, revue du collègue, merge.
    pr_merge = load("pr-merge")
    assert [s.type for s in pr_merge.steps][1:4] == ["repo_state", "pr_state", "pr_state"]
    assert any(op.op == "colleague_reaction" for op in pr_merge.setup)


# ------------------------------------------------------------------------- bout en bout
@pytest.mark.slow
@pytest.mark.parametrize("track", TRACKS)
@pytest.mark.parametrize("scenario_id", IDS)
def test_scenario_joue_de_bout_en_bout(make_box, scenario_id: str, track: str) -> None:
    box = make_box(scenario_id, track)
    plan = SOCLE_PLAN[scenario_id]
    assert box.current() == SOLUTIONS[scenario_id][0][0]
    assert box.summary() is None
    plan.before(box)
    for index, (step_id, gestures) in enumerate(SOLUTIONS[scenario_id]):
        for gesture in gestures[:-1]:
            box.play(gesture)
            assert box.current() == step_id, f"{step_id} validée trop tôt"
        box.play(gestures[-1])
        verdicts = box.verdicts(step_id)
        assert verdicts and verdicts[-1]["passed"] is True, f"{step_id} : {verdicts}"
        following = (
            SOLUTIONS[scenario_id][index + 1][0]
            if index + 1 < len(SOLUTIONS[scenario_id])
            else None
        )
        assert box.current() == following, step_id
    plan.after(box)
    summary = box.summary()
    assert summary is not None
    assert summary["hints"] == 0
    assert (summary["quiz_correct"], summary["quiz_total"]) == plan.score
    done = [
        e
        for e in box.events
        if e.kind == Kind.PROGRESS_UPDATED and "scenario_completed" in e.payload["facts"]
    ]
    assert len(done) == 1


@dataclass(frozen=True)
class Plan:
    score: tuple[int, int]
    before: Callable[[Box], None]
    after: Callable[[Box], None]


def _nothing(box: Box) -> None:
    return None


def _after_add_commit(box: Box) -> None:
    assert box.log("main").splitlines()[:2] == [
        "Complète le README",
        "Ajoute les notes de la réunion",
    ]


def _before_push_pull(box: Box) -> None:
    # Le collègue a poussé avant : l'origine a un commit que le dépôt local ne connaît pas.
    assert not (box.engine.layout.repo / "docs" / "guide.md").exists()
    assert "guide" not in box.log("main")


def _after_push_pull(box: Box) -> None:
    origin = box.git.internal("log", "--format=%s", "main", cwd=box.engine.layout.origin)
    assert origin.splitlines()[:2] == ["Ajoute la liste à faire", "Ajoute le guide de contribution"]
    assert (box.engine.layout.repo / "docs" / "guide.md").is_file()


def _after_branche(box: Box) -> None:
    assert box.log("main").splitlines()[0] == "Ajoute le salut"
    branches = box.git.internal("branch", "--format=%(refname:short)", cwd=box.engine.layout.repo)
    assert branches.split() == ["main"]


def _after_pr_merge(box: Box) -> None:
    pr = github_sim.load(box.engine.layout).pull(1)
    assert pr.state == "merged" and pr.approvals >= 1
    assert box.log("main").splitlines()[0] == "Merge pull request #1 from feature"


def _after_conflit(box: Box) -> None:
    repo = box.engine.layout.repo
    text = (repo / "src" / "bonjour.py").read_text(encoding="utf-8")
    assert "<<<<<<<" not in text and "Bienvenue" in text
    merge = box.git.internal("rev-list", "--parents", "-n1", "HEAD", cwd=repo).split()
    assert len(merge) == 3  # le commit de fusion a deux parents
    assert box.log("main").splitlines()[0] == "Fusionne feature"


def _before_stash(box: Box) -> None:
    repo = box.engine.layout.repo
    assert "À compléter" in (repo / "README.md").read_text(encoding="utf-8")
    assert box.git.internal("stash", "list", cwd=repo).strip() == ""


def _after_stash(box: Box) -> None:
    repo = box.engine.layout.repo
    readme = (repo / "README.md").read_text(encoding="utf-8")
    assert "(équipe)" in readme and "À compléter" in readme  # les deux travaux sont réunis
    assert box.git.internal("stash", "list", cwd=repo).strip() == ""


def _before_rebase(box: Box) -> None:
    assert box.log("origin/feature").splitlines()[0] == "Raccourcit le salut"


def _after_rebase(box: Box) -> None:
    repo = box.engine.layout.repo
    assert box.log("feature").splitlines()[:2] == [
        "Raccourcit le salut",
        "Ajoute une formule de bienvenue",
    ]
    parents = box.git.internal("rev-list", "--parents", "-n1", "feature", cwd=repo).split()
    assert len(parents) == 2  # historique linéaire
    # `--force-with-lease` a réécrit l'origine : elle a la même pointe que la branche locale.
    assert box.log("origin/feature") == box.log("feature")


def _lost_subjects(box: Box) -> list[str]:
    nodes = box.engine.snapshot()["views"]["graph"]["nodes"]
    return [n["subject"] for n in nodes if n["lost"]]


def _before_recuperation(box: Box) -> None:
    assert _lost_subjects(box) == []


def _after_recuperation(box: Box) -> None:
    assert _lost_subjects(box) == []  # plus en tirets : le commit est de retour sur main
    assert box.log("main").splitlines()[0] == "Note une idée d'amélioration"


SOCLE_PLAN: dict[str, Plan] = {
    "conflit": Plan((0, 0), _nothing, _after_conflit),
    "stash": Plan((1, 1), _before_stash, _after_stash),
    "rebase": Plan((1, 1), _before_rebase, _after_rebase),
    "recuperation": Plan((1, 1), _before_recuperation, _after_recuperation),
    "add-commit": Plan((1, 1), _nothing, _after_add_commit),
    "push-pull": Plan((1, 1), _before_push_pull, _after_push_pull),
    "branche": Plan((3, 3), _nothing, _after_branche),
    "pr-merge": Plan((0, 0), _nothing, _after_pr_merge),
}


def test_pr_state_sans_espace_ou_sans_pr_ne_dit_rien() -> None:
    from wavedevsecops.scenarios.steps import StepContext
    from wavedevsecops.scenarios.steps.pr_state import Args, check

    step = Args(
        step_id="ouvrir",
        type="pr_state",
        title_text="T",
        instruction_text="I",
        explanation_text="E",
        head="feature",
    )
    assert check(None, StepContext(step=step)).status == "pending"


# --------------------------------------------------------------------- erreurs réalistes
@pytest.mark.slow
def test_branche_la_mauvaise_reponse_reset_hard_est_expliquee_puis_retablie(make_box) -> None:
    box = make_box("branche", "llm")
    for _, gestures in SOLUTIONS["branche"][:2]:
        for gesture in gestures:
            box.play(gesture)
    assert box.current() == "revenir_sur_main"
    tip = box.log("feature").splitlines()
    box.play(quiz("reset_dur"))
    failed = box.verdicts("revenir_sur_main")[-1]
    assert failed["passed"] is False and "reflog" in failed["reason_text"]
    assert box.current() == "revenir_sur_main"
    # L'état est rétabli : le commit de `feature` est toujours là, et la bonne réponse passe.
    assert box.log("feature").splitlines() != tip  # l'effet est visible : le commit a reculé
    box.engine.submit(build_operation(box.engine, "restore_state", {})).result(WAIT)
    # L'état est rétabli : le commit de `feature` est de retour, et la bonne réponse passe.
    assert box.log("feature").splitlines() == tip
    box.play(quiz("switch_main"))
    assert box.current() == "fusionner"


@pytest.mark.slow
def test_add_commit_reset_hard_efface_le_commit_puis_est_retabli(make_box) -> None:
    box = make_box("add-commit", "no_ai")
    for _, gestures in SOLUTIONS["add-commit"][:2]:
        for gesture in gestures:
            box.play(gesture)
    assert box.current() == "corriger_le_message"
    notes = box.engine.layout.repo / "notes.txt"
    tip = box.log("main").splitlines()
    box.play(quiz("reset_dur"))
    assert box.verdicts("corriger_le_message")[-1]["passed"] is False
    assert not notes.exists() and box.log("main").splitlines() != tip  # l'effet a eu lieu
    box.engine.submit(build_operation(box.engine, "restore_state", {})).result(WAIT)
    assert notes.exists() and box.log("main").splitlines() == tip
    box.play(quiz("amend"))
    assert box.current() == "second_commit"


@pytest.mark.slow
def test_push_pull_pull_n_est_pas_la_bonne_reponse_du_premier_quiz(make_box) -> None:
    box = make_box("push-pull", "no_ai")
    box.play(quiz("pull"))
    assert box.verdicts("voir_sans_integrer")[-1]["passed"] is False
    assert box.current() == "voir_sans_integrer"
    guide = box.engine.layout.repo / "docs" / "guide.md"
    assert guide.exists()  # la mauvaise commande a vraiment tourné
    box.engine.submit(build_operation(box.engine, "restore_state", {})).result(WAIT)
    assert not guide.exists()
    box.play(quiz("fetch"))
    assert box.current() == "recuperer"


@pytest.mark.slow
def test_pr_merge_la_pr_n_est_pas_mergeable_sans_la_revue(make_box) -> None:
    """La protection de `main` exige l'approbation que le collègue donne à l'ouverture, et la
    vue « Distant + PR » offre les gestes des étapes `ouvrir_pr` et `merger_pr` (story 3.3)."""
    box = make_box("pr-merge", "llm")

    def remote() -> dict:
        return box.engine.snapshot()["views"]["remote"]

    def feature() -> dict:
        return next(b for b in remote()["branches"] if b["name_text"] == "origin/feature")

    for _, gestures in SOLUTIONS["pr-merge"][:2]:
        for gesture in gestures:
            box.play(gesture)
    # Bouton « Ouvrir une PR » de remote.js : affiché pour une branche distante où `can_open_pr`.
    assert box.current() == "ouvrir_pr"
    assert feature()["can_open_pr"] is True
    for gesture in SOLUTIONS["pr-merge"][2][1]:
        box.play(gesture)
    pr = github_sim.load(box.engine.layout).pull(1)
    assert [r.state for r in pr.reviews] == ["commented", "approved"]
    assert pr.mergeable and pr.approvals == 1
    assert box.current() == "merger_pr"
    # Bouton « Merger » de remote.js : actif quand `merge.enabled`.
    card = next(c for c in remote()["pulls"] if c["number"] == 1)
    assert (card["head"], card["base"], card["state"]) == ("feature", "main", "open")
    assert card["merge"]["enabled"] is True
    assert feature()["can_open_pr"] is False


# ------------------------------------------------------------ erreurs réalistes (story 6.3)
def _play_until(box: Box, scenario_id: str, step_id: str) -> None:
    for sid, gestures in SOLUTIONS[scenario_id]:
        if sid == step_id:
            return
        for gesture in gestures:
            box.play(gesture)
    raise AssertionError(step_id)


def _restore(box: Box) -> None:
    box.engine.submit(build_operation(box.engine, "restore_state", {})).result(WAIT)


def test_exigences_des_scenarios_avances() -> None:
    settings = Settings()

    def load(scenario_id: str):
        return load_scenario(settings.scenarios_path() / f"{scenario_id}.A.yaml", settings).scenario

    # « conflit » : la fusion en conflit, puis le commit de fusion.
    conflit = load("conflit")
    assert [s.expect.in_progress for s in conflit.steps] == ["merge", ""]
    # « stash » : un collègue simulé, un quiz dont une réponse efface le travail.
    stash = load("stash")
    assert any(op.op == "colleague_commit" for op in stash.setup)
    assert any(c.command_text == "git reset --hard" for c in stash.steps[0].choices)
    # « rebase » : branche déjà poussée, quiz de push forcé.
    rebase = load("rebase")
    assert any(op.op == "push" and op.branch == "feature" for op in rebase.setup)
    assert {c.command_text for c in rebase.steps[-1].choices} >= {
        "git push --force-with-lease",
        "git push --force",
    }
    # « récupération » : le reflog est l'objet d'un quiz.
    assert any(c.command_text == "git reflog" for c in load("recuperation").steps[1].choices)


def test_conflit_abandonner_la_fusion_est_explique(make_box) -> None:
    box = make_box("conflit", "no_ai")
    box.play(line("git merge feature"))
    assert box.current() == "resoudre"
    box.play(line("git merge --abort"))
    failed = box.verdicts("resoudre")[-1]
    assert failed["passed"] is False and "abandonnée" in failed["reason_text"]
    box.play(line("git merge feature"))  # on recommence : le conflit revient
    assert box.current() == "resoudre"
    text = (box.engine.layout.repo / "src" / "bonjour.py").read_text(encoding="utf-8")
    assert "<<<<<<<" in text and ">>>>>>>" in text


def test_conflit_fusion_en_cours_est_rappelee(make_box) -> None:
    box = make_box("conflit", "llm")
    box.play(line("git merge feature"))
    box.play(line("git add src/bonjour.py"))  # marqueurs encore présents, mais indexé
    failed = box.verdicts("resoudre")[-1]
    assert failed["passed"] is False and "toujours en cours" in failed["reason_text"]
    assert box.current() == "resoudre"


def test_stash_pull_refuse_puis_reset_dur_rattrapable(make_box) -> None:
    box = make_box("stash", "llm")
    repo = box.engine.layout.repo
    box.play(quiz("pull"))
    assert box.verdicts("mettre_de_cote")[-1]["passed"] is False
    assert "titre" not in box.log("main")  # le commit du collègue n'est pas arrivé
    _restore(box)
    box.play(quiz("reset_dur"))
    assert "À compléter" not in (repo / "README.md").read_text(encoding="utf-8")  # perdu
    _restore(box)
    assert "À compléter" in (repo / "README.md").read_text(encoding="utf-8")
    box.play(quiz("stash"))
    assert box.current() == "recuperer"


def test_stash_drop_ne_ramene_pas_le_travail(make_box) -> None:
    box = make_box("stash", "no_ai")
    _play_until(box, "stash", "reprendre")
    assert box.current() == "reprendre"
    box.play(line("git stash drop"))
    # La pile est vide, mais `README.md` n'a pas repris le travail : l'étape n'est pas validée.
    assert box.current() == "reprendre"
    assert "À compléter" not in (box.engine.layout.repo / "README.md").read_text(encoding="utf-8")


def test_rebase_abandonne_est_explique_et_push_simple_refuse(make_box) -> None:
    box = make_box("rebase", "llm")
    repo = box.engine.layout.repo
    _play_until(box, "rebase", "lancer_le_rebase")
    box.play(line("git rebase origin/main"))
    assert box.current() == "resoudre"
    box.play(line("git rebase --abort"))
    failed = box.verdicts("resoudre")[-1]
    assert failed["passed"] is False and "n'a pas abouti" in failed["reason_text"]
    box.play(line("git rebase origin/main"))
    for gesture in SOLUTIONS["rebase"][2][1]:
        box.play(gesture)
    assert box.current() == "pousser_apres_rebase"
    tip = box.git.internal("rev-parse", "origin/feature", cwd=repo).strip()
    box.play(quiz("push"))
    assert box.verdicts("pousser_apres_rebase")[-1]["passed"] is False
    assert box.git.internal("rev-parse", "origin/feature", cwd=repo).strip() == tip


def test_recuperation_commit_perdu_en_tirets_jusqu_a_sa_restauration(make_box) -> None:
    box = make_box("recuperation", "no_ai")
    box.play(line("git reset --hard HEAD~1"))
    assert _lost_subjects(box) == ["Note une idée d'amélioration"]
    box.play(quiz("log"))  # mauvaise réponse : `git log` ne le montre pas
    assert box.verdicts("retrouver")[-1]["passed"] is False
    assert _lost_subjects(box) == ["Note une idée d'amélioration"]
    _restore(box)
    box.play(quiz("reflog"))
    assert _lost_subjects(box) == ["Note une idée d'amélioration"]  # retrouvé, pas restauré
    assert box.current() == "restaurer"
    box.play(line("git reset --hard HEAD@{1}"))
    assert _lost_subjects(box) == []
    assert box.current() is None


def test_recuperation_reset_mixed_laisse_le_fichier_et_n_est_pas_valide(make_box) -> None:
    box = make_box("recuperation", "llm")
    box.play(line("git reset --mixed HEAD~1"))
    failed = box.verdicts("perdre_le_commit")[-1]
    assert failed["passed"] is False and "idee.txt" in failed["reason_text"]
    assert box.current() == "perdre_le_commit"


# ------------------------------------------- contournements refusés (revue de la story 6.3)
FIX_BONJOUR = SOLUTIONS["conflit"][1][1][:2]  # réécrit src/bonjour.py sans marqueur


def test_conflit_marqueurs_commites_ne_valident_pas(make_box) -> None:
    box = make_box("conflit", "no_ai")
    box.play(line("git merge feature"))
    box.play(line("git add src/bonjour.py"))  # marqueurs encore présents
    box.play(line('git commit -m "Fusionne feature"'))
    failed = box.verdicts("resoudre")[-1]
    assert failed["passed"] is False and "marqueurs" in failed["reason_text"]
    assert box.current() == "resoudre"
    for gesture in FIX_BONJOUR:  # on suit la raison : corriger puis commiter
        box.play(gesture)
    box.play(line("git add src/bonjour.py"))
    box.play(line('git commit -m "Retire les marqueurs"'))
    assert box.current() is None


def test_conflit_abandon_puis_commits_ordinaires_ne_valident_pas(make_box) -> None:
    box = make_box("conflit", "llm")
    box.play(line("git merge feature"))
    box.play(line("git merge --abort"))
    for name in ("a", "b"):  # trois commits depuis `depart`, mais aucune fusion
        box.play(line(f'echo "{name}" > {name}.txt'))
        box.play(line(f"git add {name}.txt"))
        box.play(line(f'git commit -m "Ajoute {name}"'))
    assert box.current() == "resoudre"


def test_rebase_remplace_par_une_fusion_ne_valide_pas(make_box) -> None:
    box = make_box("rebase", "no_ai")
    _play_until(box, "rebase", "lancer_le_rebase")
    box.play(line("git rebase origin/main"))
    box.play(line("git rebase --abort"))
    box.play(line("git merge origin/main"))
    for gesture in FIX_BONJOUR:
        box.play(gesture)
    box.play(line("git add src/bonjour.py"))
    box.play(line('git commit -m "Fusionne origin/main"'))
    failed = box.verdicts("resoudre")[-1]
    assert failed["passed"] is False and "fusion" in failed["reason_text"]
    assert box.current() == "resoudre"
    # La raison donne la voie de retour : revenir sur origin/feature puis rebaser.
    box.play(line("git reset --hard origin/feature"))
    box.play(line("git rebase origin/main"))
    for gesture in SOLUTIONS["rebase"][2][1]:
        box.play(gesture)
    assert box.current() == "pousser_apres_rebase"


def test_rebase_continue_avec_marqueurs_ne_valide_pas(make_box) -> None:
    box = make_box("rebase", "llm")
    _play_until(box, "rebase", "lancer_le_rebase")
    box.play(line("git rebase origin/main"))
    box.play(line("git add src/bonjour.py"))  # marqueurs encore présents
    box.play(line("git rebase --continue"))
    failed = box.verdicts("resoudre")[-1]
    assert failed["passed"] is False and "marqueurs" in failed["reason_text"]
    assert box.current() == "resoudre"


def test_recuperation_nouveau_commit_au_meme_message_ne_restaure_pas(make_box) -> None:
    box = make_box("recuperation", "no_ai")
    _play_until(box, "recuperation", "restaurer")
    box.play(line('echo "Une idee" > idee.txt'))
    box.play(line("git add idee.txt"))
    box.play(line('git commit -m "Note une idée d\'amélioration"'))
    failed = box.verdicts("restaurer")[-1]
    assert failed["passed"] is False and "tirets" in failed["reason_text"]
    assert box.current() == "restaurer"
    assert _lost_subjects(box) == ["Note une idée d'amélioration"]
    box.play(line("git reset --hard HEAD@{2}"))  # le vrai commit, retrouvé dans le reflog
    assert box.current() is None


def test_stash_drop_puis_reecriture_ne_valide_pas(make_box) -> None:
    box = make_box("stash", "llm")
    _play_until(box, "stash", "reprendre")
    box.play(line("git stash drop"))
    box.play(line('echo "Ma section" >> README.md'))  # README modifié, pile vide
    assert box.current() == "reprendre"


def test_push_pull_faux_guide_commite_ne_valide_pas(make_box) -> None:
    box = make_box("push-pull", "no_ai")
    _play_until(box, "push-pull", "recuperer")
    box.play(line("mkdir docs"))
    box.play(line('echo "Guide" > docs/guide.md'))
    box.play(line("git add docs/guide.md"))
    box.play(line('git commit -m "Ajoute le guide"'))
    assert box.current() == "recuperer"
    assert box.verdicts("recuperer")[-1]["passed"] is False


def test_pr_merge_faux_commit_de_merge_ne_valide_pas(make_box) -> None:
    box = make_box("pr-merge", "llm")
    _play_until(box, "pr-merge", "recuperer_main")
    box.play(line("git switch main"))
    box.play(line('echo "x" > faux.txt'))
    box.play(line("git add faux.txt"))
    box.play(line('git commit -m "Merge pull request #1 from feature"'))
    assert box.current() == "recuperer_main"
