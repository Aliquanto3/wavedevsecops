"""Faits du premier passage dans le moteur (Story 4.2, AD-14) : `run.json` d'abord, puis les
faits ; rejeu au démarrage sans doublon ; `progress_updated` émis.

Réutilise la boîte de `test_steps.py` (vrai git, scénario à trois étapes).
"""

from __future__ import annotations

import json

from test_steps import Box, make_box  # noqa: F401 - `make_box` est une fixture
from test_steps import _kinds as kinds

from wavedevsecops.engine import Operation, WorkspaceManager, load_run, save_run
from wavedevsecops.events import Envelope, Kind
from wavedevsecops.progress.facts import ProgressStore


def _facts(box: Box) -> list[dict]:
    path = box.settings.resolved_data_dir() / "progress.json"
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8")).get("facts", [])


def test_une_etape_validee_est_enregistree_apres_run_json(make_box) -> None:  # noqa: F811
    box = make_box()
    assert _facts(box) == []
    events = box.run("switch", "-c", "feature")
    assert box.step_id() == "commiter"  # `run.json` est à jour quand le fait est enregistré
    [fact] = _facts(box)
    assert (fact["kind"], fact["step_id"], fact["track"]) == (
        "step_validated",
        "creer_branche",
        "llm",
    )
    assert (fact["scenario_id"], fact["mode"]) == ("etapes", "A")
    assert (fact["workspace_id"], fact["epoch"]) == ("llm.etapes.A", box.engine.epoch)
    assert fact["op_id"] == next(e for e in events if e.kind == Kind.STEP_VERDICT).op_id
    progress = next(e for e in events if e.kind == Kind.PROGRESS_UPDATED)
    assert progress.payload["facts"] == ["step_validated"]
    assert progress.payload["step_ids"] == ["creer_branche"]
    # Une commande qui ne valide rien n'ajoute rien et n'émet rien.
    assert Kind.PROGRESS_UPDATED not in kinds(box.run("status"))
    assert len(_facts(box)) == 1


def test_fin_du_scenario_et_etats_derives(make_box) -> None:  # noqa: F811
    box = make_box()
    box.run("switch", "-c", "feature")
    box.run("commit", "-q", "--allow-empty", "-m", "Travail")
    box.run(write={"README.md": "# Projet modifié\n"})
    box.run("stash", "push", "-q")
    assert [(f["kind"], f["step_id"]) for f in _facts(box)] == [
        ("step_validated", "creer_branche"),
        ("step_validated", "commiter"),
        ("step_validated", "mettre_de_cote"),
        ("scenario_completed", ""),
    ]
    progress = ProgressStore.for_dir(box.settings.resolved_data_dir())
    state = progress.progress("llm", "etapes", "A")
    assert state.state == "done"
    assert state.steps_validated == ["creer_branche", "commiter", "mettre_de_cote"]
    assert progress.progress("no_ai", "etapes", "A").state == "todo"  # autre parcours


def test_arret_brutal_entre_run_json_et_les_faits(make_box) -> None:  # noqa: F811
    """`run.json` avance mais les faits manquent : le redémarrage les soumet, une seule fois."""
    box = make_box()
    run = load_run(box.engine.layout)
    save_run(box.engine.layout, {**run, "step_id": "mettre_de_cote"})  # deux étapes passées
    assert _facts(box) == []
    manager, workspace_id = box.manager, box.engine.workspace_id
    manager.sleep(workspace_id)
    events: list[Envelope] = []
    manager.events(workspace_id).attach(None, events.append)
    _reopen(manager, workspace_id)  # réveil : rejeu
    assert [f["step_id"] for f in _facts(box)] == ["creer_branche", "commiter"]
    assert kinds(events).count(Kind.PROGRESS_UPDATED) == 1
    # Deuxième redémarrage : ni doublon ni événement.
    events.clear()
    manager.sleep(workspace_id)
    _reopen(manager, workspace_id)
    assert len(_facts(box)) == 2
    assert Kind.PROGRESS_UPDATED not in kinds(events)


def test_arret_brutal_apres_la_derniere_etape(make_box) -> None:  # noqa: F811
    box = make_box()
    save_run(box.engine.layout, {**load_run(box.engine.layout), "step_id": None})
    box.manager.sleep(box.engine.workspace_id)
    _reopen(box.manager, box.engine.workspace_id)
    assert [f["kind"] for f in _facts(box)] == ["step_validated"] * 3 + ["scenario_completed"]


def test_recommencer_ne_compte_pas_deux_fois(make_box) -> None:  # noqa: F811
    box = make_box()
    box.run("switch", "-c", "feature")
    save_run(box.engine.layout, {**load_run(box.engine.layout), "step_id": "creer_branche"})
    box.manager.sleep(box.engine.workspace_id)
    _reopen(box.manager, box.engine.workspace_id)
    assert [f["step_id"] for f in _facts(box)] == ["creer_branche"]


def _reopen(manager: WorkspaceManager, workspace_id: str) -> None:
    """Rouvre l espace puis attend que sa file ait fini son rejeu (elle le fait avant tout)."""
    engine = manager.get(workspace_id)
    engine.submit(Operation("sync", lambda _ctx: 0, writes=False, validate=False)).result(60)
