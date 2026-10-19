"""Recommencer un scénario sans perdre son score (Story 4.4) — avec un vrai git."""

from __future__ import annotations

import json
import shutil
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from pathlib import Path

import pytest

from wavedevsecops import terminal, wsfs
from wavedevsecops.config import Settings
from wavedevsecops.engine import (
    INTENTS,
    WorkspaceEngine,
    WorkspaceManager,
    build_operation,
    compute_references,
    fingerprint,
    get_snapshot,
    hints,
    load_run,
    restart,
    save_run,
    snapshots,
    write_references,
)
from wavedevsecops.engine.operations import QUIZ_REFUSED_TEXT, RESTORE_FAILED_TEXT
from wavedevsecops.engine.steps import CONTENT_CHANGED_TEXT
from wavedevsecops.events import Envelope, Kind
from wavedevsecops.gitio import Git
from wavedevsecops.progress.facts import ProgressStore, derive
from wavedevsecops.scenarios import load_scenario

WAIT = 60.0
ALLOWLIST = Path(__file__).resolve().parent.parent / "content" / "terminal-allowlist.yaml"
SCENARIO = """\
schema_version: 1
scenario_id: reprise
mode: A
title_text: Scénario d'essai de Recommencer
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
    hints:
      lead_text: Une commande défait un commit en en ajoutant un autre.
      partial_text: git revert ___
      solution_text: git revert --no-edit HEAD
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
WS = "llm.reprise.A"


@dataclass
class Box:
    manager: WorkspaceManager
    engine: WorkspaceEngine
    git: Git
    events: list[Envelope]
    settings: Settings
    path: Path
    clock: dict[str, float]
    git_path: Path

    def run(self, intent: str, body: dict | None = None) -> list[Envelope]:
        start = len(self.events)
        op = build_operation(self.engine, intent, body or {})
        self.engine.submit(op).result(WAIT)
        return self.events[start:]

    def line(self, text: str) -> list[Envelope]:
        return self.run("terminal_line", {"line": text})

    def fingerprint(self) -> str:
        return fingerprint(self.engine.layout, self.git)

    def run_json(self) -> dict:
        return load_run(self.engine.layout)

    def panel(self) -> dict:
        return self.engine.snapshot()["step_panel"]

    def facts(self, kind: str | None = None) -> list[dict]:
        path = self.settings.resolved_data_dir() / "progress.json"
        if not path.exists():
            return []
        facts = json.loads(path.read_text(encoding="utf-8")).get("facts", [])
        return [f for f in facts if kind is None or f["kind"] == kind]

    def finish(self) -> None:
        """Parcourt le scénario : bonne réponse du quiz, puis la branche `feature`."""
        self.run("quiz_choice", {"choice_id": "revert"})
        self.line("git switch -c feature")


def _of(events: list[Envelope], kind: Kind) -> list[Envelope]:
    return [e for e in events if e.kind == kind]


@pytest.fixture
def make_box(tmp_path: Path, git_path: Path, monkeypatch) -> Iterator[Callable[[], Box]]:
    boxes: list[Box] = []
    clock = {"now": 1_780_000_000.0}
    monkeypatch.setattr(hints, "clock", lambda: clock["now"])
    terminal.register_intents()
    hints.register_intents()
    restart.register_intents()

    def make() -> Box:
        content = tmp_path / "content"
        (content / "scenarios").mkdir(parents=True)
        path = content / "scenarios" / "reprise.A.yaml"
        path.write_text(SCENARIO, encoding="utf-8", newline="\n")
        shutil.copy(ALLOWLIST, content / ALLOWLIST.name)
        settings = Settings(data_dir=tmp_path / "data", content_dir=content, restore_retry_ms=1)
        manager = WorkspaceManager(settings, git_path=git_path, watch=False)
        loaded = load_scenario(path, settings)
        events: list[Envelope] = []
        manager.events(WS).attach(None, events.append)
        engine, setup = manager.create(loaded, "llm")
        setup.result(WAIT)
        git = Git.for_workspace(git_path, engine.layout.root, settings)
        box = Box(manager, engine, git, events, settings, path, clock, git_path)
        boxes.append(box)
        return box

    yield make
    for box in boxes:
        box.manager.close()


# ------------------------------------------------------------ l'AC : retour à l'instantané 0
def test_recommencer_rend_l_empreinte_de_l_instantane_0_et_l_etape_1(make_box) -> None:
    box = make_box()
    setup_digest = get_snapshot(box.engine.layout, 0).fingerprint
    box.run("quiz_choice", {"choice_id": "revert"})
    assert box.fingerprint() != setup_digest
    assert box.panel()["current_step_id"] == "ensuite"

    events = box.run("restart")

    assert box.fingerprint() == setup_digest
    assert box.engine.last_projection.fingerprint == setup_digest
    panel = box.panel()
    assert panel["current_step_id"] == "annuler"
    assert [s["state"] for s in panel["steps"]] == ["current", "todo"]
    states = [e.payload["state"] for e in _of(events, Kind.ENGINE_STATE)]
    assert states[0] == "restoring" and states[-1] == "idle"
    # Epoch incrémenté, repères du run refaits.
    run = box.run_json()
    assert run["epoch"] == box.engine.epoch
    assert run["step_id"] == "annuler" and "validated" not in run
    assert run["step_ids"] == ["annuler", "ensuite"]
    assert run["setup_fingerprint"] == setup_digest
    assert _of(events, Kind.APP_ERROR) == []


def test_recommencer_n_est_pas_un_retablissement_marque(make_box) -> None:
    box = make_box()
    box.run("quiz_choice", {"choice_id": "revert"})
    events = box.run("restart")
    assert _of(events, Kind.RESTORE_ENDED) == []
    assert box.run_json().get("restoring") is None


# --------------------------------------------------------- 4.5 : quiz et restore_failed
def test_recommencer_efface_restore_failed_quiz_et_quiz_first(make_box) -> None:
    box = make_box()
    setup_digest = get_snapshot(box.engine.layout, 0).fingerprint
    box.run("quiz_choice", {"choice_id": "reset_hard"})
    snapshot_id = box.run_json()["quiz"]["snapshot_id"]
    (box.engine.layout.snapshots / str(snapshot_id) / snapshots.MANIFEST_FILE).unlink()
    ended = _of(box.run("restore_state"), Kind.RESTORE_ENDED)[0].payload
    assert ended["status"] == "restore_failed"
    run = box.run_json()
    assert run["restore_failed"] and run["quiz"] and run["quiz_first"]
    assert box.engine.rest_state == "quiz_altered"
    with pytest.raises(Exception, match="rétabli"):
        box.run("quiz_choice", {"choice_id": "revert"})

    events = box.run("restart")

    assert _of(events, Kind.APP_ERROR) == []
    run = box.run_json()
    assert not run.get("restore_failed") and not run.get("quiz") and not run.get("quiz_first")
    assert box.engine.rest_state == "idle"
    assert box.engine.snapshot()["state"] == "idle"
    panel = box.panel()
    assert panel["restore_failed"] is None and panel["quiz_altered"] is None
    assert box.fingerprint() == setup_digest
    # Les écritures repassent : plus de refus `restore_failed` ni `quiz_altered`.
    assert box.run("quiz_choice", {"choice_id": "revert"})


def test_recommencer_sort_de_quiz_altered_sans_retablir_d_abord(make_box) -> None:
    box = make_box()
    setup_digest = get_snapshot(box.engine.layout, 0).fingerprint
    box.run("quiz_choice", {"choice_id": "reset_hard"})
    assert box.engine.rest_state == "quiz_altered"
    with pytest.raises(Exception, match="Refusée pendant l'état modifié"):
        box.run("quiz_choice", {"choice_id": "revert"})
    box.run("restart")
    assert box.engine.rest_state == "idle"
    assert box.fingerprint() == setup_digest
    assert not box.run_json().get("quiz")


def test_une_vraie_restauration_ratee_ne_laisse_pas_restore_failed(make_box) -> None:
    """L'instantané 0 est corrompu : Recommencer reconstruit par le setup."""
    box = make_box()
    reference = get_snapshot(box.engine.layout, 0).fingerprint
    (box.engine.layout.snapshots / "0" / snapshots.MANIFEST_FILE).unlink()
    box.run("quiz_choice", {"choice_id": "revert"})
    events = box.run("restart")
    assert _of(events, Kind.APP_ERROR) == []
    assert box.fingerprint() == reference  # le setup est déterministe
    assert box.panel()["current_step_id"] == "annuler"
    assert get_snapshot(box.engine.layout, 0) is not None  # l'instantané 0 est refait


