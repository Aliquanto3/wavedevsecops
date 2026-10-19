"""Quiz à exécution réelle et rétablissement de l'état (Story 4.5) — avec un vrai git."""

from __future__ import annotations

import json
import shutil
import threading
import time
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from pathlib import Path

import pytest
from pydantic import ValidationError

from wavedevsecops import terminal
from wavedevsecops.config import Settings
from wavedevsecops.engine import (
    INTENTS,
    Operation,
    OperationRefused,
    WorkspaceEngine,
    WorkspaceManager,
    build_operation,
    fingerprint,
    list_snapshots,
    load_run,
    save_run,
    snapshots,
)
from wavedevsecops.engine.operations import QUIZ_REFUSED_TEXT, RESTORE_FAILED_TEXT
from wavedevsecops.events import Envelope, Kind
from wavedevsecops.gitio import Git
from wavedevsecops.progress.facts import ProgressStore
from wavedevsecops.scenarios import load_scenario
from wavedevsecops.scenarios.steps.quiz import Args

WAIT = 60.0
ALLOWLIST = Path(__file__).resolve().parent.parent / "content" / "terminal-allowlist.yaml"
SCENARIO = """\
schema_version: 1
scenario_id: quiz
mode: A
title_text: Scénario d'essai du quiz
tracks: [llm, no_ai]
tools: [git]
setup:
  - op: write_file
    path: README.md
    content: "# Projet\\n"
  - op: commit
    message: Ajoute le README
    as: premier
  - op: write_file
    path: notes.txt
    content: "notes\\n"
  - op: commit
    message: Ajoute les notes
    as: second
  - op: push
    branch: main
    as: origin-main
steps:
  - step_id: annuler
    type: quiz
    title_text: Annuler le dernier commit sans réécrire l'historique
    instruction_text: Quelle commande annule le dernier commit en gardant l'historique ?
    explanation_text: "`git revert` ajoute un commit qui défait l'autre."
    choices:
      - choice_id: reset_hard
        command_text: git reset --hard HEAD~1
        effect_text: "`reset --hard` a déplacé la branche et effacé le commit."
      - choice_id: branche
        command_text: git switch -c autre
        effect_text: Une branche a été créée, mais rien n'a été annulé.
      - choice_id: revert
        command_text: git revert --no-edit HEAD
        correct: true
  - step_id: ensuite
    type: repo_state
    title_text: Créer la branche feature
    instruction_text: Créez la branche `feature`.
    explanation_text: Une branche est un pointeur.
    expect:
      branches:
        - name: feature
"""


@dataclass
class Box:
    manager: WorkspaceManager
    engine: WorkspaceEngine
    git: Git
    events: list[Envelope]
    settings: Settings
    path: Path

    def choose(self, choice_id: str) -> list[Envelope]:
        start = len(self.events)
        op = build_operation(self.engine, "quiz_choice", {"choice_id": choice_id})
        self.engine.submit(op).result(WAIT)
        return self.events[start:]

    def restore(self) -> list[Envelope]:
        start = len(self.events)
        op = build_operation(self.engine, "restore_state", {})
        self.engine.submit(op).result(WAIT)
        return self.events[start:]

    def fingerprint(self) -> str:
        return fingerprint(self.engine.layout, self.git)

    def log(self) -> list[str]:
        out = self.git.internal("log", "--format=%s", cwd=self.engine.layout.repo)
        return out.strip().splitlines()


def _of(events: list[Envelope], kind: Kind) -> list[Envelope]:
    return [e for e in events if e.kind == kind]


