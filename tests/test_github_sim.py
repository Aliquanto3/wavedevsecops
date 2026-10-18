"""GitHub simulé : modèle de PR, checks liés au SHA, `mergeable` (AD-8, AD-20), par le vrai git."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from wavedevsecops import github_sim
from wavedevsecops.config import Settings
from wavedevsecops.contracts import element_id
from wavedevsecops.contracts.github import (
    BranchProtection,
    Check,
    GithubState,
    PullRequest,
    Review,
)
from wavedevsecops.engine import fingerprint, prepare_workspace
from wavedevsecops.gitio import Git
from wavedevsecops.scenarios import LoadedScenario, parse_scenario
from wavedevsecops.scenarios.context import PERSONAS

BASE = """\
schema_version: 1
scenario_id: essai
mode: A
title_text: Essai
tracks: [llm]
setup:
  - op: write_file
    path: app.py
    content: "valeur = 1\\n"
  - op: commit
    message: Premier commit
  - op: push
    branch: main
  - op: switch
    branch: feature
    create: true
  - op: write_file
    path: {feature_path}
    content: "valeur = 2\\n"
  - op: commit
    message: Change la valeur
  - op: push
    as: feature
  - op: switch
    branch: main
"""


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(data_dir=tmp_path / "data")


def _prepare(settings: Settings, git_path: Path, extra: str = "", feature_path: str = "app.py"):
    text = BASE.format(feature_path=feature_path) + extra
    loaded = LoadedScenario(parse_scenario(text, "essai.A.yaml"), Path("essai.A.yaml"), "0" * 64)
    prepared = prepare_workspace(loaded, "llm", settings=settings, git_path=git_path)
    git = Git.for_workspace(git_path, prepared.layout.root, settings)
    return prepared, git


def _sha(git: Git, layout, ref: str) -> str:
    return git.internal("rev-parse", ref, cwd=layout.origin).strip()


def _commit_and_push(git: Git, layout, branch: str, path: str, content: str) -> None:
    repo = layout.repo
    git.internal("switch", "-q", branch, cwd=repo)
    (repo / path).write_text(content, encoding="utf-8")
    env = {
        "GIT_AUTHOR_NAME": "t",
        "GIT_AUTHOR_EMAIL": "t@exemple.test",
        "GIT_COMMITTER_NAME": "t",
        "GIT_COMMITTER_EMAIL": "t@exemple.test",
    }
    git.internal("commit", "-q", "-a", "-m", "suite", cwd=repo, extra_env=env)
    git.internal("push", "-q", "--no-verify", "origin", branch, cwd=repo)


def test_le_modele_porte_tous_les_champs_d_ad8() -> None:
    assert {
        "number",
        "head",
        "base",
        "state",
        "head_sha",
        "base_sha",
        "checks",
        "reviews",
        "required_approvals",
        "protection",
        "mergeable",
        "blocking_reasons",
    } <= set(PullRequest.model_fields)
    assert {"job_id", "head_sha", "base_sha", "state", "required", "output", "findings"} <= set(
        Check.model_fields
    )
    states = Check.model_fields["state"].annotation.__args__
    assert set(states) == {"queued", "running", "success", "failure", "error"}


def test_setup_ecrit_un_github_json_vide_et_versionne(settings: Settings, git_path: Path) -> None:
    prepared, _ = _prepare(settings, git_path)
    raw = prepared.layout.github_json.read_bytes()
    assert b"\r" not in raw and raw.endswith(b"\n")
    data = json.loads(raw)
    assert data == {
        "next_number": 1,
        "protections": [],
        "pulls": [],
        "reactions": [],
        "schema_version": 1,
    }
    assert list(data) == sorted(data)


def test_ouvrir_des_pr_numerotees_depuis_1(settings: Settings, git_path: Path) -> None:
    extra = """\
  - op: set_protection
    branch: main
    required_approvals: 1
    required_checks: [tests]
  - op: open_pr
    head: "@feature"
    title_text: Change la valeur
    checks:
      - {job_id: lint, state: success, output: "Tout va bien."}
    as: pr
