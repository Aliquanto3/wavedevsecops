"""Story 5.1 : actes de l'agent B rejoués de façon déterministe, sur un vrai git (AD-3, AD-7)."""

from __future__ import annotations

from pathlib import Path

import pytest
from test_github_sim import BASE

from wavedevsecops.config import Settings
from wavedevsecops.engine import prepare_workspace
from wavedevsecops.gitio import Git
from wavedevsecops.projections import ACTORS, project, read_repo_state
from wavedevsecops.scenarios import LoadedScenario, parse_scenario

AGENT_COMMIT = """\
  - op: agent_commit
    files: [{path: app.py, content: "valeur = 3\\n"}]
    message: Simplifie la valeur
    date: "2026-01-06T10:00:00+00:00"
    as: agent-fix
"""

PUSH_FORCE = """\
  - op: push
    branch: main
  - op: agent_push_force
    branch: main
    parent: "main~1"
    files: [{path: app.py, content: "valeur = 4\\n"}]
    message: Réécrit main
    date: "2026-01-06T11:00:00+00:00"
"""

STASH = """\
  - op: stash
    files: [{path: brouillon.txt, content: "à revoir\\n"}]
    message: Brouillon de l'agent
    date: "2026-01-06T12:00:00+00:00"
    as: mis-de-cote
"""

REBASE = """\
  - op: switch
    branch: feature
  - op: agent_rebase_conflict
    onto: main
    date: "2026-01-06T13:00:00+00:00"
"""

COMPLET = AGENT_COMMIT + PUSH_FORCE + STASH + REBASE

AGENT_SHA = "031f2236efd40efcb9d24c89b4e89c18e2e63d8b"
"""SHA de référence du commit de l'agent : identique sur Windows, macOS et Linux."""
STASH_SHA = "be4075356bdc3b0fa10cf66213f007c423bd8c43"
FINGERPRINT = "d99a0e2fc0d4cca98de7d2faea5dfd95f588a1918fc7f5f69844684e007f5f42"
"""Empreinte de référence de l'espace après `COMPLET` : identique sur les trois systèmes."""


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(data_dir=tmp_path / "data")


def _prepare(settings: Settings, git_path: Path, extra: str, feature: str = "app.py"):
    text = BASE.format(feature_path=feature) + extra
    loaded = LoadedScenario(parse_scenario(text, "essai.B.yaml"), Path("essai.B.yaml"), "0" * 64)
    prepared = prepare_workspace(loaded, "llm", settings=settings, git_path=git_path)
    return prepared, Git.for_workspace(git_path, prepared.layout.root, settings)


def _repo(git: Git, layout, *args: str) -> str:
    return git.internal(*args, cwd=layout.repo).strip()


def _origin(git: Git, layout, *args: str) -> str:
    return git.internal(*args, cwd=layout.origin).strip()


@pytest.mark.slow
def test_agent_commit_identite_date_et_fichiers(settings: Settings, git_path: Path) -> None:
    prepared, git = _prepare(settings, git_path, AGENT_COMMIT)
    layout = prepared.layout
    sha = prepared.aliases["agent-fix"].removeprefix("commit:")
    assert _repo(git, layout, "rev-parse", "HEAD") == sha
    fmt = "%an|%ae|%cn|%ce|%aI|%cI|%s"
    line = _repo(git, layout, "log", "-1", f"--format={fmt}")
    assert line == (
        "Agent B|agent-b@exemple.test|Agent B|agent-b@exemple.test|"
        "2026-01-06T10:00:00Z|2026-01-06T10:00:00Z|Simplifie la valeur"
    )
    assert (layout.repo / "app.py").read_text(encoding="utf-8") == "valeur = 3\n"


@pytest.mark.slow
def test_agent_commit_n_indexe_que_ses_fichiers(settings: Settings, git_path: Path) -> None:
    extra = (
        """\
  - op: write_file
    path: perso.txt
    content: "à moi\\n"
"""
        + AGENT_COMMIT
    )
    prepared, git = _prepare(settings, git_path, extra)
    layout = prepared.layout
    assert _repo(git, layout, "show", "--name-only", "--format=", "HEAD") == "app.py"
    assert _repo(git, layout, "status", "--porcelain") == "?? perso.txt"


@pytest.mark.slow
def test_commit_de_l_agent_porte_le_badge_agent(settings: Settings, git_path: Path) -> None:
    prepared, git = _prepare(settings, git_path, AGENT_COMMIT)
    views = project(git, prepared.layout).views
    actors = {n.subject: n.actor for n in views.graph.nodes}
    assert actors["Simplifie la valeur"] == "agent"
    assert actors["Premier commit"] == "learner"
    assert ACTORS["agent-b@exemple.test"] == "agent"


