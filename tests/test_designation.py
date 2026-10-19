"""Désignation côté serveur, en un seul essai (Story 5.2) : vrai git, file d'opérations,
marques `designable`, correction, premier essai, `resolve_sha` (AD-2, AD-7, AD-14, AD-17)."""

from __future__ import annotations

import http.client
import json
import shutil
import time
from collections.abc import Iterator
from pathlib import Path

import pytest
from test_steps import WAIT, Box, _kinds

from wavedevsecops import cli
from wavedevsecops.config import Settings
from wavedevsecops.engine import (
    InvalidIntent,
    Operation,
    OperationRefused,
    WorkspaceManager,
    build_operation,
    designation,
    load_run,
    prepare_workspace,
    save_run,
)
from wavedevsecops.engine.designation import ALREADY_TEXT, NOT_DESIGNATION_TEXT, resolve_sha
from wavedevsecops.events import Envelope, Kind
from wavedevsecops.gitio import Git
from wavedevsecops.progress.facts import ProgressStore
from wavedevsecops.scenarios import ScenarioError, load_scenario, parse_scenario

ROOT = Path(__file__).resolve().parent.parent

SCENARIO = """\
schema_version: 1
scenario_id: designation
mode: B
title_text: Qu'a fait l'agent ?
tracks: [llm, no_ai]
tools: [git]
setup:
  - op: write_file
    path: app.txt
    content: "v1\\n"
  - op: commit
    message: Ajoute l'application
    as: base
  - op: write_file
    path: app.txt
    content: "v2\\n"
  - op: commit
    message: Supprime la sauvegarde
    author: agent
    as: casse
  - op: write_file
    path: app.txt
    content: "v3\\n"
  - op: commit
    message: Corrige une faute de frappe
    author: agent
    as: correctif
  - op: push
    branch: main
    as: origin-main
steps:
  - step_id: creer_branche
    type: repo_state
    title_text: Créer la branche feature
    instruction_text: Créez la branche `feature`.
    explanation_text: Une branche est un pointeur.
    expect:
      head:
        branch: feature
  - step_id: qui_a_casse
    type: designate
    title_text: Quel commit a cassé la sauvegarde ?
    instruction_text: Désignez le commit en cause.
    explanation_text: Le commit qui supprime la sauvegarde est le coupable.
    question_text: Quel commit de l'agent a supprimé la sauvegarde ?
    accept: [commit]
    slots:
      - slot_id: culprit
        label_text: Le commit en cause
        answers: ["@casse", "@correctif"]
        primary: "@casse"
  - step_id: deux_commits
    type: designate
    title_text: Deux commits
    instruction_text: Désignez les deux commits de l'agent.
    explanation_text: L'agent a fait deux commits.
    question_text: Quels sont les deux commits de l'agent ?
    accept: [commit]
    slots:
      - slot_id: first
        label_text: Le premier
        answers: ["@casse"]
        primary: "@casse"
      - slot_id: second
        label_text: Le second
        answers: ["@correctif"]
        primary: "@correctif"
  - step_id: creer_fin
    type: repo_state
    title_text: Créer la branche fin
    instruction_text: Créez la branche `fin`.
    explanation_text: Fin.
    expect:
      branches:
        - name: fin
"""


@pytest.fixture
def make_box(tmp_path: Path, git_path: Path) -> Iterator:
    boxes: list[Box] = []
    designation.register_intents()

    def make() -> Box:
        content = tmp_path / "content"
        (content / "scenarios").mkdir(parents=True)
        path = content / "scenarios" / "designation.B.yaml"
        path.write_text(SCENARIO, encoding="utf-8", newline="\n")
        settings = Settings(data_dir=tmp_path / "data", content_dir=content)
        manager = WorkspaceManager(settings, git_path=git_path, watch=False)
        loaded = load_scenario(path, settings)
        workspace_id = "llm.designation.B"
        events: list[Envelope] = []
        manager.events(workspace_id).attach(None, events.append)
        engine, setup = manager.create(loaded, "llm")
        setup.result(WAIT)
        git = Git.for_workspace(git_path, engine.layout.root, settings)
        box = Box(manager, engine, git, events, settings, path)
        boxes.append(box)
        return box

    yield make
    for box in boxes:
        box.manager.close()


