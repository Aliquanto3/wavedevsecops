# ruff: noqa: E501
"""Correction relue dans le panneau (Story 5.5) : une étape de désignation fermée porte sa
correction (`step_panel.steps[].correction`), même forme que `answer_corrected`, avec le nom en
mots de chaque élément ; elle disparaît après « Recommencer »."""

from __future__ import annotations

from test_designation import _answer, _commit, _to_first_designation, make_box  # noqa: F401
from test_steps import WAIT

from wavedevsecops.engine import build_operation, load_run, restart
from wavedevsecops.events import Kind


def test_la_correction_est_dans_le_panneau_apres_fermeture_et_rechargement(make_box) -> None:  # noqa: F811
    box = make_box()
    _to_first_designation(box)
    before = box.engine.snapshot()["step_panel"]
    assert not any("correction" in s for s in before["steps"])  # rien avant la réponse
    wrong = _commit(box, "Ajoute l'application")
    events = _answer(box, [wrong], step_id="qui_a_casse")
    live = next(e for e in events if e.kind == Kind.ANSWER_CORRECTED).payload
    panel = box.engine.snapshot()["step_panel"]  # ce que lit un rechargement
    done = next(s for s in panel["steps"] if s["step_id"] == "qui_a_casse")
    assert done["state"] == "done" and done["correction"] == live
    mark = done["correction"]["slots"][0]
    assert mark["label_text"] == "Le commit en cause" and mark["correct"] is False
    assert mark["element_texts"][wrong].endswith("« Ajoute l'application »")
    assert mark["element_texts"][mark["expected_element_id"]].endswith("« Supprime la sauvegarde »")
    assert set(mark["element_texts"]) == {wrong, *mark["accepted_element_ids"]}
    assert not any("correction" in s for s in panel["steps"] if s["step_id"] != "qui_a_casse")
    # « Recommencer » (vraie intention de la story 4.4) remet les réponses à zéro : la correction
    # quitte le panneau.
    restart.register_intents()
    box.engine.submit(build_operation(box.engine, "restart", {})).result(WAIT)
    assert not load_run(box.engine.layout).get("answers")
    again = box.engine.snapshot()["step_panel"]
    assert not any("correction" in s for s in again["steps"])
