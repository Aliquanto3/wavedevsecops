"""Story 3.4 : commits et revues du collègue simulé, sur un vrai git (AD-3, AD-7, AD-8)."""

from __future__ import annotations

from pathlib import Path

import pytest
from test_github_sim import BASE

from wavedevsecops import github_sim
from wavedevsecops.config import Settings
from wavedevsecops.contracts.github import Review
from wavedevsecops.engine import prepare_workspace
from wavedevsecops.gitio import Git
from wavedevsecops.projections import ACTORS, project
from wavedevsecops.scenarios import LoadedScenario, parse_scenario
from wavedevsecops.scenarios.loader import ScenarioError

COLLEAGUE_COMMIT = """\
  - op: colleague_commit
    branch: main
    files:
      - {path: notes.md, content: "Relu par Sacha.\\n"}
    message: Ajoute des notes
    date: "2026-01-06T10:00:00+00:00"
    as: sacha
"""

FIXED_SHA = "91e9894655c2e05cda942a8b68ddfcef1ae739c7"
"""Empreinte de référence du commit du collègue : identique sur Windows, macOS et Linux."""

REACTIONS = """\
  - op: colleague_reaction
    trigger: pr_opened
    reviews:
      - {state: commented, body_text: "Merci pour la PR, je regarde."}
      - {state: approved, body_text: "C'est bon pour moi."}
  - op: colleague_reaction
    trigger: checks_green
    head: feature
    reviews:
      - {state: approved, body_text: "Checks verts, je valide."}
"""


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(data_dir=tmp_path / "data")


def _prepare(settings: Settings, git_path: Path, extra: str = ""):
    text = BASE.format(feature_path="autre.py") + extra
    loaded = LoadedScenario(parse_scenario(text, "essai.A.yaml"), Path("essai.A.yaml"), "0" * 64)
    prepared = prepare_workspace(loaded, "llm", settings=settings, git_path=git_path)
    return prepared, Git.for_workspace(git_path, prepared.layout.root, settings)


def _origin(git: Git, layout, *args: str) -> str:
    return git.internal(*args, cwd=layout.origin).strip()


def test_commit_du_collegue_sur_origin_sans_toucher_au_local(
    settings: Settings, git_path: Path
) -> None:
    prepared, git = _prepare(settings, git_path, COLLEAGUE_COMMIT)
    layout = prepared.layout
    sha = prepared.aliases["sacha"].removeprefix("commit:")
    assert _origin(git, layout, "rev-parse", "main") == sha
    assert not (layout.repo / "notes.md").exists()
    fmt = "%an|%ae|%cn|%aI|%cI|%s|%P"
    author, email, committer, adate, cdate, subject, parents = _origin(
        git, layout, "log", "-1", f"--format={fmt}", "main"
    ).split("|")
    assert (author, committer) == ("Sacha Martin", "Sacha Martin")
    assert email == "sacha.martin@exemple.test"
    assert adate == cdate == "2026-01-06T10:00:00Z"
    assert subject == "Ajoute des notes"
    assert len(parents.split()) == 1  # le commit prolonge main
    assert _origin(git, layout, "show", "main:notes.md") == "Relu par Sacha."
    assert _origin(git, layout, "show", "main:app.py") == "valeur = 1"  # arbre précédent gardé


def test_pull_apporte_le_commit_avec_le_badge_collegue(settings: Settings, git_path: Path) -> None:
    prepared, git = _prepare(settings, git_path, COLLEAGUE_COMMIT)
    layout = prepared.layout
    git.internal("pull", "-q", "--ff-only", cwd=layout.repo)
    assert (layout.repo / "notes.md").read_text(encoding="utf-8") == "Relu par Sacha.\n"
    views = project(git, layout).views
    actors = {n.subject: n.actor for n in views.graph.nodes}
    assert actors["Ajoute des notes"] == "colleague"
    assert actors["Premier commit"] == "learner"
    assert ACTORS["sacha.martin@exemple.test"] == "colleague"


def test_sha_du_commit_du_collegue_stable_sur_les_trois_os(
    settings: Settings, git_path: Path
) -> None:
    prepared, _ = _prepare(settings, git_path, COLLEAGUE_COMMIT)
    assert prepared.aliases["sacha"] == f"commit:{FIXED_SHA}"