@pytest.fixture
def make_box(tmp_path: Path, git_path: Path) -> Iterator[Callable[[], Box]]:
    boxes: list[Box] = []
    terminal.register_intents()

    def make() -> Box:
        content = tmp_path / "content"
        (content / "scenarios").mkdir(parents=True)
        path = content / "scenarios" / "quiz.A.yaml"
        path.write_text(SCENARIO, encoding="utf-8", newline="\n")
        shutil.copy(ALLOWLIST, content / ALLOWLIST.name)
        settings = Settings(data_dir=tmp_path / "data", content_dir=content, restore_retry_ms=1)
        manager = WorkspaceManager(settings, git_path=git_path, watch=False)
        loaded = load_scenario(path, settings)
        events: list[Envelope] = []
        manager.events("llm.quiz.A").attach(None, events.append)
        engine, setup = manager.create(loaded, "llm")
        setup.result(WAIT)
        box = Box(
            manager,
            engine,
            Git.for_workspace(git_path, engine.layout.root, settings),
            events,
            settings,
            path,
        )
        boxes.append(box)
        return box

    yield make
    for box in boxes:
        box.manager.close()


@pytest.mark.slow
def test_le_panneau_propose_les_commandes_sans_la_bonne_reponse(make_box) -> None:
    box = make_box()
    panel = box.engine.snapshot()["step_panel"]
    current = next(s for s in panel["steps"] if s["state"] == "current")
    assert [c["choice_id"] for c in current["quiz"]["choices"]] == [
        "reset_hard",
        "branche",
        "revert",
    ]
    assert all(set(c) == {"choice_id", "command_text"} for c in current["quiz"]["choices"])
    assert "quiz" not in panel["steps"][1]
    assert panel["quiz_altered"] is None
    assert panel["restore_failed"] is None


@pytest.mark.slow
def test_une_mauvaise_reponse_s_execute_puis_l_etat_est_modifie(make_box) -> None:
    box = make_box()
    before = box.fingerprint()
    assert box.engine.last_projection.fingerprint == before
    events = box.choose("reset_hard")

    # Un instantané est pris avant le choix, puis la commande est répétée et exécutée.
    assert [s.reason for s in list_snapshots(box.engine.layout)] == ["setup", "quiz"]
    out = [(e.payload["stream"], e.payload["text"]) for e in _of(events, Kind.TERMINAL_OUTPUT)]
    assert out[0] == ("input", "git reset --hard HEAD~1")
    assert box.log() == ["Ajoute le README"]
    assert box.engine.state == "quiz_altered"
    altered = _of(events, Kind.QUIZ_ALTERED)[0].payload
    assert altered["choice_id"] == "reset_hard"
    assert altered["first_attempt"] is True
    assert "effacé le commit" in altered["explanation_text"]
    assert "snapshot_id" not in altered
    verdict = _of(events, Kind.STEP_VERDICT)[0].payload
    assert verdict["status"] == "failed"
    assert verdict["reason_text"] == altered["explanation_text"]
    assert load_run(box.engine.layout)["step_id"] == "annuler"

    panel = box.engine.snapshot()["step_panel"]
    assert panel["quiz_altered"]["command_text"] == "git reset --hard HEAD~1"
    assert "snapshot_id" not in panel["quiz_altered"]


@pytest.mark.slow
def test_en_etat_modifie_les_ecritures_sont_refusees_et_les_lectures_passent(make_box) -> None:
    box = make_box()
    box.choose("branche")
    read = build_operation(box.engine, "terminal_line", {"line": "git log --oneline"})
    assert box.engine.submit(read).result(WAIT).code == 0
    for intent, body in (
        ("terminal_line", {"line": "git commit --allow-empty -m x"}),
        ("quiz_choice", {"choice_id": "revert"}),
    ):
        with pytest.raises(OperationRefused) as refused:
            box.engine.submit(build_operation(box.engine, intent, body))
        assert refused.value.reason_text == QUIZ_REFUSED_TEXT
    assert QUIZ_REFUSED_TEXT.startswith("Refusée pendant l'état modifié par le quiz")