# ---------------------------------------------------------------------- 4.6 : indices
def _tiers(box: Box) -> list[str]:
    current = next(s for s in box.panel()["steps"] if s["state"] == "current")
    return [t["state"] for t in current["hints"]["tiers"]]


def test_recommencer_clot_la_lecture_puis_remet_les_paliers_a_zero(make_box) -> None:
    box = make_box()
    box.run("hint_open", {"tier": 1})
    box.clock["now"] += 6
    assert _tiers(box) == ["open", "available", "locked"]

    box.run("restart")

    # La lecture du palier 1 est un fait (clos AVANT la reconstruction de run.json) ...
    [fact] = box.facts("hint_opened")
    assert (fact["tier"], fact["read_ms"]) == (1, 6000)
    # ... et les paliers de l'espace repartent de zéro, sans toucher au fait.
    run = box.run_json()
    assert "hint_pending" not in run
    assert run["hints"]["annuler"].get("opened", {}) == {}
    assert run["hints"]["annuler"].get("attempts", 0) == 0
    assert _tiers(box) == ["available", "locked", "locked"]
    assert len(box.facts("hint_opened")) == 1


def test_les_essais_de_la_solution_sont_remis_a_zero(make_box) -> None:
    box = make_box()
    box.run("hint_open", {"tier": 1})
    box.run("hint_open", {"tier": 2})
    box.line("git status")  # un essai : la solution se débloque
    assert _tiers(box)[2] == "available"
    box.run("restart")
    assert _tiers(box) == ["available", "locked", "locked"]


