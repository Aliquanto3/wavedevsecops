"""Validation d'étape sur l'état réel du dépôt (Story 4.1) : vrai git, ordre fixe des événements,
`step_id` stable, verdict `unexpected`, lint de contenu (AD-7, AD-1)."""

from __future__ import annotations

import os
import re
import warnings
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

import pytest

from wavedevsecops.config import Settings
from wavedevsecops.contracts import Commit, RepoState, element_id
from wavedevsecops.engine import (
    OpContext,
    Operation,
    WorkspaceEngine,
    WorkspaceManager,
    load_run,
)
from wavedevsecops.events import Envelope, Kind
from wavedevsecops.gitio import Git
from wavedevsecops.projections import EXPLAIN_REFS
from wavedevsecops.scenarios import (
    STEP_TYPES,
    ScenarioError,
    load_scenario,
    parse_scenario,
    scenario_files,
)
from wavedevsecops.scenarios.steps import StepContext, StepType
from wavedevsecops.scenarios.steps.repo_state import MISSING_FORESEEN_TEXT, Args, check

WAIT = 60.0
ROOT = Path(__file__).resolve().parent.parent

SCENARIO = """\
schema_version: 1
scenario_id: etapes
mode: A
title_text: Scénario d'essai des étapes
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
    explanation_text: Une branche est un pointeur ; HEAD dit laquelle est active.
    explain_ref: graph.branch
    expect:
      head:
        branch: feature
      branches:
        - name: feature
          at: "@premier"
    foreseen:
      - when:
          branches:
            - name: feature
        reason_text: La branche `feature` existe, mais HEAD n'est pas dessus.
  - step_id: commiter
    type: repo_state
    title_text: Faire un commit
    instruction_text: Créez un fichier et commitez-le.
    explanation_text: Un commit fige l'index.
    expect:
      commits:
        - ahead_of: "@origin-main"
          min: 1
      index:
        clean: true
  - step_id: mettre_de_cote
    type: repo_state
    title_text: Mettre de côté
    instruction_text: Modifiez le README puis mettez-le de côté.
    explanation_text: Le stash garde les modifications.
    expect:
      stash:
        min: 1
      tree:
        present: [README.md]
"""


@dataclass
class Box:
    manager: WorkspaceManager
    engine: WorkspaceEngine
    git: Git
    events: list[Envelope]
    settings: Settings
    scenario_path: Path
    clock: int = 1_780_000_000

    @property
    def repo(self) -> Path:
        return self.engine.layout.repo

    def run(self, *args: str, write: dict[str, str] | None = None) -> list[Envelope]:
        """Une commande de l'apprenant passée par la file ; rend les événements qu'elle produit."""
        start = len(self.events)
        self.clock += 60
        env = {
            "GIT_AUTHOR_NAME": "Camille Durand",
            "GIT_AUTHOR_EMAIL": "camille.durand@exemple.test",
            "GIT_COMMITTER_NAME": "Camille Durand",
            "GIT_COMMITTER_EMAIL": "camille.durand@exemple.test",
            "GIT_AUTHOR_DATE": f"@{self.clock} +0000",
            "GIT_COMMITTER_DATE": f"@{self.clock} +0000",
        }

        def body(ctx: OpContext) -> int:
            for rel, text in (write or {}).items():
                (self.repo / rel).write_text(text, encoding="utf-8", newline="\n")
            if args:
                ctx.output(self.git.internal(*args, cwd=self.repo, extra_env=env) or "ok")
            return 0

        self.engine.submit(Operation("terminal_line", body)).result(WAIT)
        return self.events[start:]

    def step_id(self) -> str | None:
        return load_run(self.engine.layout).get("step_id")


def _kinds(events: list[Envelope]) -> list[str]:
    return [e.kind for e in events]


