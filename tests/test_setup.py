"""Setup déterministe d'un espace par le vrai git (AD-3, AD-5, AD-6, AD-7)."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
import yaml

from wavedevsecops import gitio
from wavedevsecops.config import Settings
from wavedevsecops.engine import (
    WorkspaceError,
    canonical_records,
    fingerprint,
    prepare_workspace,
)
from wavedevsecops.gitio import Git, hermetic_environment
from wavedevsecops.scenarios import (
    LoadedScenario,
    Scenario,
    SetupError,
    load_scenario,
    parse_scenario,
)

FREE = Path(__file__).resolve().parent.parent / "content" / "scenarios" / "bac-a-sable-libre.A.yaml"


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(data_dir=tmp_path / "data")


@pytest.fixture
def free(settings: Settings) -> LoadedScenario:
    return load_scenario(FREE, settings)


def _git(prepared, settings: Settings, git_path: Path) -> Git:
    return Git.for_workspace(git_path, prepared.layout.root, settings)


def _loaded(text: str, *, checked: bool = True) -> LoadedScenario:
    if checked:
        scenario = parse_scenario(text, "essai.A.yaml")
    else:  # sans les règles entre champs du chargeur : l'erreur vient de l'exécution
        scenario = Scenario.model_validate(yaml.safe_load(text))
    return LoadedScenario(scenario, Path("essai.A.yaml"), "0" * 64)


def test_environnement_hermetique(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    inherited = {
        "PATH": "/bin",
        "GIT_DIR": "/ailleurs",
        "GIT_CONFIG_PARAMETERS": "'core.autocrlf'='true'",
        "HTTPS_PROXY": "http://proxy:3128",
        "no_proxy": "x",
        "LC_ALL": "fr_FR.UTF-8",
        "LANG": "fr_FR.UTF-8",
        "EDITOR": "vim",
    }
    monkeypatch.setattr(gitio, "inherited_environment", lambda: dict(inherited))
    env = hermetic_environment(gitconfig=tmp_path / "gitconfig", hooks_dir=tmp_path / "hooks")
    assert env["PATH"] == "/bin"
    for name in ("GIT_DIR", "GIT_CONFIG_PARAMETERS", "HTTPS_PROXY", "no_proxy", "EDITOR", "LANG"):
        assert name not in env
    assert env["LC_ALL"] == "C" and env["LANGUAGE"] == ""
    assert env["GIT_CONFIG_NOSYSTEM"] == "1"
    assert env["GIT_CONFIG_GLOBAL"] == str(tmp_path / "gitconfig")
    assert env["GIT_TERMINAL_PROMPT"] == "0" and env["GIT_EDITOR"] == ":"
    forced = {
        env[f"GIT_CONFIG_KEY_{i}"]: env[f"GIT_CONFIG_VALUE_{i}"]
        for i in range(int(env["GIT_CONFIG_COUNT"]))
    }
    assert forced["core.autocrlf"] == "false" and forced["core.eol"] == "lf"
    assert forced["core.hooksPath"] == (tmp_path / "hooks").as_posix()
    assert forced["init.defaultBranch"] == "main" and forced["credential.helper"] == ""
    learner = hermetic_environment(
        gitconfig=tmp_path, hooks_dir=tmp_path, context="learner", locale="fr_FR.UTF-8"
    )
    assert learner["LC_ALL"] == "fr_FR.UTF-8" and learner["LANGUAGE"] == "fr"


def test_bac_a_sable_libre(settings: Settings, free: LoadedScenario, git_path: Path) -> None:
    prepared = prepare_workspace(free, "llm", settings=settings, git_path=git_path)
    root = settings.resolved_data_dir() / "workspaces" / "llm" / "bac-a-sable-libre.A"
    assert prepared.layout.root == root
    for name in ("repo", "origin.git", "hooks", "run.json"):
        assert (root / name).exists(), name
    git = _git(prepared, settings, git_path)
    assert git.internal("rev-parse", "--is-bare-repository", cwd=root / "origin.git").strip() == (
        "true"
    )
    assert git.internal("remote", "get-url", "origin", cwd=root / "repo").strip() == "../origin.git"
    log = git.internal(
        "log", "--date=raw", "--format=%H|%an|%ae|%ad|%cd|%s", "main", cwd=root / "repo"
    )
    lines = log.splitlines()
    assert len(lines) == 2
    stamp = int(datetime(2026, 1, 5, 9, 1, tzinfo=UTC).timestamp())
    assert lines[0].split("|")[1:] == [
        "Camille Durand",
        "camille.durand@exemple.test",
        f"{stamp} +0000",
        f"{stamp} +0000",
        "Ajoute la fonction bonjour",
    ]
    origin_main = git.internal("rev-parse", "main", cwd=root / "origin.git").strip()
    assert origin_main == lines[0].split("|")[0]
    assert (root / "repo" / "README.md").read_bytes().count(b"\r") == 0
    assert git.internal("status", "--porcelain", cwd=root / "repo") == ""
    run = json.loads((root / "run.json").read_bytes())
    assert run["setup_fingerprint"] == prepared.fingerprint
    assert run["content_hash"] == free.content_hash and run["epoch"] == 0
    assert run["aliases"]["second-commit"] == f"commit:{origin_main}"
    assert run["aliases"]["origin-main"] == "ref:refs/remotes/origin/main"
    assert run["aliases"]["readme"] == "path:worktree:README.md"


def test_meme_empreinte_quel_que_soit_le_poste(
    settings: Settings,
    free: LoadedScenario,
    git_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    first = prepare_workspace(free, "llm", settings=settings, git_path=git_path)
    hostile = tmp_path / "hostile.gitconfig"
    hostile.write_text(
        "[core]\n\tautocrlf = true\n[user]\n\tname = Intrus\n[init]\n\tdefaultBranch = trunk\n",
        encoding="utf-8",
    )
    # Ignore et attributs globaux par défaut ($XDG_CONFIG_HOME/git/…, ~/.config/git/…) :
    # lus par git même avec GIT_CONFIG_GLOBAL, ils doivent rester sans effet.
    for base in (tmp_path / "xdg" / "git", tmp_path / "home" / ".config" / "git"):
        base.mkdir(parents=True)
        (base / "ignore").write_text("*.py\nREADME.md\n", encoding="utf-8")
        (base / "attributes").write_text("* text eol=crlf\n", encoding="utf-8")
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setenv("USERPROFILE", str(tmp_path / "home"))
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(hostile))
    monkeypatch.setenv("GIT_AUTHOR_NAME", "Intrus")
    monkeypatch.setenv("GIT_COMMITTER_DATE", "2001-01-01T00:00:00+00:00")
    second = prepare_workspace(free, "no_ai", settings=settings, git_path=git_path)
    assert first.fingerprint == second.fingerprint
    rebuilt = prepare_workspace(free, "llm", settings=settings, git_path=git_path, replace=True)
    assert rebuilt.fingerprint == first.fingerprint


def test_empreinte_suit_l_etat_et_ignore_le_reste(
    settings: Settings, free: LoadedScenario, git_path: Path
) -> None:
    prepared = prepare_workspace(free, "llm", settings=settings, git_path=git_path)
    layout = prepared.layout
    git = _git(prepared, settings, git_path)
    reference = prepared.fingerprint
    records = canonical_records(layout, git)
    assert "repo HEAD -> refs/heads/main" in records
    assert "origin HEAD -> refs/heads/main" in records
    assert any(r.startswith("repo index 100644 ") and r.endswith(" README.md") for r in records)

    (layout.ci / "1-abc").mkdir(parents=True)
    (layout.ci / "1-abc" / "log.txt").write_text("x", encoding="utf-8")
    (layout.cache / "venv").mkdir(parents=True)
    (layout.repo / ".gitignore").write_text("*.log\n", encoding="utf-8")
    with_gitignore = fingerprint(layout, git)
    assert with_gitignore != reference
    (layout.repo / "debug.log").write_text("ignoré", encoding="utf-8")
    assert fingerprint(layout, git) == with_gitignore
    (layout.repo / ".gitignore").unlink()
    assert fingerprint(layout, git) != reference
    (layout.repo / "debug.log").unlink()
    assert fingerprint(layout, git) == reference

    (layout.repo / "README.md").write_text("modifié\n", encoding="utf-8")
    assert fingerprint(layout, git) != reference
    git.internal("checkout", "--", "README.md", cwd=layout.repo)
    assert fingerprint(layout, git) == reference

    (layout.hooks / "pre-commit").write_text("#!/bin/sh\n", encoding="utf-8")
    assert fingerprint(layout, git) != reference


def test_ops_branch_switch_et_alias(settings: Settings, git_path: Path) -> None:
    text = """\