def test_commit_du_collegue_sur_nouvelle_branche_et_racine(
    settings: Settings, git_path: Path
) -> None:
    extra = """\
  - op: colleague_commit
    branch: hotfix
    start: main
    files: [{path: fix.txt, content: "ok\\n"}]
    message: Correctif
  - op: colleague_commit
    branch: orpheline
    files: [{path: seul.txt, content: "x\\n"}]
    message: Racine
"""
    prepared, git = _prepare(settings, git_path, extra)
    layout = prepared.layout
    main = _origin(git, layout, "rev-parse", "main")
    assert _origin(git, layout, "rev-parse", "hotfix^") == main
    assert _origin(git, layout, "show", "hotfix:app.py") == "valeur = 1"
    assert _origin(git, layout, "log", "-1", "--format=%P", "orpheline") == ""


def test_start_absent_d_origin_refuse(settings: Settings, git_path: Path) -> None:
    extra = """\
  - op: colleague_commit
    branch: hotfix
    start: nulle-part
    files: [{path: fix.txt, content: "ok\\n"}]
    message: Correctif
"""
    with pytest.raises(Exception, match="nulle-part"):
        _prepare(settings, git_path, extra)


def test_chemin_hors_depot_ou_en_double_refuse() -> None:
    bad = """\
schema_version: 1
scenario_id: essai
mode: A
title_text: Essai
tracks: [llm]
setup:
  - op: colleague_commit
    files: [{path: ../dehors, content: x}]
    message: m
"""
    with pytest.raises(ScenarioError):
        parse_scenario(bad, "essai.A.yaml")
    dup = bad.replace("../dehors", "a.txt").replace(
        "[{path: a.txt, content: x}]", "[{path: a.txt, content: x}, {path: a.txt, content: y}]"
    )
    with pytest.raises(ScenarioError):
        parse_scenario(dup, "essai.A.yaml")