@pytest.fixture
def make_box(tmp_path: Path, git_path: Path) -> Iterator:
    boxes: list[Box] = []
    counter = 0

    def make(track: str = "llm") -> Box:
        nonlocal counter
        counter += 1
        content = tmp_path / f"content{counter}"
        (content / "scenarios").mkdir(parents=True)
        path = content / "scenarios" / "etapes.A.yaml"
        path.write_text(SCENARIO, encoding="utf-8", newline="\n")
        settings = Settings(data_dir=tmp_path / f"data{counter}", content_dir=content)
        manager = WorkspaceManager(settings, git_path=git_path, watch=False)
        loaded = load_scenario(path, settings)
        workspace_id = f"{track}.etapes.A"
        events: list[Envelope] = []
        manager.events(workspace_id).attach(None, events.append)
        engine, setup = manager.create(loaded, track)
        setup.result(WAIT)
        git = Git.for_workspace(git_path, engine.layout.root, settings)
        box = Box(manager, engine, git, events, settings, path)
        boxes.append(box)
        return box

    yield make
    for box in boxes:
        box.manager.close()


# ------------------------------------------------------------------ registre
def test_registre_des_types_d_etape() -> None:
    assert "repo_state" in STEP_TYPES
    spec = STEP_TYPES["repo_state"]
    assert spec.args is Args
    assert spec.check is check
    assert spec.summary


def test_le_moteur_ne_connait_aucun_type_d_etape() -> None:
    """Ajouter un type de test ne modifie ni le moteur ni le chargeur (AD-7)."""
    for folder in ("engine", "events"):
        for path in (ROOT / "src" / "wavedevsecops" / folder).glob("*.py"):
            assert "repo_state" not in path.read_text(encoding="utf-8"), path.name
    loader = ROOT / "src" / "wavedevsecops" / "scenarios" / "loader.py"
    assert "repo_state" not in loader.read_text(encoding="utf-8")


# ------------------------------------------------------- vrai git, bout en bout
@pytest.mark.parametrize("command", [("switch", "-c", "feature"), ("checkout", "-b", "feature")])
def test_etape_reussie_quelle_que_soit_la_commande(make_box, command: tuple[str, ...]) -> None:
    box = make_box()
    events = box.run(*command)
    kinds = _kinds(events)
    # Ordre fixe (AD-1) : sortie, fin, projection, verdict, explication, progression, repos.
    assert kinds == [
        Kind.ENGINE_STATE,
        Kind.OP_STARTED,
        Kind.TERMINAL_OUTPUT,
        Kind.OP_EXIT,
        Kind.STATE_PROJECTED,
        Kind.STEP_VERDICT,
        Kind.STEP_EXPLANATION,
        Kind.PROGRESS_UPDATED,
        Kind.ENGINE_STATE,
    ]
    verdict = next(e for e in events if e.kind == Kind.STEP_VERDICT).payload
    assert verdict["step_id"] == "creer_branche"
    assert verdict["passed"] is True
    assert verdict["status"] == "passed"
    assert verdict["next_step_id"] == "commiter"
    explanation = next(e for e in events if e.kind == Kind.STEP_EXPLANATION).payload
    assert explanation["step_id"] == "creer_branche"
    assert explanation["explain_ref"] == "graph.branch"
    assert explanation["explanation_text"].startswith("Une branche est un pointeur")
    assert box.step_id() == "commiter"
    panel = box.engine.snapshot()["step_panel"]
    assert panel["current_step_id"] == "commiter"
    assert [s["state"] for s in panel["steps"]] == ["done", "current", "todo"]


def test_la_suite_des_etapes_et_la_fin(make_box) -> None:
    box = make_box()
    box.run("switch", "-c", "feature")
    events = box.run("commit", "-q", "--allow-empty", "-m", "Travail")
    assert next(e for e in events if e.kind == Kind.STEP_VERDICT).payload["step_id"] == "commiter"
    box.run(write={"README.md": "# Projet modifié\n"})  # lecture seule pour git, état qui bouge
    events = box.run("stash", "push", "-q")
    verdict = next(e for e in events if e.kind == Kind.STEP_VERDICT).payload
    assert verdict["step_id"] == "mettre_de_cote"
    assert verdict["next_step_id"] == ""
    assert box.step_id() is None
    panel = box.engine.snapshot()["step_panel"]
    assert panel["current_step_id"] == ""
    assert {s["state"] for s in panel["steps"]} == {"done"}
    # Plus d'étape : plus de verdict.
    assert Kind.STEP_VERDICT not in _kinds(box.run("commit", "-q", "--allow-empty", "-m", "Suite"))