schema_version: 1
scenario_id: essai
mode: A
title_text: Essai
tracks: [no_ai]
setup:
  - {op: write_file, path: a.txt, content: "a\\n"}
  - {op: commit, message: Premier, as: premier}
  - {op: branch, name: feature, start: "@premier", as: feature}
  - {op: switch, branch: "@feature"}
  - {op: write_file, path: b.txt, content: "b\\n"}
  - {op: commit, message: Second, author: colleague, date: "2026-02-01T10:00:00+01:00"}
  - {op: push, branch: "@feature", as: origin-feature}
  - {op: switch, branch: correctif, create: true, start: "@premier"}
"""
    prepared = prepare_workspace(_loaded(text), "no_ai", settings=settings, git_path=git_path)
    git = _git(prepared, settings, git_path)
    repo = prepared.layout.repo
    assert git.internal("symbolic-ref", "--short", "HEAD", cwd=repo).strip() == "correctif"
    show = git.internal("log", "-1", "--date=raw", "--format=%an|%ad", "feature", cwd=repo)
    stamp = int(datetime(2026, 2, 1, 9, 0, tzinfo=UTC).timestamp())
    assert show.strip() == f"Sacha Martin|{stamp} +0100"
    origin = git.internal("rev-parse", "feature", cwd=prepared.layout.origin).strip()
    assert origin == git.internal("rev-parse", "feature", cwd=repo).strip()
    assert prepared.aliases["feature"] == "ref:refs/heads/feature"
    assert prepared.aliases["origin-feature"] == "ref:refs/remotes/origin/feature"


def test_espace_existant_et_echec_nettoye(
    settings: Settings, free: LoadedScenario, git_path: Path
) -> None:
    prepare_workspace(free, "llm", settings=settings, git_path=git_path)
    with pytest.raises(WorkspaceError) as info:
        prepare_workspace(free, "llm", settings=settings, git_path=git_path)
    assert "existe déjà" in info.value.cause_text
    with pytest.raises(WorkspaceError):
        prepare_workspace(free, "autre", settings=settings, git_path=git_path)

    broken = _loaded(
        "schema_version: 1\nscenario_id: essai\nmode: A\ntitle_text: E\ntracks: [llm]\n"
        "setup:\n  - {op: switch, branch: inexistante}\n"
    )
    with pytest.raises(gitio.GitError):
        prepare_workspace(broken, "llm", settings=settings, git_path=git_path)
    assert not (settings.workspaces_path() / "llm" / "essai.A").exists()


def test_alias_inconnu_a_l_execution(settings: Settings, git_path: Path) -> None:
    loaded = _loaded(
        "schema_version: 1\nscenario_id: essai\nmode: A\ntitle_text: E\ntracks: [llm]\n"
        "setup:\n  - {op: branch, name: x, start: '@absent'}\n",
        checked=False,
    )
    with pytest.raises(SetupError) as info:
        prepare_workspace(loaded, "llm", settings=settings, git_path=git_path)
    assert "@absent" in info.value.cause_text
