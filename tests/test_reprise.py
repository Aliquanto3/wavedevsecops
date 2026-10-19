"""Reprendre le dernier scénario là où on l'a laissé (Story 6.4), sur le vrai git et le vrai
serveur : l'espace conservé est rouvert, jamais recréé ; sinon l'encart propose « Recommencer »."""

from __future__ import annotations

import http.client
import json
import time
from collections.abc import Iterator
from pathlib import Path

import pytest

from wavedevsecops import cli, wsfs
from wavedevsecops.config import Settings
from wavedevsecops.engine.resume import check_resume
from wavedevsecops.engine.runfile import load_run, save_run
from wavedevsecops.engine.workspace import prepare_workspace
from wavedevsecops.progress.facts import ProgressStore
from wavedevsecops.scenarios import load_scenario
from wavedevsecops.web.catalogue import catalogue_body
from wavedevsecops.wsfs import Layout

SCENARIO = """\
schema_version: 1
scenario_id: add-commit
mode: A
title_text: Add et commit
tracks: [llm, no_ai]
tools: [git]
setup:
  - op: write_file
    path: README.md
    content: "# Projet\\n"
  - op: commit
    message: Ajoute le README
    as: premier
  - op: push
    branch: main
    as: origin-main
steps:
  - step_id: creer_branche
    type: repo_state
    title_text: Créer la branche feature
    instruction_text: Créez la branche `feature` et placez-vous dessus.
    explanation_text: Une branche est un pointeur.
    expect:
      head:
        branch: feature
  - step_id: commiter
    type: repo_state
    title_text: Faire un commit
    instruction_text: Créez un fichier et commitez-le.
    explanation_text: Un commit fige l'index.
    expect:
      commits:
        - ahead_of: "@origin-main"
          min: 1
  - step_id: mettre_de_cote
    type: repo_state
    title_text: Mettre de côté
    instruction_text: Mettez-le de côté.
    explanation_text: Le stash garde les modifications.
    expect:
      stash:
        min: 1
"""

WAIT_S = 60.0


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    content = tmp_path / "content"
    (content / "scenarios").mkdir(parents=True)
    (content / "scenarios" / "add-commit.A.yaml").write_text(SCENARIO, encoding="utf-8")
    return Settings(data_dir=tmp_path / "data", content_dir=content)


@pytest.fixture
def prepared(settings: Settings, git_path: Path):
    path = settings.scenarios_path() / "add-commit.A.yaml"
    loaded = load_scenario(path, settings)
    prepare_workspace(loaded, "no_ai", settings=settings, git_path=git_path)
    layout = Layout.for_scenario(settings.workspaces_path(), "no_ai", "add-commit", "A")
    return loaded, layout


def _at_step(layout: Layout, step_id: str | None) -> None:
    save_run(layout, {**load_run(layout), "step_id": step_id})


def test_reprise_possible_donne_l_etape_n_sur_total(
    settings: Settings, git_path: Path, prepared
) -> None:
    loaded, layout = prepared
    _at_step(layout, "commiter")
    check = check_resume(layout, loaded, settings, git_path)
    assert (check.can_resume, check.step_number, check.step_total, check.reason) == (
        True,
        2,
        3,
        "",
    )


@pytest.mark.parametrize(
    ("alter", "reason"),
    [
        ("missing", "workspace_missing"),
        ("unreadable", "run_unreadable"),
        ("hash", "content_changed"),
        ("step", "step_unknown"),
        ("restore_failed", "broken"),
        ("no_git", "fingerprint"),
    ],
)
def test_reprise_refusee(
    alter: str, reason: str, settings: Settings, git_path: Path, prepared
) -> None:

    loaded, layout = prepared
    if alter == "missing":
        wsfs.remove_tree(layout.root)
    elif alter == "unreadable":
        layout.run_json.write_text("{ pas du json", encoding="utf-8")
    elif alter == "hash":
        save_run(layout, {**load_run(layout), "content_hash": "autre"})
    elif alter == "step":
        _at_step(layout, "disparue")
    elif alter == "restore_failed":
        save_run(layout, {**load_run(layout), "restore_failed": {"reason_text": "x"}})
    else:
        wsfs.remove_tree(layout.repo / ".git")
    check = check_resume(layout, loaded, settings, git_path)
    assert check.can_resume is False and check.reason == reason


def test_scenario_termine_n_offre_pas_de_reprise(
    settings: Settings, git_path: Path, prepared
) -> None:
    loaded, layout = prepared
    _at_step(layout, None)
    check = check_resume(layout, loaded, settings, git_path)
    assert check.offered is False


def test_catalogue_n_affiche_reprendre_que_sur_le_dernier_ouvert(
    settings: Settings, git_path: Path, prepared
) -> None:
    loaded, layout = prepared
    _at_step(layout, "commiter")

    def mode(track: str) -> dict:
        return catalogue_body(settings, track)["sections"][0]["scenarios"][0]["modes"][0]

    assert "resume" not in mode("no_ai")  # jamais ouvert via le catalogue
    store = ProgressStore.for_dir(settings.resolved_data_dir())
    store.set_last_opened("no_ai", "add-commit", "A")
    assert store.last_opened() == ("no_ai", "add-commit", "A")
    resume = mode("no_ai")["resume"]
    assert resume == {
        "can_resume": True,
        "step_number": 2,
        "step_total": 3,
        "text": "Étape 2 sur 3",
        "button_text": "Reprendre",
    }
    assert "resume" not in mode("llm")  # le dernier ouvert est dans l'autre parcours
    # Espace disparu : l'encart et « Recommencer », pas de bouton Reprendre.

    wsfs.remove_tree(layout.root)
    assert mode("no_ai")["resume"] == {
        "can_resume": False,
        "step_number": 0,
        "step_total": 3,
        "blocked_text": "Ce scénario ne peut pas reprendre là où vous l'aviez laissé.",
        "restart_text": "Recommencer",
    }