def _shas(box: Box) -> dict[str, str]:
    commits = box.engine.last_projection.views["repo"]["commits"]
    return {c["subject"]: c["sha"] for c in commits}


def _commit(box: Box, subject: str) -> str:
    return f"commit:{_shas(box)[subject]}"


def _answer(box: Box, slots: list[str], **extra) -> list[Envelope]:
    start = len(box.events)
    op = build_operation(box.engine, "answer_submit", {"slots": slots, **extra})
    box.engine.submit(op).result(WAIT)
    return box.events[start:]


def _facts(box: Box) -> list[dict]:
    return ProgressStore.for_dir(box.settings.resolved_data_dir()).facts()


def _to_first_designation(box: Box) -> None:
    box.run("switch", "-c", "feature")
    assert box.step_id() == "qui_a_casse"


# -------------------------------------------------------------- étape et YAML
def test_le_yaml_declare_question_types_cases_et_alias() -> None:
    scenario = parse_scenario(SCENARIO, "designation.B.yaml")
    step = scenario.steps[1]
    assert step.type == "designate" and step.accept == ["commit"]
    assert step.slots[0].answers == ["@casse", "@correctif"] and step.slots[0].primary == "@casse"
    assert not scenario.authoring_warnings()


def _lint(text: str) -> dict[str, str]:
    with pytest.raises(ScenarioError) as info:
        parse_scenario(text, "designation.B.yaml")
    return {e.field: e.message for e in info.value.errors}


def test_lint_des_cases_de_designation() -> None:
    primary = SCENARIO.replace(
        'primary: "@casse"\n  - step_id: deux', 'primary: "@x"\n  - step_id: deux'
    )
    assert any("primary" in m for m in _lint(primary).values())
    accept = SCENARIO.replace(
        "accept: [commit]\n    slots:\n      - slot_id: culprit",
        "accept: [bidule]\n    slots:\n      - slot_id: culprit",
    )
    assert any("inconnu" in m for m in _lint(accept).values())
    alias = SCENARIO.replace('answers: ["@casse", "@correctif"]', 'answers: ["@casse", "@fantome"]')
    assert any("@fantome" in m for m in _lint(alias).values())


@pytest.mark.slow
def test_le_panneau_montre_la_question_jamais_les_bonnes_reponses(make_box) -> None:
    box = make_box()
    _to_first_designation(box)
    panel = box.engine.snapshot()["step_panel"]
    current = next(s for s in panel["steps"] if s["state"] == "current")
    assert current["designate"] == {
        "question_text": "Quel commit de l'agent a supprimé la sauvegarde ?",
        "accept": ["commit"],
        "slots": [{"slot_id": "culprit", "label_text": "Le commit en cause"}],
    }
    dumped = json.dumps(panel)
    assert "correctif" not in dumped.replace("Corrige", "") and "primary" not in dumped
    assert not any("designate" in s for s in panel["steps"] if s["state"] != "current")


# --------------------------------------------------------------- designable
def _flags(views: dict) -> dict[str, set[bool]]:
    commits = {n["designable"] for n in views["graph"]["nodes"]}
    refs = {r["designable"] for n in views["graph"]["nodes"] for r in n["refs"]}
    return {"commits": commits, "refs": refs}


@pytest.mark.slow
def test_la_projection_marque_designables_les_types_acceptes_seulement(make_box) -> None:
    box = make_box()
    assert _flags(box.engine.snapshot()["views"]) == {"commits": {True}, "refs": {True}}
    events = box.run("switch", "-c", "feature")
    # Les vues sont re-marquées pour l'étape suivante : un dernier `state_projected`.
    assert _kinds(events)[-6:] == [
        Kind.STATE_PROJECTED,
        Kind.STEP_VERDICT,
        Kind.STEP_EXPLANATION,
        Kind.PROGRESS_UPDATED,
        Kind.STATE_PROJECTED,
        Kind.ENGINE_STATE,
    ]
    last = [e for e in events if e.kind == Kind.STATE_PROJECTED][-1]
    assert _flags(last.payload["views"]) == {"commits": {True}, "refs": {False}}
    assert _flags(box.engine.snapshot()["views"]) == {"commits": {True}, "refs": {False}}
    # Une opération suivante conserve les marques (le projecteur les recalcule).
    box.run("status")
    assert _flags(box.engine.snapshot()["views"]) == {"commits": {True}, "refs": {False}}