# ---------------------------------------------------------------- 5.2 : désignation
def test_recommencer_vide_les_reponses_de_designation(make_box) -> None:
    box = make_box()
    run = box.run_json()
    save_run(
        box.engine.layout,
        {**run, "answers": {"annuler": {"correct": False, "slots": {"commit": "abc1234"}}}},
    )
    box.run("restart")
    assert "answers" not in box.run_json()


# -------------------------------------------------------- 4.2 : le score est conservé
def test_les_faits_du_premier_passage_sont_conserves(make_box) -> None:
    box = make_box()
    box.run("quiz_choice", {"choice_id": "branche"})  # mauvais premier choix
    box.run("restore_state")
    box.finish()
    before = box.facts()
    kinds = {f["kind"] for f in before}
    assert {"quiz_first_attempt", "step_validated", "scenario_completed"} <= kinds
    score = ProgressStore.for_dir(box.settings.resolved_data_dir()).progress("llm", "reprise", "A")
    assert (score.quiz_total, score.quiz_correct, score.state) == (1, 0, "done")

    events = box.run("restart")

    after = box.facts()
    assert [f for f in after if f["kind"] != "scenario_restarted"] == before
    [restarted] = [f for f in after if f["kind"] == "scenario_restarted"]
    identity = (restarted["track"], restarted["scenario_id"], restarted["mode"])
    assert identity == ("llm", "reprise", "A")
    progress = _of(events, Kind.PROGRESS_UPDATED)
    assert [e.payload["facts"] for e in progress] == [["scenario_restarted"]]
    # Le score du premier coup reste celui du premier passage, même en refaisant juste.
    box.finish()
    assert [f for f in box.facts() if f["kind"] == "quiz_first_attempt"] == [
        f for f in before if f["kind"] == "quiz_first_attempt"
    ]
    score = ProgressStore.for_dir(box.settings.resolved_data_dir()).progress("llm", "reprise", "A")
    assert (score.quiz_total, score.quiz_correct) == (1, 0)


def test_chaque_remise_a_zero_ajoute_son_fait(make_box) -> None:
    box = make_box()
    box.run("restart")
    box.run("restart")
    assert len(box.facts("scenario_restarted")) == 2


def test_une_remise_a_zero_ne_fait_pas_commencer_un_scenario() -> None:
    fact = {"kind": "scenario_restarted", "track": "llm", "scenario_id": "x", "mode": "A"}
    assert derive([fact], "llm", "x", "A").state == "todo"


# ------------------------------------------------------------------ 4.7 : le bilan
def test_le_bilan_disparait_apres_recommencer_et_revient_identique(make_box) -> None:
    box = make_box()
    box.finish()
    summary = box.panel()["summary"]
    assert summary and box.panel()["current_step_id"] == ""

    events = box.run("restart")

    # Le front relit le panneau sur ce fait : il n'a plus de bilan et repart à l'étape 1.
    assert [e.payload["facts"] for e in _of(events, Kind.PROGRESS_UPDATED)] == [
        ["scenario_restarted"]
    ]
    panel = box.panel()
    assert panel["summary"] is None and panel["current_step_id"] == "annuler"
    box.finish()
    assert box.panel()["summary"] == summary  # le premier passage fait foi