def test_etat_prevu_mais_insuffisant(make_box) -> None:
    box = make_box()
    events = box.run("branch", "feature")
    verdict = next(e for e in events if e.kind == Kind.STEP_VERDICT).payload
    assert verdict["status"] == "failed"
    assert verdict["passed"] is False
    assert verdict["reason_text"] == "La branche `feature` existe, mais HEAD n'est pas dessus."
    assert verdict["expected_text"].startswith("Attendu : HEAD sur la branche `feature`")
    assert Kind.STEP_EXPLANATION not in _kinds(events)
    assert box.step_id() == "creer_branche"
    # Quelle que soit la suite de commandes, le dépôt finit par valider.
    events = box.run("switch", "feature")
    assert next(e for e in events if e.kind == Kind.STEP_VERDICT).payload["passed"] is True


def test_etat_inattendu(make_box) -> None:
    box = make_box()
    events = box.run("switch", "-c", "autre")
    verdict = next(e for e in events if e.kind == Kind.STEP_VERDICT).payload
    assert verdict["status"] == "unexpected"
    assert verdict["passed"] is False
    assert "Rien n'est bloqué" in verdict["reason_text"]
    assert "HEAD sur la branche `feature`" in verdict["expected_text"]
    observed = {o["text"]: o["element_id"] for o in verdict["observed"]}
    assert observed["HEAD est sur la branche `autre`."] == element_id("ref", "HEAD")
    assert Kind.STEP_EXPLANATION not in _kinds(events)
    assert _kinds(events).index(Kind.STATE_PROJECTED) < _kinds(events).index(Kind.STEP_VERDICT)
    assert box.step_id() == "creer_branche"  # rien n'est bloqué : l'étape reste ouverte


def test_commande_de_lecture_sans_verdict(make_box) -> None:
    box = make_box()
    assert Kind.STEP_VERDICT not in _kinds(box.run("status"))
    assert Kind.STEP_VERDICT not in _kinds(box.run("log", "--oneline"))


def test_step_id_stable_si_les_etapes_sont_reordonnees(make_box) -> None:
    """La progression cite le `step_id`, pas la position : insérer ou déplacer ne la perd pas."""
    box = make_box()
    box.run("switch", "-c", "feature")
    assert box.step_id() == "commiter"
    text = box.scenario_path.read_text(encoding="utf-8")
    head, _, rest = text.partition("steps:\n")
    blocks = re.split(r"(?m)^(?=  - step_id:)", rest)[1:]
    reordered = head + "steps:\n" + blocks[2] + blocks[0] + blocks[1]
    box.scenario_path.write_text(reordered, encoding="utf-8", newline="\n")
    stamp = box.scenario_path.stat().st_mtime_ns + 10_000_000_000
    os.utime(box.scenario_path, ns=(stamp, stamp))
    panel = box.engine.snapshot()["step_panel"]
    assert panel["current_step_id"] == "commiter"
    assert [s["step_id"] for s in panel["steps"]] == [
        "mettre_de_cote",
        "creer_branche",
        "commiter",
    ]
    # Le verdict suivant concerne bien « commiter ».
    events = box.run("commit", "-q", "--allow-empty", "-m", "Travail")
    assert next(e for e in events if e.kind == Kind.STEP_VERDICT).payload["step_id"] == "commiter"


def test_panneau_ne_devoile_que_les_explications_des_etapes_reussies(make_box) -> None:
    box = make_box()
    panel = box.engine.snapshot()["step_panel"]
    assert panel["title_text"] == "Scénario d'essai des étapes"
    assert panel["mode"] == "A"
    assert panel["mode_text"].startswith("Mode A")
    assert [s["explanation_text"] for s in panel["steps"]] == ["", "", ""]
    assert panel["steps"][0]["instruction_text"].startswith("Créez la branche")
    box.run("switch", "-c", "feature")
    steps = box.engine.snapshot()["step_panel"]["steps"]
    assert steps[0]["explanation_text"] and not steps[1]["explanation_text"]