@pytest.mark.slow
def test_push_force_reecrit_origin_sans_toucher_au_local(
    settings: Settings, git_path: Path
) -> None:
    prepared, git = _prepare(settings, git_path, AGENT_COMMIT + PUSH_FORCE)
    layout = prepared.layout
    local_old = _repo(git, layout, "rev-parse", "main")
    new = _origin(git, layout, "rev-parse", "main")
    assert new != local_old
    # l'ancien sommet n'est plus un ancêtre : l'historique d'origin a été réécrit
    ancestry = git.run("merge-base", "--is-ancestor", local_old, new, cwd=layout.origin)
    assert not ancestry.ok
    assert _origin(git, layout, "rev-parse", "main~1") == _origin(
        git, layout, "rev-parse", f"{local_old}~1"
    )
    line = _origin(git, layout, "log", "-1", "--format=%an|%cn|%aI|%s", "main")
    assert line == "Agent B|Agent B|2026-01-06T11:00:00Z|Réécrit main"
    assert _origin(git, layout, "show", "main:app.py") == "valeur = 4"
    # le dépôt local garde son suivi d'origin jusqu'au prochain fetch
    assert _repo(git, layout, "rev-parse", "origin/main") == local_old
    git.internal("fetch", "-q", cwd=layout.repo)
    assert _repo(git, layout, "rev-parse", "origin/main") == new


@pytest.mark.slow
def test_push_force_sans_force_refuse_une_branche_qui_n_est_pas_le_parent(
    settings: Settings, git_path: Path
) -> None:
    from wavedevsecops.scenarios.context import SetupContext, SetupError
    from wavedevsecops.scenarios.ops._origin import commit_on_origin

    prepared, git = _prepare(settings, git_path, AGENT_COMMIT + "  - op: push\n    branch: main\n")
    ctx = SetupContext(layout=prepared.layout, git=git)
    with pytest.raises(SetupError, match="push forcé"):
        commit_on_origin(ctx, "agent", "main", {}, "x", parent="main~1")


def test_push_force_parent_introuvable_refuse(settings: Settings, git_path: Path) -> None:
    extra = """\
  - op: agent_push_force
    parent: nulle-part
    message: Réécrit
"""
    with pytest.raises(Exception, match="nulle-part"):
        _prepare(settings, git_path, extra)


@pytest.mark.slow
def test_stash_identite_date_et_arbre_propre(settings: Settings, git_path: Path) -> None:
    prepared, git = _prepare(settings, git_path, STASH)
    layout = prepared.layout
    sha = prepared.aliases["mis-de-cote"].removeprefix("commit:")
    assert _repo(git, layout, "rev-parse", "refs/stash") == sha
    line = _repo(git, layout, "stash", "list", "--format=%an|%cn|%cI|%gs")
    assert line.startswith("Agent B|Agent B|2026-01-06T12:00:00Z|")
    assert "Brouillon de l'agent" in line
    assert _repo(git, layout, "status", "--porcelain") == ""
    assert not (layout.repo / "brouillon.txt").exists()


def test_stash_sans_modification_refuse(settings: Settings, git_path: Path) -> None:
    extra = """\
  - op: stash
    message: Rien
"""
    with pytest.raises(Exception, match="Rien à mettre de côté"):
        _prepare(settings, git_path, extra)


@pytest.mark.slow
def test_rebase_laisse_en_conflit_avec_l_identite_de_l_agent(
    settings: Settings, git_path: Path
) -> None:
    prepared, git = _prepare(settings, git_path, AGENT_COMMIT + REBASE)
    layout = prepared.layout
    assert read_repo_state(git, layout.repo, ACTORS).in_progress == "rebase"
    unmerged = _repo(git, layout, "diff", "--name-only", "--diff-filter=U")
    assert unmerged == "app.py"
    content = (layout.repo / "app.py").read_text(encoding="utf-8")
    assert "<<<<<<<" in content
    # le commit déjà rejoué sous l'identité de l'agent : la tête est celle de main
    assert _repo(git, layout, "rev-parse", "HEAD") == _repo(git, layout, "rev-parse", "main")


def test_rebase_sans_conflit_refuse(settings: Settings, git_path: Path) -> None:
    extra = """\
  - op: switch
    branch: feature
  - op: agent_rebase_conflict
    onto: main
"""
    with pytest.raises(Exception, match="sans conflit"):
        _prepare(settings, git_path, extra, feature="autre.py")


def test_rebase_deja_en_cours_refuse(settings: Settings, git_path: Path) -> None:
    # sans ce refus, le second `git rebase` échoue (code 128) et `rebase-merge` du premier
    # ferait croire à un nouveau conflit (revue 5.1)
    extra = (
        AGENT_COMMIT
        + REBASE
        + """\
  - op: agent_rebase_conflict
    onto: main
"""
    )
    with pytest.raises(Exception, match="déjà en cours"):
        _prepare(settings, git_path, extra)


@pytest.mark.slow
def test_scenario_rejoue_deux_fois_donne_la_meme_empreinte(
    settings: Settings, git_path: Path, tmp_path: Path
) -> None:
    first, _ = _prepare(settings, git_path, COMPLET)
    second, _ = _prepare(Settings(data_dir=tmp_path / "autre"), git_path, COMPLET)
    assert first.fingerprint == second.fingerprint
    assert first.aliases == second.aliases


@pytest.mark.slow
def test_sha_et_empreinte_de_reference_stables_sur_les_trois_os(
    settings: Settings, git_path: Path
) -> None:
    prepared, _ = _prepare(settings, git_path, COMPLET)
    assert prepared.aliases["agent-fix"] == f"commit:{AGENT_SHA}"
    assert prepared.aliases["mis-de-cote"] == f"commit:{STASH_SHA}"
    assert prepared.fingerprint == FINGERPRINT