@pytest.mark.slow
def test_une_etape_sans_designation_laisse_tout_designable(make_box) -> None:
    box = make_box()
    _to_first_designation(box)
    _answer(box, [_commit(box, "Supprime la sauvegarde")], step_id="qui_a_casse")
    _answer(
        box,
        [_commit(box, "Supprime la sauvegarde"), _commit(box, "Corrige une faute de frappe")],
        step_id="deux_commits",
    )
    assert box.step_id() == "creer_fin"
    assert _flags(box.engine.snapshot()["views"]) == {"commits": {True}, "refs": {True}}


@pytest.mark.slow
def test_le_reveil_d_un_espace_garde_les_marques(make_box) -> None:
    box = make_box()
    _to_first_designation(box)
    box.manager.sleep(box.engine.workspace_id)
    engine = box.manager.get(box.engine.workspace_id)
    # Projection d'ouverture du nouvel espace : l'étape courante est une désignation.
    engine.submit(Operation("terminal_line", lambda _ctx: 0, writes=False)).result(WAIT)
    assert _flags(engine.snapshot()["views"]) == {"commits": {True}, "refs": {False}}


# ---------------------------------------------------------------- correction
@pytest.mark.slow
def test_une_mauvaise_reponse_est_corrigee_une_seule_fois(make_box) -> None:
    box = make_box()
    _to_first_designation(box)
    wrong = _commit(box, "Ajoute l'application")
    events = _answer(box, [wrong], step_id="qui_a_casse")
    assert _kinds(events)[:3] == [Kind.ENGINE_STATE, Kind.OP_STARTED, Kind.ANSWER_CORRECTED]
    assert _kinds(events).index(Kind.ANSWER_CORRECTED) < _kinds(events).index(Kind.OP_EXIT)
    assert _kinds(events).index(Kind.STEP_VERDICT) > _kinds(events).index(Kind.STATE_PROJECTED)
    payload = next(e for e in events if e.kind == Kind.ANSWER_CORRECTED).payload
    mark = payload["slots"][0]
    culprit = _commit(box, "Supprime la sauvegarde")
    assert payload["step_id"] == "qui_a_casse" and payload["correct"] is False
    assert (mark["slot_id"], mark["element_id"], mark["correct"]) == ("culprit", wrong, False)
    assert mark["expected_element_id"] == culprit
    assert set(mark["accepted_element_ids"]) == {
        culprit,
        _commit(box, "Corrige une faute de frappe"),
    }
    assert culprit.split(":")[1][:7] in mark["text"] and "Supprime la sauvegarde" in mark["text"]
    assert "plus d'essai" in payload["summary_text"]
    # L'étape se ferme et le premier essai est consigné (run.json, puis faits).
    assert box.step_id() == "deux_commits"
    assert load_run(box.engine.layout)["answers"]["qui_a_casse"]["correct"] is False
    kinds = [(f["kind"], f["step_id"], f.get("correct")) for f in _facts(box)]
    assert ("quiz_first_attempt", "qui_a_casse", False) in kinds
    assert ("step_validated", "qui_a_casse", None) in kinds
    # Sans `step_id`, le corps est invalide (422) : il viserait la désignation suivante.
    with pytest.raises(InvalidIntent):
        build_operation(box.engine, "answer_submit", {"slots": [culprit]})
    # Une seconde soumission sur la même étape est refusée (409).
    with pytest.raises(OperationRefused) as again:
        build_operation(box.engine, "answer_submit", {"slots": [culprit], "step_id": "qui_a_casse"})
    assert again.value.reason_text == ALREADY_TEXT
    assert load_run(box.engine.layout)["answers"]["qui_a_casse"]["correct"] is False


@pytest.mark.slow
def test_la_bonne_reponse_et_un_equivalent(make_box) -> None:
    box = make_box()
    _to_first_designation(box)
    equivalent = _commit(box, "Corrige une faute de frappe")
    events = _answer(box, [equivalent], step_id="qui_a_casse")
    payload = next(e for e in events if e.kind == Kind.ANSWER_CORRECTED).payload
    mark = payload["slots"][0]
    assert payload["correct"] is True and mark["correct"] and mark["equivalent"]
    assert mark["expected_element_id"] == _commit(box, "Supprime la sauvegarde")
    assert "convient aussi" in mark["text"] and payload["summary_text"] == "Désignation juste."
    assert ("quiz_first_attempt", "qui_a_casse", True) in [
        (f["kind"], f["step_id"], f.get("correct")) for f in _facts(box)
    ]
    verdict = next(e for e in events if e.kind == Kind.STEP_VERDICT).payload
    assert verdict["passed"] is True and verdict["next_step_id"] == "deux_commits"