@pytest.mark.slow
def test_le_retablissement_redonne_la_meme_empreinte(make_box) -> None:
    box = make_box()
    before = box.fingerprint()
    box.choose("reset_hard")
    assert box.fingerprint() != before
    events = box.restore()

    assert box.fingerprint() == before
    assert box.engine.last_projection.fingerprint == before
    assert box.engine.state == "idle"
    assert box.log() == ["Ajoute les notes", "Ajoute le README"]
    started = _of(events, Kind.RESTORE_STARTED)[0].payload
    ended = _of(events, Kind.RESTORE_ENDED)[0].payload
    assert (ended["status"], ended["snapshot_id"]) == ("ok", started["snapshot_id"])
    run = load_run(box.engine.layout)
    assert run["quiz"] is None
    assert run["step_id"] == "annuler"
    assert box.engine.snapshot()["step_panel"]["quiz_altered"] is None
    # Plus rien à rétablir.
    with pytest.raises(OperationRefused):
        build_operation(box.engine, "restore_state", {})


@pytest.mark.slow
def test_une_bonne_reponse_garde_l_etat_et_valide_l_etape(make_box) -> None:
    box = make_box()
    events = box.choose("revert")
    assert box.engine.state == "idle"
    assert not _of(events, Kind.QUIZ_ALTERED)
    assert box.log()[0].startswith("Revert")
    verdict = _of(events, Kind.STEP_VERDICT)[0].payload
    assert (verdict["status"], verdict["next_step_id"]) == ("passed", "ensuite")
    assert _of(events, Kind.STEP_EXPLANATION)
    run = load_run(box.engine.layout)
    assert run["step_id"] == "ensuite"
    assert run["quiz"] is None
    # L'instantané est pris avant chaque choix, même juste.
    assert [s.reason for s in list_snapshots(box.engine.layout)] == ["setup", "quiz"]


@pytest.mark.slow
def test_seul_le_premier_essai_est_retenu(make_box) -> None:
    box = make_box()
    first = _of(box.choose("branche"), Kind.QUIZ_ALTERED)[0].payload
    box.restore()
    again = _of(box.choose("reset_hard"), Kind.QUIZ_ALTERED)[0].payload
    box.restore()
    final = box.choose("revert")
    assert (first["first_attempt"], again["first_attempt"]) == (True, False)
    assert _of(final, Kind.STEP_VERDICT)[0].payload["status"] == "passed"
    assert load_run(box.engine.layout)["quiz_first"] == {
        "annuler": {"choice_id": "branche", "correct": False}
    }
    # Le premier essai est le fait du score (story 4.2), un seul par étape.
    quiz = [
        f
        for f in ProgressStore.for_dir(box.settings.resolved_data_dir()).facts()
        if f["kind"] == "quiz_first_attempt"
    ]
    assert [(f["step_id"], f["correct"]) for f in quiz] == [("annuler", False)]


@pytest.mark.slow
def test_le_premier_essai_est_rejoue_au_reveil(make_box, git_path: Path) -> None:
    box = make_box()
    box.choose("revert")
    store = ProgressStore.for_dir(box.settings.resolved_data_dir())
    assert [
        (f["kind"], f["correct"]) for f in store.facts() if f["kind"] == "quiz_first_attempt"
    ] == [("quiz_first_attempt", True)]
    assert store.progress("llm", "quiz", "A").first_try_score == 100
    box.manager.close()
    # Arrêt brutal entre `run.json` et `progress.json` : le fait manquant revient au réveil.
    path = box.settings.resolved_data_dir() / "progress.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    data["facts"] = [f for f in data["facts"] if f["kind"] != "quiz_first_attempt"]
    path.write_text(json.dumps(data), encoding="utf-8")
    reopened = WorkspaceManager(box.settings, git_path=git_path, watch=False)
    try:
        reopened.get("llm.quiz.A")
        deadline = time.monotonic() + WAIT
        while time.monotonic() < deadline:
            facts = [f for f in store.facts() if f["kind"] == "quiz_first_attempt"]
            if facts:
                break
        assert [(f["step_id"], f["correct"]) for f in facts] == [("annuler", True)]
    finally:
        reopened.close()


