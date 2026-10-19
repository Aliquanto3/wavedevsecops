"""Bilan de fin de scénario (Story 4.7, AD-14, AD-2) : textes du `score-summary`, panneau lu dans
`progress.json`, identique après redémarrage et après Recommencer, scénario suivant."""

from __future__ import annotations

import pytest
from test_progress_engine import _reopen
from test_steps import Box, make_box  # noqa: F401 - `make_box` est une fixture

from wavedevsecops.engine import load_run, save_run
from wavedevsecops.events import Kind
from wavedevsecops.progress.facts import Fact, ScenarioProgress
from wavedevsecops.progress.summary import build_summary, hints_text, score_text

NEXT = """\
schema_version: 1
scenario_id: zeta
mode: A
title_text: Scénario suivant d'essai
tracks: [no_ai]
tools: [git]
"""


@pytest.mark.parametrize(
    ("count", "text"), [(0, "0 indice"), (1, "1 indice"), (2, "2 indices"), (12, "12 indices")]
)
def test_accord_des_indices(count: int, text: str) -> None:
    assert hints_text(count) == text


def test_gabarit_du_score() -> None:
    summary = build_summary(ScenarioProgress(quiz_total=4, quiz_correct=3, hints=1))
    assert summary["text"] == "3 sur 4 du premier coup · 1 indice"
    assert (summary["quiz_correct"], summary["quiz_total"], summary["hints"]) == (3, 4, 1)
    assert build_summary(ScenarioProgress(quiz_total=2, hints=0))["text"] == (
        "0 sur 2 du premier coup · 0 indice"
    )
    assert score_text(0, 0) == "Aucune question dans ce scénario"


def _fact(box: Box, kind: str, step_id: str, **extra) -> Fact:
    return Fact(
        kind=kind,  # type: ignore[arg-type]
        track=box.engine.workspace_id.split(".")[0],
        scenario_id="etapes",
        mode="A",
        step_id=step_id,
        workspace_id=box.engine.workspace_id,
        epoch=box.engine.epoch,
        op_id="essai",
        **extra,
    )


def _finish(box: Box) -> None:
    box.run("switch", "-c", "feature")
    box.run("commit", "-q", "--allow-empty", "-m", "Travail")
    box.run(write={"README.md": "# Projet modifié\n"})
    box.run("stash", "push", "-q")


def _summary(box: Box) -> dict | None:
    return box.engine.snapshot()["step_panel"]["summary"]


@pytest.mark.slow
def test_pas_de_bilan_avant_la_fin(make_box) -> None:  # noqa: F811
    box = make_box()
    assert _summary(box) is None
    box.run("switch", "-c", "feature")
    assert _summary(box) is None


@pytest.mark.slow
def test_bilan_a_la_fin_lu_dans_progress_json(make_box) -> None:  # noqa: F811
    box = make_box()
    box.engine._progress.submit(
        [
            _fact(box, "quiz_first_attempt", "creer_branche", correct=True),
            _fact(box, "quiz_first_attempt", "commiter", correct=False),
            _fact(box, "hint_opened", "commiter", tier=1, delay_ms=10, read_ms=10),
        ]
    )
    _finish(box)
    summary = _summary(box)
    assert summary["text"] == "1 sur 2 du premier coup · 1 indice"
    assert summary["score_text"] == "1 sur 2 du premier coup"
    assert summary["hints_text"] == "1 indice"
    assert summary["next"] is None  # un seul scénario du catalogue pour ce mode
    assert summary["next_none_text"]
    # L'événement qui annonce la fin pousse le front à relire l'état.
    done = [
        e
        for e in box.events
        if e.kind == Kind.PROGRESS_UPDATED and "scenario_completed" in e.payload["facts"]
    ]
    assert len(done) == 1


@pytest.mark.slow
def test_bilan_identique_apres_redemarrage_et_recommencer(make_box) -> None:  # noqa: F811
    box = make_box()
    box.engine._progress.submit([_fact(box, "quiz_first_attempt", "commiter", correct=True)])
    _finish(box)
    before = _summary(box)
    assert before is not None
    box.manager.sleep(box.engine.workspace_id)
    _reopen(box.manager, box.engine.workspace_id)
    reopened = box.manager.get(box.engine.workspace_id)
    assert reopened.snapshot()["step_panel"]["summary"] == before
    # Recommencer remet le pointeur au début : plus de bilan ; fini de nouveau, le même bilan
    # (le premier passage fait foi).
    run = load_run(reopened.layout)
    save_run(reopened.layout, {**run, "step_id": "creer_branche", "validated": []})
    assert reopened.snapshot()["step_panel"]["summary"] is None
    save_run(reopened.layout, {**load_run(reopened.layout), "step_id": None})
    assert reopened.snapshot()["step_panel"]["summary"] == before


@pytest.mark.slow
def test_scenario_suivant_du_catalogue(make_box) -> None:  # noqa: F811
    box = make_box("no_ai")
    (box.scenario_path.parent / "zeta.A.yaml").write_text(NEXT, encoding="utf-8", newline="\n")
    (box.scenario_path.parent / "zeta.B.yaml").write_text(
        NEXT.replace("mode: A", "mode: B"), encoding="utf-8", newline="\n"
    )
    _finish(box)
    assert _summary(box)["next"] == {
        "scenario_id": "zeta",
        "mode": "A",
        "track": "no_ai",
        "title_text": "Scénario suivant d'essai",
    }


def test_total_vient_du_scenario_si_le_suivi_est_perdu() -> None:
    # progress.json absent après la fin : le scénario pose 2 questions, pas « Aucune question ».
    summary = build_summary(ScenarioProgress(), asked=2)
    assert summary["text"] == "0 sur 2 du premier coup · 0 indice"
    assert build_summary(ScenarioProgress(quiz_total=3, quiz_correct=3), asked=2)["quiz_total"] == 3


def test_scenario_suivant_suit_l_ordre_du_socle(make_box) -> None:  # noqa: F811
    # FR-9 : add-commit, push-pull, branche… et non l'ordre alphabétique (add-commit → branche).
    box = make_box("no_ai")
    folder = box.scenario_path.parent

    def write(scenario_id: str, section: str | None) -> None:
        text = NEXT.replace("scenario_id: zeta", f"scenario_id: {scenario_id}")
        if section:
            text += f"section: {section}\n"
        (folder / f"{scenario_id}.A.yaml").write_text(text, encoding="utf-8", newline="\n")

    write("add-commit", None)
    write("branche", "socle-git")
    write("push-pull", "socle-git")  # sans section ou « socle-git » : même section
    write("aaa-autre", "securite")
    runner = box.manager._steps
    current = runner._load(folder / "add-commit.A.yaml")
    assert runner._next_scenario(current, "no_ai")["scenario_id"] == "push-pull"
    current = runner._load(folder / "push-pull.A.yaml")
    assert runner._next_scenario(current, "no_ai")["scenario_id"] == "branche"
    # Un scénario hors de la liste vient après le socle connu, par identifiant.
    current = runner._load(folder / "branche.A.yaml")
    assert runner._next_scenario(current, "no_ai")["scenario_id"] == "etapes"
    # Le scénario d'une autre section n'est jamais proposé, même s'il vient avant.
    current = runner._load(folder / "aaa-autre.A.yaml")
    assert runner._next_scenario(current, "no_ai") is None