"""
    prepared, git = _prepare(settings, git_path, extra)
    layout = prepared.layout
    assert prepared.aliases["pr"] == "pr:1"
    state = github_sim.load(layout)
    pr = state.pull(1)
    assert pr is not None and state.next_number == 2
    head, base = _sha(git, layout, "feature"), _sha(git, layout, "main")
    assert (pr.head, pr.base, pr.state) == ("feature", "main", "open")
    assert (pr.head_sha, pr.base_sha) == (head, base)
    assert pr.required_approvals == 1 and pr.protection is not None
    assert pr.protection.required_checks == ["tests"]
    checks = {c.job_id: c for c in pr.checks}
    assert checks["lint"].state == "success" and not checks["lint"].required
    assert checks["tests"].state == "queued" and checks["tests"].required
    assert (checks["tests"].head_sha, checks["tests"].base_sha) == (head, base)
    assert not pr.mergeable
    reasons = {r.kind: r for r in pr.blocking_reasons}
    assert set(reasons) == {"check", "approvals"}
    assert reasons["check"].element_id == element_id("check", "1", "tests", head)
    assert "tests" in reasons["check"].text
    assert reasons["approvals"].element_id == "pr:1"
    assert "0 sur 1" in reasons["approvals"].text

    git.internal("branch", "-q", "autre", "main", cwd=layout.repo)
    git.internal("push", "-q", "--no-verify", "origin", "autre", cwd=layout.repo)
    second = github_sim.open_pr(git, layout, "autre", "main")
    assert second.number == 2 and github_sim.load(layout).next_number == 3
    with pytest.raises(github_sim.GithubSimError, match="déjà ouverte"):
        github_sim.open_pr(git, layout, "feature", "main")


def test_branche_absente_d_origin_refusee(settings: Settings, git_path: Path) -> None:
    prepared, git = _prepare(settings, git_path)
    git.internal("branch", "-q", "locale", cwd=prepared.layout.repo)
    with pytest.raises(github_sim.GithubSimError) as caught:
        github_sim.open_pr(git, prepared.layout, "locale")
    assert "Poussez d'abord" in caught.value.action_text


@pytest.mark.parametrize(
    ("state", "mergeable", "words"),
    [("failure", False, "a échoué"), ("error", False, "erreur"), ("success", True, "")],
)
def test_check_obligatoire_declare_par_le_scenario(
    settings: Settings, git_path: Path, state: str, mergeable: bool, words: str
) -> None:
    extra = f"""\
  - op: open_pr
    head: feature
    checks:
      - {{job_id: tests, state: {state}, required: true}}
"""
    prepared, git = _prepare(settings, git_path, extra, feature_path="autre.py")
    pr = github_sim.load(prepared.layout).pull(1)
    assert pr is not None and pr.mergeable is mergeable
    if mergeable:
        assert pr.blocking_reasons == []
    else:
        [reason] = pr.blocking_reasons
        assert reason.kind == "check" and words in reason.text
        assert reason.element_id == element_id("check", "1", "tests", pr.head_sha)


def test_nouveau_sha_remet_les_checks_en_queued(settings: Settings, git_path: Path) -> None:
    extra = """\
  - op: open_pr
    head: feature
    checks:
      - {job_id: tests, state: success, required: true, output: "3 passed"}
"""
    prepared, git = _prepare(settings, git_path, extra, feature_path="autre.py")
    layout = prepared.layout
    assert github_sim.load(layout).pulls[0].mergeable

    _commit_and_push(git, layout, "feature", "autre.py", "valeur = 3\n")
    result = github_sim.refresh(git, layout)
    assert result.sha_changed == [1] and result.updated == [1]
    pr = github_sim.load(layout).pulls[0]
    [check] = pr.checks
    assert pr.head_sha == _sha(git, layout, "feature")
    assert (check.state, check.head_sha, check.base_sha) == ("queued", pr.head_sha, pr.base_sha)
    assert check.output == "" and not pr.mergeable

    before = layout.github_json.read_bytes()
    again = github_sim.refresh(git, layout)
    assert again.sha_changed == [] and again.updated == []
    assert layout.github_json.read_bytes() == before

    _commit_and_push(git, layout, "main", "app.py", "valeur = 9\n")
    result = github_sim.refresh(git, layout)
    assert result.sha_changed == [1]
    pr = github_sim.load(layout).pulls[0]
    assert pr.base_sha == _sha(git, layout, "main") == pr.checks[0].base_sha


def test_un_vieux_succes_ne_compte_pas(git_path: Path) -> None:
    sha_a, sha_b, base = "a" * 40, "b" * 40, "c" * 40
    pr = PullRequest(
        number=4,
        head="feature",
        base="main",
        head_sha=sha_b,
        base_sha=base,
        checks=[
            Check(job_id="tests", head_sha=sha_a, base_sha=base, state="success", required=True)
        ],
    )
    new, changed = github_sim.evaluate(pr, None, {"feature": sha_b, "main": base}, lambda *_: False)
    assert not changed and not new.mergeable
    assert "ancien commit" in new.blocking_reasons[0].text


def test_conflit_detecte_par_merge_tree(settings: Settings, git_path: Path) -> None:
    extra = """\
  - op: write_file
    path: app.py
    content: "valeur = 5\\n"
  - op: commit
    message: Change aussi la valeur
  - op: push
    branch: main
  - op: open_pr
    head: feature