@pytest.mark.slow
def test_principal_juste_sans_equivalent(make_box) -> None:
    box = make_box()
    _to_first_designation(box)
    events = _answer(box, [_commit(box, "Supprime la sauvegarde")], step_id="qui_a_casse")
    mark = next(e for e in events if e.kind == Kind.ANSWER_CORRECTED).payload["slots"][0]
    assert mark["correct"] and not mark["equivalent"] and "c'est bien" in mark["text"]


@pytest.mark.slow
def test_plusieurs_cases_correction_par_case(make_box) -> None:
    box = make_box()
    _to_first_designation(box)
    casse, fix = _commit(box, "Supprime la sauvegarde"), _commit(box, "Corrige une faute de frappe")
    _answer(box, [casse], step_id="qui_a_casse")
    events = _answer(box, [casse, casse], step_id="deux_commits")  # la 2e case est fausse
    payload = next(e for e in events if e.kind == Kind.ANSWER_CORRECTED).payload
    assert [m["correct"] for m in payload["slots"]] == [True, False]
    assert payload["correct"] is False and "partielle" in payload["summary_text"]
    assert payload["slots"][1]["expected_element_id"] == fix
    [fact] = [
        f for f in _facts(box) if f["step_id"] == "deux_commits" and f["kind"] != "step_validated"
    ]
    assert fact["kind"] == "quiz_first_attempt" and fact["correct"] is False


@pytest.mark.slow
def test_refus_connus_d_avance_sans_consommer_l_essai(make_box) -> None:
    box = make_box()
    # Étape 1 : ce n'est pas une désignation.
    with pytest.raises(OperationRefused) as none:
        build_operation(
            box.engine,
            "answer_submit",
            {"slots": [_commit(box, "Ajoute l'application")], "step_id": "creer_branche"},
        )
    assert none.value.reason_text == NOT_DESIGNATION_TEXT
    _to_first_designation(box)
    good = _commit(box, "Supprime la sauvegarde")

    def refused(**body) -> str:
        with pytest.raises(OperationRefused) as info:
            build_operation(box.engine, "answer_submit", {"step_id": "qui_a_casse", **body})
        return info.value.reason_text

    assert "1 réponse" in refused(slots=[good, good])
    assert "pas un élément" in refused(slots=["n'importe quoi"])
    assert "pas accepté" in refused(slots=["ref:refs/heads/main"])
    assert "n'existe pas" in refused(slots=["commit:" + "0" * 40])
    assert refused(slots=[good], step_id="deux_commits") == NOT_DESIGNATION_TEXT
    assert "answers" not in load_run(box.engine.layout)  # aucun essai consommé
    assert box.step_id() == "qui_a_casse"


@pytest.mark.slow
def test_deux_soumissions_en_file_la_seconde_est_dite_a_l_ecran(make_box) -> None:
    box = make_box()
    _to_first_designation(box)
    good = _commit(box, "Supprime la sauvegarde")
    start = len(box.events)
    first = build_operation(
        box.engine, "answer_submit", {"slots": [good], "step_id": "qui_a_casse"}
    )
    second = build_operation(
        box.engine, "answer_submit", {"slots": [good], "step_id": "qui_a_casse"}
    )
    futures = [box.engine.submit(first), box.engine.submit(second)]
    assert [f.result(WAIT).code for f in futures] == [0, 2]
    events = box.events[start:]
    assert _kinds(events).count(Kind.ANSWER_CORRECTED) == 1
    refused = [
        e for e in events if e.kind == Kind.TERMINAL_OUTPUT and e.payload["stream"] == "refused"
    ]
    assert refused and refused[0].payload["text"] == ALREADY_TEXT
    assert len([f for f in _facts(box) if f["kind"] == "quiz_first_attempt"]) == 1