@pytest.mark.slow
def test_l_etat_modifie_survit_a_la_reouverture(make_box, git_path: Path) -> None:
    box = make_box()
    box.choose("branche")
    box.manager.close()
    reopened = WorkspaceManager(box.settings, git_path=git_path, watch=False)
    try:
        engine = reopened.get("llm.quiz.A")
        assert engine.rest_state == "quiz_altered"
        assert engine.snapshot()["step_panel"]["quiz_altered"]["choice_id"] == "branche"
        engine.submit(build_operation(engine, "restore_state", {})).result(WAIT)
        assert engine.rest_state == "idle"
    finally:
        reopened.close()


@pytest.mark.slow
def test_apres_un_retablissement_echoue_seules_les_lectures_passent(make_box) -> None:
    box = make_box()
    run = load_run(box.engine.layout)
    save_run(box.engine.layout, {**run, "restore_failed": {"snapshot_id": 1, "reason_text": "x"}})
    with pytest.raises(OperationRefused) as refused:
        box.engine.submit(build_operation(box.engine, "quiz_choice", {"choice_id": "revert"}))
    assert refused.value.reason_text == RESTORE_FAILED_TEXT
    read = build_operation(box.engine, "terminal_line", {"line": "git status"})
    assert box.engine.submit(read).result(WAIT).code == 0
    assert box.engine.snapshot()["step_panel"]["restore_failed"] == {"reason_text": "x"}
    # « Recommencer » (4.4) reste admise.
    box.engine.submit(Operation("restart", lambda ctx: 0)).result(WAIT)


@pytest.mark.slow
def test_un_vrai_retablissement_echoue_laisse_recommencer_seulement(make_box) -> None:
    box = make_box()
    box.choose("reset_hard")
    # Instantané perdu : la restauration échoue pour de vrai.
    snapshot_id = load_run(box.engine.layout)["quiz"]["snapshot_id"]
    (box.engine.layout.snapshots / str(snapshot_id) / snapshots.MANIFEST_FILE).unlink()
    ended = _of(box.restore(), Kind.RESTORE_ENDED)[0].payload
    assert ended["status"] == "restore_failed"
    assert load_run(box.engine.layout)["restore_failed"]
    assert box.engine.snapshot()["step_panel"]["restore_failed"]["reason_text"]
    for intent, body in (
        ("terminal_line", {"line": "git commit --allow-empty -m x"}),
        ("quiz_choice", {"choice_id": "revert"}),
    ):
        with pytest.raises(OperationRefused) as refused:
            box.engine.submit(build_operation(box.engine, intent, body))
        assert refused.value.reason_text == RESTORE_FAILED_TEXT
    # « Seule action : Recommencer » : un nouveau rétablissement n'est pas proposé.
    with pytest.raises(OperationRefused) as again:
        build_operation(box.engine, "restore_state", {})
    assert again.value.reason_text == RESTORE_FAILED_TEXT
    read = build_operation(box.engine, "terminal_line", {"line": "git status"})
    assert box.engine.submit(read).result(WAIT).code == 0
    # « Recommencer » (4.4) passe, même si l'espace est resté en `quiz_altered`.
    assert box.engine.rest_state == "quiz_altered"
    box.engine.submit(Operation("restart", lambda ctx: 0, validate=False)).result(WAIT)


def _blocked(box: Box) -> threading.Event:
    """Occupe la file : les opérations suivantes attendent derrière."""
    gate = threading.Event()
    box.engine.submit(Operation("block", lambda ctx: gate.wait(WAIT), writes=False, validate=False))
    return gate