def test_dernier_ouvert_survit_et_se_remplace(settings: Settings) -> None:
    store = ProgressStore.for_dir(settings.resolved_data_dir())
    assert store.last_opened() is None
    store.set_last_opened("llm", "a", "A")
    store.set_last_opened("no_ai", "b", "B")
    assert store.last_opened() == ("no_ai", "b", "B")
    data = json.loads((settings.resolved_data_dir() / "progress.json").read_text("utf-8"))
    assert data["last_opened"]["scenario_id"] == "b"


@pytest.fixture
def instance(settings: Settings, git_path: Path) -> Iterator[cli.Instance]:
    inst = cli.start_instance(settings)
    try:
        yield inst
    finally:
        inst.stop()


def _call(inst: cli.Instance, method: str, path: str, body: object = None):
    conn = http.client.HTTPConnection(cli.HOST, inst.port, timeout=WAIT_S)
    conn.request("GET", f"/?t={inst.token}")
    first = conn.getresponse()
    first.read()
    headers = {"Cookie": first.getheader("Set-Cookie", "").split(";")[0]}
    data = None
    if method == "POST":
        headers["Origin"] = f"http://{cli.HOST}:{inst.port}"
        headers["Content-Type"] = "application/json"
        data = json.dumps(body).encode("utf-8")
    conn.request(method, path, body=data, headers=headers)
    resp = conn.getresponse()
    raw = resp.read()
    conn.close()
    return resp.status, json.loads(raw)


def _wait_idle(inst: cli.Instance, workspace_id: str) -> None:
    deadline = time.monotonic() + WAIT_S
    while True:
        _status, state = _call(inst, "GET", f"/api/ws/{workspace_id}/state")
        if state.get("state") == "idle" and state.get("epoch", 0) >= 1:
            return
        assert time.monotonic() < deadline, state
        time.sleep(0.1)


def test_api_ouvrir_reprendre_et_recommencer(instance: cli.Instance, settings: Settings) -> None:
    open_body = {"scenario_id": "add-commit", "mode": "A", "track": "no_ai"}
    workspace_id = "no_ai.add-commit.A"
    status, _ = _call(instance, "POST", "/api/open", open_body)
    assert status == 202
    _wait_idle(instance, workspace_id)
    layout = Layout.for_scenario(settings.workspaces_path(), "no_ai", "add-commit", "A")
    _at_step(layout, "commiter")
    marker = layout.repo / "travail-en-cours.txt"
    marker.write_text("à conserver\n", encoding="utf-8")

    status, body = _call(instance, "GET", "/api/catalogue?track=no_ai")
    resume = body["sections"][0]["scenarios"][0]["modes"][0]["resume"]
    assert status == 200 and resume["can_resume"] and resume["text"] == "Étape 2 sur 3"

    # Reprendre rouvre l'espace conservé : ni nouveau setup, ni perte de l'état du dépôt.
    status, again = _call(instance, "POST", "/api/open", {**open_body, "resume": True})
    assert status == 200 and again["preparing"] is False
    assert marker.read_text(encoding="utf-8") == "à conserver\n"
    assert load_run(layout)["step_id"] == "commiter"

    # Contenu du scénario modifié : la reprise est refusée, l'espace n'est pas touché.
    path = settings.scenarios_path() / "add-commit.A.yaml"
    path.write_text(SCENARIO.replace("Add et commit", "Add et commit v2"), encoding="utf-8")
    status, refused = _call(instance, "POST", "/api/open", {**open_body, "resume": True})
    assert (
        status == 409
        and "ne peut pas reprendre là où vous l'aviez laissé" in refused["reason_text"]
    )
    assert marker.exists()
    status, body = _call(instance, "GET", "/api/catalogue?track=no_ai")
    blocked = body["sections"][0]["scenarios"][0]["modes"][0]["resume"]
    assert blocked["can_resume"] is False and blocked["restart_text"] == "Recommencer"

    # Recommencer reconstruit l'espace à la première étape.
    status, _ = _call(instance, "POST", "/api/open", {**open_body, "restart": True})
    assert status == 202
    deadline = time.monotonic() + WAIT_S
    while True:  # le setup remplace l'espace dans la file : attendre la fin de la reconstruction
        try:
            if not marker.exists() and load_run(layout)["step_id"] == "creer_branche":
                break
        except Exception:  # noqa: BLE001 - run.json absent le temps de la reconstruction
            pass
        assert time.monotonic() < deadline
        time.sleep(0.1)
    time.sleep(0.5)
    status, body = _call(instance, "GET", "/api/catalogue?track=no_ai")
    assert body["sections"][0]["scenarios"][0]["modes"][0]["resume"]["text"] == "Étape 1 sur 3"