def test_reaction_a_l_ouverture_commentaire_puis_approbation_dans_l_ordre(
    settings: Settings, git_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    times = iter(f"2026-01-06T10:00:0{n}.000+00:00" for n in range(9))
    monkeypatch.setattr(github_sim, "now_iso", lambda: next(times))
    extra = (
        REACTIONS.split("  - op: colleague_reaction\n    trigger: checks_green")[0]
        + """\
  - op: set_protection
    branch: main
    required_approvals: 1
  - op: open_pr
    head: feature
    as: pr
"""
    )
    prepared, git = _prepare(settings, git_path, extra)
    pr = github_sim.load(prepared.layout).pull(1)
    assert pr is not None
    assert [(r.review_id, r.author, r.state) for r in pr.reviews] == [
        (1, "Sacha Martin", "commented"),
        (2, "Sacha Martin", "approved"),
    ]
    assert [r.created_at for r in pr.reviews] == [
        "2026-01-06T10:00:00.000+00:00",
        "2026-01-06T10:00:01.000+00:00",
    ]
    assert all(r.commit_sha == pr.head_sha for r in pr.reviews)
    assert pr.reviews[0].body_text == "Merci pour la PR, je regarde."
    assert pr.approvals == 1 and pr.mergeable


def test_reaction_a_l_ouverture_ne_rejoue_pas_et_respecte_head(
    settings: Settings, git_path: Path
) -> None:
    extra = """\
  - op: colleague_reaction
    trigger: pr_opened
    head: autre-branche
    reviews: [{state: approved}]
  - op: open_pr
    head: feature
"""
    prepared, git = _prepare(settings, git_path, extra)
    layout = prepared.layout
    pr = github_sim.load(layout).pull(1)
    assert pr is not None and pr.reviews == []
    github_sim.refresh(git, layout)
    github_sim.refresh(git, layout)
    again = github_sim.load(layout).pull(1)
    assert again is not None and again.reviews == []


def test_approbation_automatique_quand_les_checks_obligatoires_passent(
    settings: Settings, git_path: Path
) -> None:
    extra = (
        "  - op: colleague_reaction\n    trigger: checks_green\n"
        "    reviews: [{state: approved, body_text: Checks verts}]\n"
        """\
  - op: set_protection
    branch: main
    required_approvals: 1
    required_checks: [tests, lint]
  - op: open_pr
    head: feature
"""
    )
    prepared, git = _prepare(settings, git_path, extra)
    layout = prepared.layout
    pr = github_sim.set_check_state(git, layout, 1, "tests", "success")
    assert pr.reviews == [] and not pr.mergeable  # lint n'est pas encore vert
    pr = github_sim.set_check_state(git, layout, 1, "lint", "success")
    assert [(r.state, r.author, r.body_text) for r in pr.reviews] == [
        ("approved", "Sacha Martin", "Checks verts")
    ]
    assert pr.approvals == 1 and pr.mergeable and pr.blocking_reasons == []
    # Rien de plus tant que le head_sha ne change pas.
    pr = github_sim.set_check_state(git, layout, 1, "lint", "success")
    assert len(pr.reviews) == 1
    # Un nouveau push remet les checks à queued et réarme la réaction.
    sha = _origin(git, layout, "rev-parse", "feature")
    git.internal("switch", "-q", "feature", cwd=layout.repo)
    (layout.repo / "plus.py").write_text("x = 1\n", encoding="utf-8")
    git.internal("add", "-A", cwd=layout.repo)
    env = {
        "GIT_AUTHOR_NAME": "t",
        "GIT_AUTHOR_EMAIL": "t@exemple.test",
        "GIT_COMMITTER_NAME": "t",
        "GIT_COMMITTER_EMAIL": "t@exemple.test",
    }
    git.internal("commit", "-q", "-m", "suite", cwd=layout.repo, extra_env=env)
    git.internal("push", "-q", "--no-verify", "origin", "feature", cwd=layout.repo)
    refreshed = github_sim.refresh(git, layout)
    assert refreshed.sha_changed == [1]
    pr = github_sim.load(layout).pull(1)
    assert pr is not None and pr.head_sha != sha and len(pr.reviews) == 1
    github_sim.set_check_state(git, layout, 1, "tests", "success")
    pr = github_sim.set_check_state(git, layout, 1, "lint", "success")
    assert len(pr.reviews) == 2 and isinstance(pr.reviews[1], Review)


def test_pas_d_approbation_sans_check_obligatoire_ni_check_en_echec(
    settings: Settings, git_path: Path
) -> None:
    extra = (
        "  - op: colleague_reaction\n    trigger: checks_green\n    reviews: [{state: approved}]\n"
        """\
  - op: open_pr
    head: feature
    checks:
      - {job_id: tests, state: queued, required: true}
"""
    )
    prepared, git = _prepare(settings, git_path, extra)
    layout = prepared.layout
    pr = github_sim.set_check_state(git, layout, 1, "tests", "failure")
    assert pr.reviews == []
    with pytest.raises(github_sim.GithubSimError, match="check « absent »"):
        github_sim.set_check_state(git, layout, 1, "absent", "success")


def test_empreinte_inchangee_par_l_heure_des_revues(
    settings: Settings, git_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    extra = (
        REACTIONS.split("  - op: colleague_reaction\n    trigger: checks_green")[0]
        + "  - op: open_pr\n    head: feature\n"
    )
    monkeypatch.setattr(github_sim, "now_iso", lambda: "2026-01-06T10:00:00.000+00:00")
    first, _ = _prepare(settings, git_path, extra)
    one = github_sim.canonical_digest(first.layout)
    monkeypatch.setattr(github_sim, "now_iso", lambda: "2027-05-05T05:05:05.000+00:00")
    second, _ = _prepare(Settings(data_dir=settings.data_dir / "bis"), git_path, extra)
    assert github_sim.canonical_digest(second.layout) == one


def test_empreinte_d_un_github_json_d_avant_la_3_4_inchangee(tmp_path: Path) -> None:
    """Un `github.json` sans `reactions` (écrit avant la story) garde son empreinte de référence."""
    from types import SimpleNamespace

    path = tmp_path / "github.json"
    path.write_text('{"schema_version": 1, "next_number": 1, "protections": [], "pulls": []}')
    layout = SimpleNamespace(github_json=path)
    reference = "229bf5c60bc1744d3720ae73bf4ad9a2c4ea1f75b51bc4f7bbf5f767efa42c9a"
    assert github_sim.canonical_digest(layout) == reference  # type: ignore[arg-type]