"""
    prepared, git = _prepare(settings, git_path, extra)
    pr = github_sim.load(prepared.layout).pull(1)
    assert pr is not None and not pr.mergeable
    [reason] = pr.blocking_reasons
    assert reason.kind == "conflict" and reason.element_id == "pr:1"
    assert "en conflit" in reason.text
    assert not github_sim.has_conflict(git, prepared.layout, pr.base_sha, pr.base_sha)

    env = {"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@exemple.test"}
    env |= {"GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@exemple.test"}
    tree = f"{pr.base_sha}^{{tree}}"
    orphan = git.internal(
        "commit-tree", tree, "-m", "sans parent", cwd=prepared.layout.origin, extra_env=env
    ).strip()
    assert github_sim.has_conflict(git, prepared.layout, pr.base_sha, orphan)


def test_approbations_et_branche_disparue(settings: Settings, git_path: Path) -> None:
    extra = """\
  - op: set_protection
    required_approvals: 1
  - op: open_pr
    head: feature
    reviews:
      - {state: approved, body_text: "Parfait."}
"""
    prepared, git = _prepare(settings, git_path, extra, feature_path="autre.py")
    layout = prepared.layout
    pr = github_sim.load(layout).pull(1)
    assert pr is not None and pr.mergeable and pr.approvals == 1
    assert json.loads(layout.github_json.read_text())["pulls"][0]["approvals"] == 1
    assert pr.reviews[0].author == PERSONAS["colleague"].name
    assert pr.reviews[0].element(1) == "review:1:1"

    git.internal("push", "-q", "--no-verify", "origin", ":feature", cwd=layout.repo)
    github_sim.refresh(git, layout)
    pr = github_sim.load(layout).pull(1)
    assert pr is not None and not pr.mergeable
    assert [r.kind for r in pr.blocking_reasons] == ["head_missing"]
    assert pr.blocking_reasons[0].element_id == "ref:refs/remotes/origin/feature"


def test_la_derniere_revue_de_chaque_auteur_fait_foi() -> None:
    sha = "a" * 40
    reviews = [
        Review(review_id=1, author="Sacha", state="approved", commit_sha=sha),
        Review(review_id=2, author="Sacha", state="changes_requested", commit_sha=sha),
        Review(review_id=3, author="Agent", state="approved", commit_sha=sha),
        Review(review_id=4, author="Agent", state="commented", commit_sha=sha),
    ]
    pr = PullRequest(number=1, head="f", base="main", head_sha=sha, base_sha=sha, reviews=reviews)
    assert pr.count_approvals() == 1


def test_empreinte_sans_sortie_ni_duree(settings: Settings, git_path: Path) -> None:
    extra = """\
  - op: open_pr
    head: feature
    checks:
      - {job_id: tests, state: failure, output: "1 failed"}