@pytest.mark.slow
def test_arret_entre_la_reponse_et_la_fermeture_de_l_etape(make_box) -> None:
    """`run.json` garde la réponse mais l'étape n'est pas fermée : la soumission suivante
    termine la fermeture avec la correction consignée, sans nouvelle correction."""
    box = make_box()
    _to_first_designation(box)
    wrong = _commit(box, "Ajoute l'application")
    _answer(box, [wrong], step_id="qui_a_casse")
    run = load_run(box.engine.layout)
    recorded = run["answers"]["qui_a_casse"]
    save_run(box.engine.layout, {**run, "step_id": "qui_a_casse", "validated": []})
    good = _commit(box, "Supprime la sauvegarde")
    events = _answer(box, [good], step_id="qui_a_casse")
    payload = next(e for e in events if e.kind == Kind.ANSWER_CORRECTED).payload
    assert payload["correct"] is False and payload["slots"][0]["element_id"] == wrong
    assert load_run(box.engine.layout)["answers"]["qui_a_casse"] == recorded
    assert box.step_id() == "deux_commits"


@pytest.mark.slow
def test_le_rejeu_apres_arret_brutal_rend_le_premier_essai(make_box) -> None:
    box = make_box()
    _to_first_designation(box)
    _answer(box, [_commit(box, "Ajoute l'application")], step_id="qui_a_casse")
    box.manager.sleep(box.engine.workspace_id)
    path = box.settings.resolved_data_dir() / "progress.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    data["facts"] = [f for f in data["facts"] if f["step_id"] != "qui_a_casse"]
    path.write_text(json.dumps(data), encoding="utf-8")
    box.manager.get(box.engine.workspace_id)
    # Le rejeu tourne dans le fil de l'espace, au réveil : on l'attend.
    deadline = time.monotonic() + WAIT
    kinds: list[tuple] = []
    while time.monotonic() < deadline:
        kinds = [(f["kind"], f["step_id"], f.get("correct")) for f in _facts(box)]
        if ("step_validated", "qui_a_casse", None) in kinds:
            break
        time.sleep(0.05)
    assert ("quiz_first_attempt", "qui_a_casse", False) in kinds
    assert ("step_validated", "qui_a_casse", None) in kinds


# --------------------------------------------------------------- resolve_sha
@pytest.mark.slow
def test_resolve_sha_apercu_sans_consommer_l_essai(make_box) -> None:
    box = make_box()
    _to_first_designation(box)
    views = box.engine.last_projection.views
    sha = _shas(box)["Supprime la sauvegarde"]
    status, body = resolve_sha(views, sha[:7])
    assert status == 200
    assert set(body) == {"element_id", "sha", "short_sha", "subject", "author_text", "actor"}
    assert (body["element_id"], body["sha"], body["short_sha"]) == (f"commit:{sha}", sha, sha[:7])
    assert (body["subject"], body["actor"]) == ("Supprime la sauvegarde", "agent")
    assert body["author_text"]
    assert resolve_sha(views, sha.upper())[0] == 200  # casse sans importance
    assert resolve_sha(views, sha)[0] == 200
    assert "answers" not in load_run(box.engine.layout) and box.step_id() == "qui_a_casse"


@pytest.mark.slow
def test_resolve_sha_refus_clairs_en_francais(make_box) -> None:
    box = make_box()
    views = box.engine.last_projection.views
    sha = _shas(box)["Supprime la sauvegarde"]
    assert resolve_sha(views, "")[0] == resolve_sha(views, sha[:6])[0] == 422
    assert resolve_sha(views, "zzzzzzz")[0] == 422
    status, body = resolve_sha(views, "0000000" if not sha.startswith("0000000") else "1111111")
    assert status == 404 and "Aucun commit" in body["reason_text"]
    # Ambiguïté : deux commits qui partagent le préfixe.
    commits = views["repo"]["commits"]
    twin = {**commits[0], "sha": commits[1]["sha"][:10] + commits[0]["sha"][10:]}
    fake = {"repo": {**views["repo"], "commits": [commits[1], twin]}}
    status, body = resolve_sha(fake, commits[1]["sha"][:7])
    assert status == 409 and "Plusieurs commits" in body["reason_text"]


# --------------------------------------------------------------------- HTTP
@pytest.fixture
def instance(tmp_path: Path, git_path: Path) -> Iterator[cli.Instance]:
    content = tmp_path / "content"
    shutil.copytree(ROOT / "content", content)
    path = content / "scenarios" / "designation.B.yaml"
    path.write_text(SCENARIO, encoding="utf-8", newline="\n")
    settings = Settings(data_dir=tmp_path / "data", content_dir=content)
    prepare_workspace(load_scenario(path, settings), "llm", settings=settings, git_path=git_path)
    inst = cli.start_instance(settings)
    try:
        yield inst
    finally:
        inst.stop()


