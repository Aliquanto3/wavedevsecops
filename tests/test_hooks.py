"""Story 3.5 : `install_hooks` et hook `pre-receive` sur un vrai git (AD-8, AD-9)."""

from __future__ import annotations

import io
import os
import sys
from pathlib import Path

import pytest
from test_github_sim import BASE

from wavedevsecops import github_sim, hooks
from wavedevsecops.config import Settings
from wavedevsecops.engine import prepare_workspace
from wavedevsecops.gitio import Git
from wavedevsecops.scenarios import LoadedScenario, parse_scenario
from wavedevsecops.scenarios.loader import ScenarioError

HOOKS = """\
  - op: install_hooks
  - op: set_protection
    branch: main
"""


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(data_dir=tmp_path / "data")


def _prepare(settings: Settings, git_path: Path, extra: str = HOOKS):
    text = BASE.format(feature_path="autre.py") + extra
    loaded = LoadedScenario(parse_scenario(text, "essai.A.yaml"), Path("essai.A.yaml"), "0" * 64)
    prepared = prepare_workspace(loaded, "llm", settings=settings, git_path=git_path)
    return prepared.layout, Git.for_workspace(git_path, prepared.layout.root, settings)


def _commit(git: Git, repo: Path, name: str) -> None:
    (repo / name).write_text("x\n", encoding="utf-8")
    env = {
        "GIT_AUTHOR_NAME": "t",
        "GIT_AUTHOR_EMAIL": "t@exemple.test",
        "GIT_COMMITTER_NAME": "t",
        "GIT_COMMITTER_EMAIL": "t@exemple.test",
    }
    git.internal("add", name, cwd=repo)
    git.internal("commit", "-q", "-m", name, cwd=repo, extra_env=env)


def test_le_script_du_hook_tient_en_une_ligne_sh_en_lf(settings: Settings, git_path: Path) -> None:
    layout, _ = _prepare(settings, git_path)
    raw = (layout.hooks / "pre-receive").read_bytes()
    assert raw == hooks.hook_script("pre-receive", Path(sys.executable)).encode("utf-8")
    assert b"\r" not in raw and raw.endswith(b"\n")
    shebang, command = raw.decode("utf-8").splitlines()
    assert shebang == "#!/bin/sh"
    assert command == (
        f'exec "{Path(sys.executable).as_posix()}" -m wavedevsecops.hooks pre-receive "$@"'
    )
    assert "bash" not in raw.decode("utf-8")
    assert "\\" not in command
    if os.name != "nt":
        assert os.access(layout.hooks / "pre-receive", os.X_OK)


def test_install_hooks_refuse_un_hook_inconnu() -> None:
    text = BASE.format(feature_path="a.py") + "  - op: install_hooks\n    hooks: [pre-push]\n"
    with pytest.raises(ScenarioError):
        parse_scenario(text, "essai.A.yaml")


def test_un_push_direct_sur_main_est_refuse_par_git(settings: Settings, git_path: Path) -> None:
    layout, git = _prepare(settings, git_path)
    before = git.internal("rev-parse", "main", cwd=layout.origin).strip()
    _commit(git, layout.repo, "direct.py")
    result = git.run("push", "origin", "main", cwd=layout.repo)
    assert not result.ok
    assert "remote:" in result.stderr
    assert "La branche « main » est protégée" in result.stderr
    assert git.internal("rev-parse", "main", cwd=layout.origin).strip() == before


def test_une_branche_non_protegee_passe(settings: Settings, git_path: Path) -> None:
    layout, git = _prepare(settings, git_path)
    git.internal("switch", "-q", "feature", cwd=layout.repo)
    _commit(git, layout.repo, "suite.py")
    assert git.run("push", "origin", "feature", cwd=layout.repo).ok


def test_une_protection_sans_blocage_laisse_passer(settings: Settings, git_path: Path) -> None:
    layout, git = _prepare(settings, git_path, HOOKS + "    block_direct_push: false\n")
    _commit(git, layout.repo, "libre.py")
    assert git.run("push", "origin", "main", cwd=layout.repo).ok


def test_le_merge_de_la_pr_ne_passe_pas_par_le_hook(settings: Settings, git_path: Path) -> None:
    extra = HOOKS + "  - op: open_pr\n    head: '@feature'\n    title_text: Change la valeur\n"
    layout, git = _prepare(settings, git_path, extra)
    github_sim.merge_pr(git, layout, 1)
    merged = git.internal("rev-list", "--count", "main", cwd=layout.origin).strip()
    assert int(merged) >= 3


def test_le_point_d_entree_ne_fait_rien_depuis_repo(settings: Settings, git_path: Path) -> None:
    layout, _ = _prepare(settings, git_path)
    line = f"{'0' * 40} {'1' * 40} refs/heads/main\n"
    err = io.StringIO()
    assert hooks.pre_receive(layout.repo, io.StringIO(line), err) == 0
    assert err.getvalue() == ""
    assert hooks.pre_receive(layout.origin, io.StringIO(line), err) == hooks.EXIT_REFUSED
    assert "« main »" in err.getvalue()
    # Hors branche (étiquette) ou ligne mal formée : rien à refuser.
    other = io.StringIO(f"{'0' * 40} {'1' * 40} refs/tags/v1\nbruit\n")
    assert hooks.pre_receive(layout.origin, other, io.StringIO()) == 0


def test_github_json_illisible_ne_bloque_rien(settings: Settings, git_path: Path) -> None:
    layout, _ = _prepare(settings, git_path)
    layout.github_json.write_bytes(b"{pas du json")
    assert github_sim.direct_push_blocked(layout, "main") is False