def test_le_sandbox_sans_etape_n_a_pas_de_panneau(tmp_path: Path, git_path: Path) -> None:
    settings = Settings(data_dir=tmp_path / "data")
    manager = WorkspaceManager(settings, git_path=git_path, watch=False)
    try:
        loaded = load_scenario(
            ROOT / "content" / "scenarios" / "bac-a-sable-libre.A.yaml", settings
        )
        engine, setup = manager.create(loaded, "llm")
        setup.result(WAIT)
        assert engine.snapshot()["step_panel"] is None
    finally:
        manager.close()


# ------------------------------------------------- conditions (états synthétiques)
SHA_A, SHA_B, SHA_C = "a" * 40, "b" * 40, "c" * 40


def _commit(sha: str, parents: list[str], subject: str) -> Commit:
    return Commit(
        sha=sha,
        parents=parents,
        tree="d" * 40,
        author_name="x",
        author_email="x@x",
        author_date="2026-01-01T00:00:00+00:00",
        committer_name="x",
        committer_email="x@x",
        committer_date="2026-01-01T00:00:00+00:00",
        committer_ts=1,
        subject=subject,
        message=subject,
    )


def _state(**kwargs) -> RepoState:
    base = {
        "head": {"detached": False, "ref": "refs/heads/main", "commit": SHA_B},
        "commits": [_commit(SHA_A, [], "un"), _commit(SHA_B, [SHA_A], "Corrige le bug")],
        "refs": [
            {
                "name": "refs/heads/main",
                "kind": "branch",
                "short_name": "main",
                "target": SHA_B,
                "commit": SHA_B,
            },
            {
                "name": "refs/remotes/origin/main",
                "kind": "remote",
                "short_name": "origin/main",
                "target": SHA_A,
                "commit": SHA_A,
            },
            {
                "name": "refs/tags/v1",
                "kind": "tag",
                "short_name": "v1",
                "target": SHA_A,
                "commit": SHA_A,
            },
        ],
        "worktree": ["README.md", "a.txt"],
    }
    return RepoState.model_validate({**base, **kwargs})


def _verdict(expect: dict, state: RepoState, *, previous: RepoState | None = None, aliases=None):
    step = Args.model_validate(
        {
            "step_id": "essai",
            "type": "repo_state",
            "title_text": "T",
            "instruction_text": "I",
            "explanation_text": "E",
            "expect": expect,
        }
    )
    return check(state, StepContext(step, aliases or {}, previous))


def test_conditions_sur_les_refs_et_les_commits() -> None:
    state = _state()
    ok = _verdict(
        {
            "head": {"branch": "main", "at": "main"},
            "branches": [{"name": "main", "at": "HEAD"}, {"name": "absente", "exists": False}],
            "tags": [{"name": "v1", "annotated": False}],
            "commits": [{"ahead_of": "origin/main", "min": 1, "subject_contains": "BUG"}],
        },
        state,
    )
    assert ok.status == "passed"
    bad = _verdict(
        {
            "branches": [{"name": "main", "at": "origin/main"}],
            "tags": [{"name": "v2"}],
            "commits": [{"ahead_of": "main", "min": 1}],
        },
        state,
    )
    assert bad.status == "unexpected"
    texts = {o.text for o in bad.observed}
    assert f"`main` pointe sur `{SHA_B[:7]}`." in texts
    assert "Le tag `v2` n'existe pas." in texts


def test_alias_de_commit_et_de_ref() -> None:
    aliases = {"debut": element_id("commit", SHA_A), "principale": "ref:refs/heads/main"}
    state = _state()
    assert (
        _verdict({"head": {"branch": "@principale", "at": "@principale"}}, state, aliases=aliases)
    ).status == "passed"
    assert (
        _verdict({"commits": [{"ahead_of": "@debut", "min": 1}]}, state, aliases=aliases)
    ).status == "passed"
    assert _verdict({"head": {"at": "@debut"}}, state, aliases=aliases).status == "unexpected"