def _http(inst: cli.Instance, method: str, path: str, cookie: str, body: object = None):
    conn = http.client.HTTPConnection(cli.HOST, inst.port, timeout=WAIT)
    headers = {"Cookie": cookie, "Origin": f"http://{cli.HOST}:{inst.port}"}
    data = json.dumps(body).encode() if body is not None else None
    if data is not None:
        headers["Content-Type"] = "application/json"
    conn.request(method, path, body=data, headers=headers)
    resp = conn.getresponse()
    raw = resp.read()
    conn.close()
    return resp.status, json.loads(raw) if raw else {}


@pytest.mark.slow
def test_http_resolve_sha_et_seconde_soumission_en_409(
    instance: cli.Instance, git_path: Path
) -> None:
    conn = http.client.HTTPConnection(cli.HOST, instance.port, timeout=WAIT)
    conn.request("GET", f"/?t={instance.token}")
    resp = conn.getresponse()
    resp.read()
    conn.close()
    cookie = resp.getheader("Set-Cookie", "").split(";")[0]
    ws = "llm.designation.B"
    deadline = time.monotonic() + WAIT
    while True:  # la projection d'ouverture se fait dans la file de l'espace
        status, state = _http(instance, "GET", f"/api/ws/{ws}/state", cookie)
        assert status == 200
        if state["views"] or time.monotonic() > deadline:
            break
        time.sleep(0.1)
    # `resolve_sha` : 200 avec l'aperçu, sans consommer l'essai.
    commits = state["views"]["repo"]["commits"]
    sha = next(c["sha"] for c in commits if c["subject"] == "Supprime la sauvegarde")
    status, body = _http(instance, "GET", f"/api/ws/{ws}/resolve_sha?prefix={sha[:7]}", cookie)
    assert (status, body["short_sha"], body["subject"]) == (200, sha[:7], "Supprime la sauvegarde")
    status, body = _http(instance, "GET", f"/api/ws/{ws}/resolve_sha?prefix=abc", cookie)
    assert status == 422 and "7 caractères" in body["reason_text"]
    status, body = _http(instance, "GET", f"/api/ws/{ws}/resolve_sha?prefix=0000000", cookie)
    assert status == 404 and "Aucun commit" in body["reason_text"]
    # Étape 1 (créer la branche) : pas de désignation attendue, 409 en français.
    status, body = _http(
        instance,
        "POST",
        f"/api/ws/{ws}/answer_submit",
        cookie,
        {"slots": [f"commit:{sha}"], "step_id": "creer_branche"},
    )
    assert status == 409 and body["reason_text"] == NOT_DESIGNATION_TEXT
    # Corps invalide : 422 (`slots` vide, ou `step_id` absent).
    status, _ = _http(instance, "POST", f"/api/ws/{ws}/answer_submit", cookie, {"slots": []})
    assert status == 422
    status, _ = _http(
        instance, "POST", f"/api/ws/{ws}/answer_submit", cookie, {"slots": [f"commit:{sha}"]}
    )
    assert status == 422
    # Étape 2 atteinte par une vraie commande : une réponse (202), puis la seconde (409).
    line = {"line": "git switch -c feature"}
    status, _ = _http(instance, "POST", f"/api/ws/{ws}/terminal_line", cookie, line)
    assert status == 202
    answer = {"slots": [f"commit:{sha}"], "step_id": "qui_a_casse"}
    deadline = time.monotonic() + WAIT
    while True:  # la commande s'exécute dans la file : l'étape se ferme à son verdict
        status, body = _http(instance, "POST", f"/api/ws/{ws}/answer_submit", cookie, answer)
        if status == 202 or time.monotonic() > deadline:
            break
        time.sleep(0.2)
    assert status == 202
    deadline = time.monotonic() + WAIT
    while time.monotonic() < deadline:  # la correction est faite dans la file
        status, body = _http(instance, "POST", f"/api/ws/{ws}/answer_submit", cookie, answer)
        if status == 409:
            break
        time.sleep(0.2)
    assert status == 409 and body["reason_text"] == ALREADY_TEXT