# ------------------------------------------------------- reconstruction par le setup
def test_sans_instantane_0_l_espace_est_reconstruit_et_compare_a_la_reference(make_box) -> None:
    box = make_box()
    write_references(compute_references(box.settings, box.git_path), box.settings)
    wsfs.remove_tree(box.engine.layout.snapshots / "0")
    box.run("quiz_choice", {"choice_id": "revert"})
    events = box.run("restart")
    assert _of(events, Kind.APP_ERROR) == []
    assert box.panel()["current_step_id"] == "annuler"
    assert box.fingerprint() == json.loads(
        (box.settings.content_path() / "fingerprints.json").read_text(encoding="utf-8")
    )["fingerprints"]["llm/reprise.A"]
    assert box.run_json()["epoch"] == box.engine.epoch


def test_une_reconstruction_qui_ne_correspond_pas_a_la_reference_est_signalee(make_box) -> None:
    box = make_box()
    write_references({"llm/reprise.A": "0" * 64}, box.settings)
    wsfs.remove_tree(box.engine.layout.snapshots / "0")
    [error] = _of(box.run("restart"), Kind.APP_ERROR)
    assert "référence" in error.payload["cause_text"]
    assert "Voir le diagnostic" in error.payload["action_text"]
    # L'espace n'est pas jugé fiable : seule l'action « Recommencer » reste admise.
    assert box.panel()["restore_failed"]["reason_text"]
    with pytest.raises(Exception, match=RESTORE_FAILED_TEXT[:20]):
        box.run("quiz_choice", {"choice_id": "revert"})


def test_un_scenario_disparu_donne_une_erreur_avec_le_diagnostic(make_box) -> None:
    box = make_box()
    box.path.unlink()
    [error] = _of(box.run("restart"), Kind.APP_ERROR)
    assert "scénario" in error.payload["cause_text"]
    assert "Voir le diagnostic" in error.payload["action_text"]


# ------------------------------------------------------- AD-20 : le contenu a changé
def test_un_contenu_incompatible_propose_recommencer_puis_reconstruit(make_box) -> None:
    box = make_box()
    assert box.panel()["content_changed"] is None
    box.path.write_text(
        SCENARIO.replace(
            "  - step_id: ensuite",
            "  - step_id: entre\n    type: repo_state\n    title_text: Une étape de plus\n"
            "    instruction_text: Ne faites rien.\n    explanation_text: Rien.\n"
            "    expect:\n      branches:\n        - name: main\n  - step_id: ensuite",
        ),
        encoding="utf-8",
        newline="\n",
    )
    assert box.panel()["content_changed"] == {"text": CONTENT_CHANGED_TEXT}
    old_hash = box.run_json()["content_hash"]

    events = box.run("restart")

    assert _of(events, Kind.APP_ERROR) == []
    run = box.run_json()
    assert run["content_hash"] != old_hash
    assert run["step_ids"] == ["annuler", "entre", "ensuite"]
    panel = box.panel()
    assert panel["content_changed"] is None
    assert [s["step_id"] for s in panel["steps"]] == ["annuler", "entre", "ensuite"]


def test_une_retouche_de_texte_ne_propose_rien(make_box) -> None:
    box = make_box()
    box.path.write_text(
        SCENARIO.replace("Une branche est un pointeur.", "Une branche pointe un commit."),
        encoding="utf-8",
        newline="\n",
    )
    assert box.panel()["content_changed"] is None


# ------------------------------------------------------------------------ l'intention
def test_l_intention_restart_est_enregistree_par_l_application(tmp_path: Path) -> None:
    from wavedevsecops.web.app import create_app  # noqa: PLC0415

    INTENTS.pop("restart", None)
    create_app(port=0, token="t", settings=Settings(data_dir=tmp_path / "d"))
    assert "restart" in INTENTS


def test_les_ecritures_sont_toujours_refusees_hors_restart(make_box) -> None:
    """Garde : seule `restart` est exemptée des refus d'écriture (4.5)."""
    box = make_box()
    run = box.run_json()
    save_run(box.engine.layout, {**run, "restore_failed": {"snapshot_id": 0, "reason_text": "x"}})
    with pytest.raises(Exception, match="Recommencez"):
        box.run("quiz_choice", {"choice_id": "revert"})
    box.run("restart")
    assert not box.run_json().get("restore_failed")
    assert QUIZ_REFUSED_TEXT  # texte inchangé