"""
    prepared, git = _prepare(settings, git_path, extra, feature_path="autre.py")
    layout = prepared.layout
    digest = github_sim.canonical_digest(layout)
    assert digest is not None and fingerprint(layout, git) == prepared.fingerprint

    data = json.loads(layout.github_json.read_bytes())
    data["pulls"][0]["checks"][0] |= {
        "output": "autre sortie",
        "duration_ms": 1234,
        "updated_at": "2026-10-18T10:00:00+00:00",
    }
    layout.github_json.write_text(json.dumps(data), encoding="utf-8")
    assert github_sim.canonical_digest(layout) == digest
    assert fingerprint(layout, git) == prepared.fingerprint

    data["pulls"][0]["checks"][0]["state"] = "success"
    layout.github_json.write_text(json.dumps(data), encoding="utf-8")
    assert github_sim.canonical_digest(layout) != digest
    assert fingerprint(layout, git) != prepared.fingerprint


def test_version_future_ou_fichier_illisible(settings: Settings, git_path: Path) -> None:
    prepared, _ = _prepare(settings, git_path)
    layout = prepared.layout
    layout.github_json.write_text('{"schema_version": 2}', encoding="utf-8")
    with pytest.raises(github_sim.GithubSimError, match="plus récente"):
        github_sim.load(layout)
    layout.github_json.write_text("{pas du json", encoding="utf-8")
    with pytest.raises(github_sim.GithubSimError, match="illisible"):
        github_sim.load(layout)
    layout.github_json.unlink()
    assert github_sim.load(layout) == GithubState()
    assert github_sim.canonical_digest(layout) is None


def test_migrations_appliquees_au_chargement(
    settings: Settings, git_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    prepared, _ = _prepare(settings, git_path)
    layout = prepared.layout
    monkeypatch.setattr(github_sim, "GITHUB_SCHEMA_VERSION", 2)
    monkeypatch.setitem(github_sim.MIGRATIONS, 1, lambda d: {**d, "ajout": True})
    assert github_sim._read_raw(layout) == {
        "next_number": 1,
        "protections": [],
        "pulls": [],
        "reactions": [],
        "schema_version": 2,
        "ajout": True,
    }


def _pr(**update) -> PullRequest:
    fields = {"head_sha": "a" * 40, "base_sha": "a" * 40} | update
    return PullRequest(number=2, head="feature", base="main", **fields)


def test_fusion_incalculable_bloque_la_pr_sans_planter() -> None:
    sha = "a" * 40
    new, _ = github_sim.evaluate(_pr(), None, {"feature": sha, "main": sha}, lambda *_: None)
    assert not new.mergeable
    [reason] = new.blocking_reasons
    assert reason.kind == "conflict" and "pas pu calculer" in reason.text


def test_revues_perimees_ecartees_si_la_protection_le_demande() -> None:
    old, new_sha, base = "a" * 40, "b" * 40, "c" * 40
    review = Review(review_id=1, author="Sacha", state="approved", commit_sha=old)
    pr = _pr(head_sha=old, base_sha=base, reviews=[review])
    branches = {"feature": new_sha, "main": base}
    keep = BranchProtection(branch="main", required_approvals=1)
    new, _ = github_sim.evaluate(pr, keep, branches, lambda *_: False)
    assert new.mergeable and new.approvals == 1
    dismiss = keep.model_copy(update={"dismiss_stale_reviews": True})
    new, _ = github_sim.evaluate(pr, dismiss, branches, lambda *_: False)
    assert not new.mergeable and new.approvals == 0
    assert [r.kind for r in new.blocking_reasons] == ["approvals"]


def test_ops_refusent_job_id_invalide_ou_en_double() -> None:
    from pydantic import ValidationError

    from wavedevsecops.scenarios.ops import open_pr, set_protection

    with pytest.raises(ValidationError):
        set_protection.Args(op="set_protection", required_checks=["build\n"])
    with pytest.raises(ValidationError):
        open_pr.Args(op="open_pr", head="feature", checks=[{"job_id": "t"}, {"job_id": "t"}])


def test_refresh_sans_github_json_n_ecrit_rien(settings: Settings, git_path: Path) -> None:
    prepared, git = _prepare(settings, git_path)
    layout = prepared.layout
    layout.github_json.unlink()
    assert github_sim.refresh(git, layout).updated == []
    assert not layout.github_json.exists()
    with pytest.raises(github_sim.GithubSimError, match="même check"):
        github_sim.open_pr(
            git,
            layout,
            "feature",
            checks=[github_sim.DeclaredCheck("tests"), github_sim.DeclaredCheck("tests")],
        )


def test_changement_externe_recalcule_les_pr(settings: Settings, git_path: Path) -> None:
    from types import SimpleNamespace

    from wavedevsecops.engine.manager import github_refresher

    extra = """\
  - op: open_pr
    head: feature
    checks:
      - {job_id: tests, state: success, required: true}
"""
    prepared, git = _prepare(settings, git_path, extra, feature_path="autre.py")
    layout = prepared.layout
    refresh = github_refresher(settings, git_path)
    ctx = SimpleNamespace(layout=layout)
    assert refresh(ctx) is None  # type: ignore[arg-type]

    _commit_and_push(git, layout, "feature", "autre.py", "valeur = 3\n")
    assert refresh(ctx) == fingerprint(layout, git)  # type: ignore[arg-type]
    pr = github_sim.load(layout).pulls[0]
    assert pr.checks[0].state == "queued" and not pr.mergeable
