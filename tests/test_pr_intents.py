"""Story 3.2 : ouvrir une PR et la merger, sur un vrai git et par la file d'opérations."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from test_terminal import WAIT, Space

from wavedevsecops import github_sim, terminal
from wavedevsecops.config import Settings
from wavedevsecops.engine import OperationRefused, build_operation, pr_intents
from wavedevsecops.events import Kind
from wavedevsecops.gitio import Git, GitError


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(data_dir=tmp_path / "data")


@pytest.fixture
def space(settings: Settings, git_path: Path) -> Iterator[Space]:
    terminal.AFTER_COMMAND_HOOKS.clear()
    pr_intents.register_intents()
    terminal.AFTER_COMMAND_HOOKS.append(pr_intents.refresh_after_command)
    s = Space(settings, git_path)
    s.identify()
    try:
        yield s
    finally:
        s.manager.close()
        terminal.AFTER_COMMAND_HOOKS.clear()


def _git(space: Space, git_path: Path) -> Git:
    return Git.for_workspace(git_path, space.layout.root, space.settings)


def _sh(space: Space, *lines: str) -> None:
    for line in lines:
        assert space.run(line).code == 0, line


def _push_branch(space: Space, name: str, path: str, text: str) -> None:
    _sh(space, f"git switch -c {name}")
    space.write(path, text)
    _sh(space, f"git add {path}", f"git commit -m {name}", f"git push origin {name}")


def _intent(space: Space, name: str, body: dict):
    op = build_operation(space.engine, name, body)
    future = space.engine.submit(op)
    code = future.result(WAIT).code
    return op, code


def _origin_sha(space: Space, git_path: Path, branch: str) -> str:
    return _git(space, git_path).internal("rev-parse", branch, cwd=space.layout.origin).strip()


def test_ouvrir_puis_merger_une_pr(space: Space, git_path: Path) -> None:
    _sh(space, "git switch main")
    _push_branch(space, "feat", "feat.txt", "x\n")
    before = _origin_sha(space, git_path, "main")
    op, code = _intent(space, "pr_open", {"head": "feat"})
    assert code == 0
    state = github_sim.load(space.layout)
    pr = state.pulls[0]
    assert (pr.number, pr.head, pr.base, pr.state) == (1, "feat", "main", "open")
    assert pr.base_sha == before and pr.mergeable
    updates = [e for e in space.events if e.kind == Kind.PR_UPDATED and e.op_id == op.op_id]
    assert updates and updates[0].payload["element_id"] == "pr:1"

    op, code = _intent(space, "pr_merge", {"number": 1})
    assert code == 0
    merged = github_sim.load(space.layout).pull(1)
    assert merged.state == "merged" and merged.merge_sha == _origin_sha(space, git_path, "main")
    assert any(e.kind == Kind.PR_UPDATED and e.op_id == op.op_id for e in space.events)
    git = _git(space, git_path)
    log = git.internal("log", "-1", "--format=%an|%ae|%s|%P", "main", cwd=space.layout.origin)
    name, email, subject, parents = log.strip().split("|")
    assert (name, subject) == ("GitHub simulé", "Merge pull request #1 from feat")
    assert email.endswith(".invalid") and len(parents.split()) == 2
    # Le graphe côté apprenant voit origin/main à jour après un fetch.
    _sh(space, "git fetch origin")
    remote = git.internal("rev-parse", "refs/remotes/origin/main", cwd=space.layout.repo).strip()
    assert remote == merged.merge_sha


def test_branche_absente_d_origin_refusee_en_409(space: Space) -> None:
    with pytest.raises(OperationRefused, match="Poussez d'abord"):
        build_operation(space.engine, "pr_open", {"head": "fantome"})
    assert github_sim.load(space.layout).pulls == []


def test_pr_en_conflit_refusee(space: Space, git_path: Path) -> None:
    _sh(space, "git switch main")
    space.write("x.txt", "a\n")
    _sh(space, "git add x.txt", "git commit -m base", "git push origin main")
    _push_branch(space, "feat", "x.txt", "b\n")
    _sh(space, "git switch main")
    space.write("x.txt", "c\n")
    _sh(space, "git add x.txt", "git commit -m main-bouge", "git push origin main")
    _intent(space, "pr_open", {"head": "feat"})
    pr = github_sim.load(space.layout).pull(1)
    assert not pr.mergeable and [r.kind for r in pr.blocking_reasons] == ["conflict"]
    with pytest.raises(OperationRefused, match="conflit"):
        build_operation(space.engine, "pr_merge", {"number": 1})
    with pytest.raises(OperationRefused, match="n'est pas ouverte"):
        build_operation(space.engine, "pr_merge", {"number": 9})


def test_base_qui_bouge_pendant_le_merge(
    space: Space, git_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _sh(space, "git switch main")
    _push_branch(space, "feat", "feat.txt", "x\n")
    _intent(space, "pr_open", {"head": "feat"})
    git = _git(space, git_path)
    layout = space.layout
    main_before = _origin_sha(space, git_path, "main")
    real = github_sim._update_ref

    def moved(g, lay, ref, new, old):
        # Un autre push avance `main` entre le calcul et l'écriture.
        sha = g.internal("rev-parse", "feat", cwd=lay.origin).strip()
        g.internal("update-ref", ref, sha, old, cwd=lay.origin)
        return real(g, lay, ref, new, old)

    monkeypatch.setattr(github_sim, "_update_ref", moved)
    with pytest.raises(github_sim.MergeRaced, match="bougé"):
        github_sim.merge_pr(git, layout, 1)
    pr = github_sim.load(layout).pull(1)
    assert pr.state == "open" and pr.merge_sha is None
    assert pr.base_sha == _origin_sha(space, git_path, "main") != main_before


def test_un_push_du_terminal_rafraichit_les_pr(space: Space, git_path: Path) -> None:
    _sh(space, "git switch main")
    _push_branch(space, "feat", "feat.txt", "x\n")
    _intent(space, "pr_open", {"head": "feat"})
    _sh(space, "git switch main")
    space.write("autre.txt", "y\n")
    _sh(space, "git add autre.txt", "git commit -m autre")
    result = space.run("git push origin main")
    assert result.code == 0
    pr = github_sim.load(space.layout).pull(1)
    assert pr.base_sha == _origin_sha(space, git_path, "main")
    assert any(e.kind == Kind.PR_UPDATED and e.op_id == result.op_id for e in space.events)


def test_intentions_enregistrees_et_corps_invalides() -> None:
    from wavedevsecops.engine import INTENTS, InvalidIntent

    pr_intents.register_intents()
    assert {"pr_open", "pr_merge"} <= set(INTENTS)
    with pytest.raises(InvalidIntent):
        build_operation(None, "pr_merge", {"number": 0})


def test_merge_interrompu_constate_sans_nouveau_commit(
    space: Space, git_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """github.json non écrit après `update-ref` : le merge relancé le constate, sans doublon."""
    _sh(space, "git switch main")
    _push_branch(space, "feat", "feat.txt", "x\n")
    _intent(space, "pr_open", {"head": "feat"})
    git, layout = _git(space, git_path), space.layout
    real_save = github_sim._save

    def locked(lay, state):
        if any(p.state == "merged" for p in state.pulls):
            raise PermissionError("github.json verrouillé")
        real_save(lay, state)

    monkeypatch.setattr(github_sim, "_save", locked)
    with pytest.raises(github_sim.GithubSimError, match="écrit dans origin"):
        github_sim.merge_pr(git, layout, 1)
    merge_sha = _origin_sha(space, git_path, "main")
    assert github_sim.load(layout).pull(1).state == "open"
    monkeypatch.setattr(github_sim, "_save", real_save)
    op, code = _intent(space, "pr_merge", {"number": 1})
    assert code == 0
    assert github_sim.load(layout).pull(1).merge_sha == merge_sha
    assert _origin_sha(space, git_path, "main") == merge_sha
    with pytest.raises(OperationRefused, match="n'est pas ouverte"):
        build_operation(space.engine, "pr_merge", {"number": 1})
    assert _origin_sha(space, git_path, "main") == merge_sha


def test_head_deja_contenue_dans_base_refusee(space: Space, git_path: Path) -> None:
    _sh(space, "git switch main")
    _push_branch(space, "feat", "feat.txt", "x\n")
    _intent(space, "pr_open", {"head": "feat"})
    _sh(space, "git switch main", "git merge --ff-only feat", "git push origin main")
    before = _origin_sha(space, git_path, "main")
    with pytest.raises(github_sim.GithubSimError, match="rien à merger"):
        github_sim.merge_pr(_git(space, git_path), space.layout, 1)
    assert _origin_sha(space, git_path, "main") == before


def test_update_ref_en_echec_sans_course(
    space: Space, git_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _sh(space, "git switch main")
    _push_branch(space, "feat", "feat.txt", "x\n")
    _intent(space, "pr_open", {"head": "feat"})
    before = _origin_sha(space, git_path, "main")
    failed = type(
        "R", (), {"ok": False, "returncode": 128, "stderr": "", "error": None, "timed_out": False}
    )()
    monkeypatch.setattr(github_sim, "_update_ref", lambda *a: failed)
    with pytest.raises(GitError):
        github_sim.merge_pr(_git(space, git_path), space.layout, 1)
    assert _origin_sha(space, git_path, "main") == before


def test_course_par_l_intention_annonce_les_pr(
    space: Space, git_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _sh(space, "git switch main")
    _push_branch(space, "feat", "feat.txt", "x\n")
    _intent(space, "pr_open", {"head": "feat"})
    real = github_sim._update_ref

    def moved(g, lay, ref, new, old):
        sha = g.internal(
            "commit-tree",
            "-m",
            "autre",
            "-p",
            old,
            f"{old}^{{tree}}",
            cwd=lay.origin,
            extra_env=github_sim.MERGE_IDENTITY,
        ).strip()
        g.internal("update-ref", ref, sha, old, cwd=lay.origin)
        return real(g, lay, ref, new, old)

    monkeypatch.setattr(github_sim, "_update_ref", moved)
    op, code = _intent(space, "pr_merge", {"number": 1})
    assert code == 2, [e.payload for e in space.events if e.op_id == op.op_id]
    assert any(e.kind == Kind.PR_UPDATED and e.op_id == op.op_id for e in space.events)
    assert github_sim.load(space.layout).pull(1).state == "open"


def test_create_app_branche_les_pr_une_seule_fois(settings: Settings) -> None:
    from wavedevsecops.engine import INTENTS
    from wavedevsecops.web.app import create_app

    terminal.AFTER_COMMAND_HOOKS.clear()
    try:
        for _ in range(2):
            app = create_app(port=1, token="t", settings=settings)
            app.state.workspaces.close()
        assert terminal.AFTER_COMMAND_HOOKS == [pr_intents.refresh_after_command]
        assert {"pr_open", "pr_merge"} <= set(INTENTS)
    finally:
        terminal.AFTER_COMMAND_HOOKS.clear()
