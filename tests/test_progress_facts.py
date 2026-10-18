"""Faits du premier passage (Story 4.2) : magasin idempotent, états dérivés, reprise (AD-14)."""

from __future__ import annotations

import json
import threading
from datetime import datetime
from pathlib import Path

import pytest

from wavedevsecops.progress import FutureSchemaError, UnreadableDataError, ensure_progress
from wavedevsecops.progress.facts import Fact, ProgressStore, derive

TRACK, SCENARIO, MODE = "llm", "etapes", "A"


def fact(kind: str = "step_validated", step_id: str = "s1", op_id: str = "op1", **extra) -> Fact:
    return Fact(
        kind=kind,
        track=TRACK,
        scenario_id=SCENARIO,
        mode=MODE,
        step_id=step_id,
        workspace_id="llm.etapes.A",
        epoch=0,
        op_id=op_id,
        **extra,
    )


@pytest.fixture
def store(tmp_path: Path) -> ProgressStore:
    return ProgressStore(tmp_path)


def stored(store: ProgressStore) -> list[dict]:
    return json.loads((store.data_dir / "progress.json").read_text(encoding="utf-8"))["facts"]


def test_un_fait_est_ajoute_dans_progress_json(store: ProgressStore) -> None:
    added = store.submit([fact()])
    assert [f.step_id for f in added] == ["s1"]
    data = json.loads((store.data_dir / "progress.json").read_text(encoding="utf-8"))
    assert data["schema_version"] == 1
    assert data["first_launch_at"]  # le fichier de base est conservé
    [entry] = data["facts"]
    assert (entry["track"], entry["scenario_id"], entry["mode"], entry["step_id"]) == (
        TRACK,
        SCENARIO,
        MODE,
        "s1",
    )
    assert (entry["workspace_id"], entry["epoch"], entry["op_id"]) == ("llm.etapes.A", 0, "op1")
    assert entry["at"]
    assert not (store.data_dir / "progress.json.tmp").exists()


def test_meme_cle_soumise_deux_fois_est_ignoree(store: ProgressStore) -> None:
    assert store.submit([fact()])
    assert store.submit([fact()]) == []
    assert len(stored(store)) == 1


def test_le_premier_passage_n_est_jamais_remplace(store: ProgressStore) -> None:
    store.submit([fact("quiz_first_attempt", correct=False)])
    # Recommencer : autre opération, autre epoch, réponse juste : ignorée.
    again = fact("quiz_first_attempt", op_id="op2", correct=True).model_copy(update={"epoch": 3})
    assert store.submit([again]) == []
    [entry] = stored(store)
    assert entry["correct"] is False and entry["op_id"] == "op1"
    assert store.progress(TRACK, SCENARIO, MODE).first_try_score == 0


def test_faits_par_parcours_et_par_etape(store: ProgressStore) -> None:
    other = fact().model_copy(update={"track": "no_ai"})
    added = store.submit([fact(), fact(step_id="s2"), other])
    assert len(added) == 3
    assert store.progress("no_ai", SCENARIO, MODE).steps_validated == ["s1"]
    assert store.progress(TRACK, SCENARIO, MODE).steps_validated == ["s1", "s2"]


def test_indices_par_palier_et_etat_derive(store: ProgressStore) -> None:
    assert store.progress(TRACK, SCENARIO, MODE).state == "todo"
    store.submit([fact(), fact("hint_opened", tier=1, delay_ms=900, read_ms=3000)])
    store.submit([fact("hint_opened", tier=1, op_id="x"), fact("hint_opened", tier=2, op_id="y")])
    state = store.progress(TRACK, SCENARIO, MODE)
    assert (state.state, state.hints) == ("in_progress", 2)
    store.submit([fact("scenario_completed", step_id="")])
    store.submit([fact("scenario_completed", step_id="", op_id="z")])
    assert store.progress(TRACK, SCENARIO, MODE).state == "done"
    assert sum(1 for f in stored(store) if f["kind"] == "scenario_completed") == 1


def test_score_du_premier_coup() -> None:
    answers = {"q1": True, "q2": False, "q3": True, "q4": True}
    facts = [
        {
            "kind": "quiz_first_attempt",
            "step_id": step,
            "correct": ok,
            "track": TRACK,
            "scenario_id": SCENARIO,
            "mode": MODE,
        }
        for step, ok in answers.items()
    ]
    state = derive(facts, TRACK, SCENARIO, MODE)
    assert (state.quiz_total, state.quiz_correct, state.first_try_score) == (4, 3, 75)
    assert derive([], TRACK, SCENARIO, MODE).first_try_score is None


def test_ecritures_concurrentes_sous_un_seul_verrou(tmp_path: Path) -> None:
    def submit(i: int) -> None:
        ProgressStore.for_dir(tmp_path).submit([fact(step_id=f"s{i}", op_id=f"op{i}")])

    threads = [threading.Thread(target=submit, args=(i,)) for i in range(20)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert ProgressStore.for_dir(tmp_path) is ProgressStore.for_dir(tmp_path)
    assert len(ProgressStore.for_dir(tmp_path).facts()) == 20


def test_fichier_d_une_version_future_n_est_pas_modifie(store: ProgressStore) -> None:
    path = store.data_dir / "progress.json"
    path.write_text(json.dumps({"schema_version": 99}), encoding="utf-8")
    with pytest.raises(FutureSchemaError):
        store.submit([fact()])
    assert json.loads(path.read_text(encoding="utf-8")) == {"schema_version": 99}


def test_fichier_illisible_donne_une_erreur_claire(store: ProgressStore) -> None:
    (store.data_dir / "progress.json").write_text("{pas du json", encoding="utf-8")
    with pytest.raises(UnreadableDataError):
        store.submit([fact()])


def test_un_progress_json_sans_faits_reste_valide(tmp_path: Path) -> None:
    ensure_progress(tmp_path, datetime.now().astimezone())
    store = ProgressStore(tmp_path)
    assert store.facts() == []
    assert store.submit([fact()])


def test_arret_pendant_l_ecriture_laisse_le_fichier_precedent(
    store: ProgressStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Écriture interrompue avant le renommage : `progress.json` reste entier et lisible."""
    import wavedevsecops.progress as progress_module

    store.submit([fact()])
    before = (store.data_dir / "progress.json").read_bytes()

    def crash(*_args: object) -> None:
        raise KeyboardInterrupt  # arrêt brutal entre l'écriture du temporaire et le renommage

    monkeypatch.setattr(progress_module.os, "replace", crash)
    with pytest.raises(KeyboardInterrupt):
        store.submit([fact(step_id="s2", op_id="op2")])
    assert (store.data_dir / "progress.json").read_bytes() == before
    monkeypatch.undo()
    assert [f.step_id for f in store.submit([fact(step_id="s2", op_id="op2")])] == ["s2"]
    assert [f["step_id"] for f in stored(store)] == ["s1", "s2"]


def test_tous_les_etats_en_un_passage(store: ProgressStore) -> None:
    other = fact().model_copy(update={"track": "no_ai"})
    store.submit([fact(), fact("scenario_completed", step_id="", op_id="z"), other])
    states = store.all_progress()
    assert set(states) == {(TRACK, SCENARIO, MODE), ("no_ai", SCENARIO, MODE)}
    assert states[(TRACK, SCENARIO, MODE)].state == "done"
    assert states[("no_ai", SCENARIO, MODE)] == store.progress("no_ai", SCENARIO, MODE)
    assert states[("no_ai", SCENARIO, MODE)].state == "in_progress"