def test_conditions_sur_l_index_l_arbre_et_le_stash() -> None:
    state = _state(
        status=[
            {"path": "a.txt", "kind": "changed", "index_status": "A", "worktree_status": "M"},
            {"path": "n.txt", "kind": "untracked", "index_status": "?", "worktree_status": "?"},
        ],
        index=[{"path": "a.txt", "mode": "100644", "oid": SHA_C}],
        stash=[{"index": 0, "sha": SHA_C, "message": "On main: ma sauvegarde"}],
        in_progress="merge",
    )
    ok = _verdict(
        {
            "index": {
                "staged": ["a.txt"],
                "unstaged": ["a.txt"],
                "untracked": ["n.txt"],
                "tracked": ["a.txt"],
                "clean": False,
            },
            "tree": {"present": ["README.md"], "absent": ["zzz.txt"]},
            "stash": {"count": 1, "message_contains": "SAUVEGARDE"},
            "in_progress": "merge",
        },
        state,
    )
    assert ok.status == "passed"
    bad = _verdict(
        {
            "index": {"staged": ["n.txt"], "clean": True},
            "tree": {"absent": ["a.txt"]},
            "stash": {"count": 2},
            "in_progress": "",
        },
        state,
    )
    assert bad.status == "unexpected"
    assert "`n.txt` n'est pas indexé." in {o.text for o in bad.observed}
    linked = {o.text: o.element_id for o in bad.observed}["`a.txt` est présent."]
    assert linked == element_id("path", "worktree", "a.txt")


def test_etat_inchange_n_a_rien_a_dire() -> None:
    state = _state()
    assert _verdict({"head": {"branch": "autre"}}, state, previous=state).status == "pending"
    assert _verdict({"head": {"branch": "autre"}}, state).status == "unexpected"


def test_conditions_vides_refusees() -> None:
    with pytest.raises(ValueError, match="au moins une condition"):
        _verdict({}, _state())
    with pytest.raises(ValueError):
        _verdict({"head": {"branche": "x"}}, _state())  # champ inconnu


# ------------------------------------------------------------- lint de contenu
def test_lint_de_contenu_des_scenarios_du_depot() -> None:
    """Charge tous les YAML : ops, types d'étape, outils, clés d'explication, alias, `step_id`."""
    files = scenario_files(Settings())
    assert files
    seen: set[str] = set()
    for path in files:
        loaded = load_scenario(path, Settings(), explain_keys=EXPLAIN_REFS)
        assert loaded.scenario.key not in seen
        seen.add(loaded.scenario.key)
        ids = [s.step_id for s in loaded.scenario.steps]
        assert len(ids) == len(set(ids))
        for step in loaded.scenario.steps:
            assert step.type in STEP_TYPES
        for field, message in loaded.scenario.authoring_warnings():
            warnings.warn(f"{path.name} : {field} : {message}", UserWarning, stacklevel=1)


def _lint_errors(text: str, **kwargs) -> dict[str, str]:
    with pytest.raises(ScenarioError) as info:
        parse_scenario(text, "etapes.A.yaml", explain_keys=EXPLAIN_REFS, **kwargs)
    return {e.field: e.message for e in info.value.errors}


def test_lint_type_d_etape_alias_cle_d_explication_et_step_id() -> None:
    step = (
        "  - step_id: {id}\n    type: {type}\n    title_text: T\n    instruction_text: I\n"
        '    explanation_text: E\n{extra}    expect:\n      head:\n        at: "{at}"\n'
    )
    head = SCENARIO.split("steps:\n")[0] + "steps:\n"
    ok = step.format(id="a", type="repo_state", extra="", at="@premier")
    parse_scenario(head + ok, "etapes.A.yaml", explain_keys=EXPLAIN_REFS)

    unknown = _lint_errors(head + ok.replace("repo_state", "quiz_choix"))
    assert unknown["steps[0].type"].startswith("type d'étape inconnu")

    alias = _lint_errors(head + step.format(id="a", type="repo_state", extra="", at="@absent"))
    assert alias["steps[0].expect.head.at"].startswith("l'alias « @absent »")

    key = _lint_errors(
        head
        + step.format(
            id="a", type="repo_state", extra="    explain_ref: graph.inconnue\n", at="HEAD"
        )
    )
    assert key["steps[0].explain_ref"] == "clé d'explication inconnue : « graph.inconnue »"

    twice = _lint_errors(head + ok + ok)
    assert twice["steps[1].step_id"] == "step_id « a » en double"

    bad_id = _lint_errors(head + step.format(id="Mauvais", type="repo_state", extra="", at="HEAD"))
    assert "steps[0].step_id" in bad_id