@pytest.mark.slow
def test_deux_choix_envoyes_d_affilee_n_en_executent_qu_un(make_box) -> None:
    box = make_box()
    before = box.fingerprint()
    gate = _blocked(box)
    first = box.engine.submit(build_operation(box.engine, "quiz_choice", {"choice_id": "branche"}))
    second = box.engine.submit(
        build_operation(box.engine, "quiz_choice", {"choice_id": "reset_hard"})
    )
    start = len(box.events)
    gate.set()
    first.result(WAIT)
    second.result(WAIT)
    assert len(_of(box.events[start:], Kind.QUIZ_ALTERED)) == 1
    assert load_run(box.engine.layout)["quiz"]["choice_id"] == "branche"
    assert box.log() == ["Ajoute les notes", "Ajoute le README"]
    box.restore()
    assert box.fingerprint() == before


@pytest.mark.slow
def test_une_ecriture_en_file_derriere_un_mauvais_choix_est_refusee(make_box) -> None:
    box = make_box()
    gate = _blocked(box)
    box.engine.submit(build_operation(box.engine, "quiz_choice", {"choice_id": "branche"}))
    write = box.engine.submit(
        build_operation(box.engine, "terminal_line", {"line": "git commit --allow-empty -m x"})
    )
    start = len(box.events)
    gate.set()
    assert write.result(WAIT).code is None
    errors = _of(box.events[start:], Kind.APP_ERROR)
    assert [e.payload["cause_text"] for e in errors] == [QUIZ_REFUSED_TEXT]
    assert box.log() == ["Ajoute les notes", "Ajoute le README"]


@pytest.mark.slow
def test_un_git_en_echec_laisse_l_etat_modifie_coherent(make_box, monkeypatch) -> None:
    box = make_box()
    from wavedevsecops.terminal import quiz as quiz_module

    def boom(*args, **kwargs):
        raise RuntimeError("git introuvable")

    monkeypatch.setattr(quiz_module, "_run_git", boom)
    events = box.choose("branche")
    assert load_run(box.engine.layout)["quiz"]["choice_id"] == "branche"
    assert box.engine.rest_state == "quiz_altered"
    assert box.engine.state == "quiz_altered"
    assert _of(events, Kind.QUIZ_ALTERED)


@pytest.mark.slow
def test_refus_d_un_choix_hors_quiz_ou_inconnu(make_box) -> None:
    box = make_box()
    with pytest.raises(OperationRefused) as unknown:
        build_operation(box.engine, "quiz_choice", {"choice_id": "absent"})
    assert "ne fait pas partie des choix" in unknown.value.reason_text
    box.choose("revert")
    with pytest.raises(OperationRefused) as other:
        build_operation(box.engine, "quiz_choice", {"choice_id": "revert"})
    assert "n'est pas un quiz" in other.value.reason_text


def test_les_intentions_du_quiz_sont_au_catalogue() -> None:
    terminal.register_intents()
    assert {"quiz_choice", "restore_state"} <= set(INTENTS)


def _step(choices: list[dict]) -> dict:
    return {
        "step_id": "q",
        "type": "quiz",
        "title_text": "t",
        "instruction_text": "i",
        "explanation_text": "e",
        "choices": choices,
    }


def test_un_quiz_a_exactement_une_bonne_reponse() -> None:
    ok = {"choice_id": "a", "command_text": "git status", "correct": True}
    other = {"choice_id": "b", "command_text": "git log", "effect_text": "x"}
    assert Args.model_validate(_step([ok, other]))
    for choices in ([other, {**other, "choice_id": "c"}], [ok, {**ok, "choice_id": "c"}]):
        with pytest.raises(ValidationError):
            Args.model_validate(_step(choices))
    with pytest.raises(ValidationError):
        Args.model_validate(_step([ok, {**other, "choice_id": "a"}]))
    bare = Args.model_validate(_step([ok, {"choice_id": "b", "command_text": "git log"}]))
    assert bare.authoring_warnings() == [
        (("choices", 1, "effect_text"), "une mauvaise réponse sans explication de son effet")
    ]