# ------------------------------------------------------------------ revue 4.1
def test_lecture_seule_dans_un_etat_prevu_ne_republie_rien(make_box) -> None:
    box = make_box()
    events = box.run("branch", "feature")
    assert next(e for e in events if e.kind == Kind.STEP_VERDICT).payload["status"] == "failed"
    assert Kind.STEP_VERDICT not in _kinds(box.run("status"))
    assert Kind.STEP_VERDICT not in _kinds(box.run("log", "--oneline"))


def test_reference_introuvable_echoue_ferme() -> None:
    state = _state()
    for expect in (
        {"commits": [{"ahead_of": "supprimee", "min": 1}]},
        {"commits": [{"ahead_of": "@absent", "min": 1}]},
        {"commits": [{"on": "@absent", "min": 0}]},
        {"head": {"at": "@absent"}},
        {"branches": [{"name": "@absent"}]},
    ):
        verdict = _verdict(expect, state, aliases={})
        assert verdict.status == "unexpected", expect
    texts = {o.text for o in _verdict({"commits": [{"ahead_of": "supprimee"}]}, state).observed}
    assert texts == {"`supprimee` est introuvable dans le dépôt."}


def test_depot_illisible_rien_a_dire() -> None:
    step = Args.model_validate(
        {
            "step_id": "essai",
            "type": "repo_state",
            "title_text": "T",
            "instruction_text": "I",
            "explanation_text": "E",
            "expect": {"head": {"branch": "main"}},
        }
    )
    assert check(None, StepContext(step)).status == "pending"


def test_un_type_recoit_l_intention_et_les_vues(make_box, monkeypatch) -> None:
    """Un type qui ne juge pas le dépôt (quiz, désignation) lit l'opération : le moteur ne
    change pas."""
    seen: list[tuple] = []
    real = STEP_TYPES["repo_state"]

    def spy(state, ctx):
        seen.append((state is not None, ctx.intent, sorted(ctx.views), dict(ctx.data)))
        return real.check(state, ctx)

    monkeypatch.setitem(
        STEP_TYPES, "repo_state", StepType("repo_state", real.args, spy, real.summary)
    )
    box = make_box()

    def body(ctx: OpContext) -> int:
        ctx.data["answer"] = "b"
        return 0

    box.engine.submit(Operation("quiz_answer", body)).result(WAIT)
    assert seen == [
        (True, "quiz_answer", sorted(box.engine.last_projection.views), {"answer": "b"})
    ]


def test_scenario_devenu_invalide_ne_fait_pas_d_erreur(make_box) -> None:
    box = make_box()
    box.scenario_path.write_text("schema_version: [", encoding="utf-8")
    stamp = box.scenario_path.stat().st_mtime_ns + 10_000_000_000
    os.utime(box.scenario_path, ns=(stamp, stamp))
    kinds = _kinds(box.run("switch", "-c", "feature"))
    assert Kind.APP_ERROR not in kinds
    assert Kind.STEP_VERDICT not in kinds
    assert box.engine.snapshot()["step_panel"] is None


def test_lint_avertit_d_une_etape_sans_etat_prevu() -> None:
    loaded = parse_scenario(SCENARIO, "etapes.A.yaml")
    warned = loaded.authoring_warnings()
    assert warned == [
        (("steps", 1, "foreseen"), MISSING_FORESEEN_TEXT),
        (("steps", 2, "foreseen"), MISSING_FORESEEN_TEXT),
    ]


def test_type_absent_d_une_etape_nomme_le_champ_type() -> None:
    text = SCENARIO.replace("    type: repo_state\n", "", 1)
    errors = _lint_errors(text)
    # Un seul type : pydantic signale le champ ; à plusieurs, `union_tag_not_found` le nomme.
    assert errors == {"steps[0].type": "champ obligatoire absent"}
    from wavedevsecops.scenarios.loader import french_message

    assert french_message({"type": "union_tag_not_found", "loc": ("steps", 0)}) == (
        "champ `type` absent"
    )
    assert french_message({"type": "union_tag_not_found", "loc": ("setup", 0)}) == (
        "champ `op` absent"
    )
