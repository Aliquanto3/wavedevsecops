"""`RepoState` et vues sur le vrai git : conformité à `git log --all` et `git status`,
stabilité du placement, annotations, passages liables, publication par la file (AD-2)."""

from __future__ import annotations

import subprocess
import time
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

import pytest

from wavedevsecops.config import Settings
from wavedevsecops.contracts import RepoState, Views, element_id, parse_element_id
from wavedevsecops.engine import OpContext, Operation, WorkspaceEngine, prepare_workspace
from wavedevsecops.engine.manager import repo_projector
from wavedevsecops.events import Envelope, EventLog, Kind
from wavedevsecops.gitio import Git
from wavedevsecops.projections import (
    ACTORS,
    Linker,
    build_views,
    place,
    previous_state,
    project,
    read_repo_state,
)
from wavedevsecops.scenarios import load_scenario
from wavedevsecops.wsfs import Layout

FREE = Path(__file__).resolve().parent.parent / "content" / "scenarios" / "bac-a-sable-libre.A.yaml"
WAIT = 30.0


@dataclass
class Sandbox:
    git: Git
    layout: Layout
    clock: int = 1_780_000_000

    @property
    def repo(self) -> Path:
        return self.layout.repo

    def run(self, *args: str) -> str:
        """Commande de l'apprenant, avec une date qui avance d'une minute à chaque appel."""
        self.clock += 60
        date = f"@{self.clock} +0000"
        env = {
            "GIT_AUTHOR_NAME": "Camille Durand",
            "GIT_AUTHOR_EMAIL": "camille.durand@exemple.test",
            "GIT_COMMITTER_NAME": "Camille Durand",
            "GIT_COMMITTER_EMAIL": "camille.durand@exemple.test",
            "GIT_AUTHOR_DATE": date,
            "GIT_COMMITTER_DATE": date,
        }
        return self.git.internal(*args, cwd=self.repo, extra_env=env)

    def commit(self, message: str) -> str:
        self.run("commit", "-q", "--allow-empty", "-m", message)
        return self.run("rev-parse", "HEAD").strip()

    def write(self, rel: str, text: str) -> None:
        (self.repo / rel).parent.mkdir(parents=True, exist_ok=True)
        (self.repo / rel).write_text(text, encoding="utf-8", newline="\n")

    def state(self) -> RepoState:
        return read_repo_state(self.git, self.repo, ACTORS)


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(data_dir=tmp_path / "data")


@pytest.fixture
def sandbox(settings: Settings, git_path: Path) -> Sandbox:
    prepared = prepare_workspace(
        load_scenario(FREE, settings), "llm", settings=settings, git_path=git_path
    )
    git = Git.for_workspace(git_path, prepared.layout.root, settings)
    return Sandbox(git, prepared.layout)


def conformity(box: Sandbox, state: RepoState) -> None:
    """La projection reprend `git log --all` (hors stash) et `git status`."""
    log = box.run("log", "--exclude=refs/stash", "--all", "--format=%H %P")
    expected = {line.split(" ", 1)[0]: line.split()[1:] for line in log.splitlines() if line}
    reachable = {c.sha: c.parents for c in state.commits if not c.lost}
    assert reachable == expected
    status = box.run("status", "--porcelain=v1", "-z", "--untracked-files=all")
    entries = []
    tokens = iter(status.split("\0"))
    for token in tokens:
        if not token:
            continue
        entries.append((token[:2], token[3:]))
        if token[0] in "RC":
            next(tokens)
    ours = [
        (
            "??"
            if e.kind == "untracked"
            else (e.index_status + e.worktree_status).replace(".", " "),
            e.path,
        )
        for e in state.status
    ]
    assert sorted(ours) == sorted(entries)
    head = box.run("rev-parse", "HEAD").strip()
    assert state.head.commit == head
    graph = place(state.commits)
    assert set(graph.cells) == {c.sha for c in state.commits}


def test_suite_d_etats_conforme_et_placement_stable(sandbox: Sandbox) -> None:
    box = sandbox
    states: list[RepoState] = []
    cells: dict[str, tuple[int, int]] = {}

    def step() -> RepoState:
        state = box.state()
        conformity(box, state)
        layout = place(state.commits)
        current = {sha: (cell.column, cell.row) for sha, cell in layout.cells.items()}
        for sha, cell in cells.items():
            if sha in current:
                assert current[sha] == cell, f"{sha[:7]} a bougé après l'état {len(states)}"
        cells.update(current)
        states.append(state)
        return state

    initial = step()
    assert [c.subject for c in initial.commits if not c.lost] != []
    assert initial.head.ref == "refs/heads/main" and not initial.head.detached
    assert any(r.name == "refs/remotes/origin/main" for r in initial.refs)

    box.commit("Troisième commit")
    step()
    box.run("switch", "-q", "-c", "feature")
    box.commit("Fonction 1")
    f2 = box.commit("Fonction 2")
    step()
    box.run("switch", "-q", "main")
    box.commit("Correctif sur main")
    step()
    box.run("merge", "-q", "--no-ff", "feature", "-m", "Fusion de feature")
    merge = box.run("rev-parse", "HEAD").strip()
    state = step()
    assert next(c for c in state.commits if c.sha == merge).parents[1] == f2

    box.run("tag", "v1.0")
    box.run("tag", "-a", "v1.1", "-m", "Version 1.1", "HEAD~1")
    box.run("push", "-q", "origin", "main")
    state = step()
    tags = {r.short_name: r for r in state.refs if r.kind == "tag"}
    assert tags["v1.0"].commit == merge and not tags["v1.0"].annotated
    assert tags["v1.1"].annotated and tags["v1.1"].commit != tags["v1.1"].target
    assert next(r for r in state.refs if r.name == "refs/remotes/origin/main").commit == merge

    box.run("checkout", "-q", "--detach", "HEAD~1")
    detached = box.commit("Essai détaché")
    state = step()
    assert state.head.detached and state.head.commit == detached
    box.run("switch", "-q", "main")
    state = step()
    assert {c.sha for c in state.commits if c.lost} == {detached}

    box.run("switch", "-q", "feature")
    dropped = box.commit("À jeter")
    box.run("reset", "-q", "--hard", "HEAD~1")
    state = step()
    assert {c.sha for c in state.commits if c.lost} == {detached, dropped}

    box.run("switch", "-q", "-c", "topic")
    replayed = box.commit("Sujet")
    box.run("rebase", "-q", "main")
    state = step()
    assert replayed in {c.sha for c in state.commits if c.lost}
    new_tip = next(r for r in state.refs if r.name == "refs/heads/topic").commit
    assert next(c for c in state.commits if c.sha == new_tip).parents == [merge]

    box.write("README.md", "# Modifié\n")
    box.run("stash", "push", "-q", "-m", "travail en cours")
    state = step()
    assert [(s.index, s.message) for s in state.stash] == [(0, "On topic: travail en cours")]
    assert state.stash[0].sha not in {c.sha for c in state.commits}

    box.write("README.md", "# Encore\n")
    box.write("src/nouveau.py", "x = 1\n")
    box.run("add", "src/nouveau.py")
    box.write("brouillon é.txt", "brouillon\n")
    box.run("mv", "src/bonjour.py", "src/salut.py")
    state = step()
    kinds = {e.path: (e.kind, e.index_status, e.worktree_status) for e in state.status}
    assert kinds["README.md"] == ("changed", ".", "M")
    assert kinds["src/nouveau.py"] == ("changed", "A", ".")
    assert kinds["brouillon é.txt"] == ("untracked", "?", "?")
    assert kinds["src/salut.py"][0] == "renamed"
    assert "brouillon é.txt" in state.worktree and "src/bonjour.py" not in state.worktree
    assert {e.path for e in state.index} >= {"src/nouveau.py", "src/salut.py"}


def test_vues_annotees(sandbox: Sandbox) -> None:
    box = sandbox
    before = box.state()
    box.run("switch", "-q", "-c", "feature")
    sha = box.commit("Ajoute la config")
    after = box.state()
    views = build_views(after, before)

    node = next(n for n in views.graph.nodes if n.sha == sha)
    parent = after.commits[[c.sha for c in after.commits].index(sha)].parents[0]
    assert node.new and not node.lost and node.head and node.designable
    assert node.a11y_name_text == (
        f"Commit {sha[:7]}, Ajoute la config, par vous, parent {parent[:7]}, "
        "pointé par la branche locale feature et HEAD, nouveau"
    )
    assert node.explain_ref == "graph.commit"
    assert [label.name_text for label in node.refs] == ["feature", "HEAD"]
    assert node.links == [element_id("ref", "refs/heads/feature"), element_id("ref", "HEAD")]
    assert sum(n.new for n in views.graph.nodes) == 1
    assert views.prompt.text == "feature" and not views.prompt.detached
    assert views.announce_text == (
        "Vues mises à jour : 1 commit nouveau, 1 branche nouvelle, HEAD sur feature."
    )
    for n in views.graph.nodes:
        assert parse_element_id(n.element_id)[0] == "commit"
        for label in n.refs:
            parse_element_id(label.element_id)

    origin = next(n for n in views.graph.nodes if any(r.kind == "remote" for r in n.refs))
    assert "la référence distante origin/main" in origin.a11y_name_text

    box.run("checkout", "-q", "--detach", "HEAD~1")
    detached = box.state()
    views = build_views(detached, after)
    assert views.prompt.text == "HEAD détachée" and views.prompt.detached
    assert views.prompt.element_id == element_id("commit", detached.head.commit)
    head_node = next(n for n in views.graph.nodes if n.head)
    assert head_node.detached_head and head_node.refs[0].name_text == "HEAD détachée"
    assert views.graph.head_text == f"HEAD détachée sur {detached.head.commit[:7]}"
    assert "HEAD détachée sur" in views.announce_text

    box.run("switch", "-q", "main")
    box.run("branch", "-q", "-D", "feature")
    gone = box.state()
    views = build_views(gone, detached)
    lost = next(n for n in views.graph.nodes if n.sha == sha)
    assert lost.lost and lost.explain_ref == "graph.commit_lost"
    assert lost.a11y_name_text.endswith("perdu, visible par reflog")
    assert "1 commit perdu, visible par reflog" in views.announce_text
    assert "1 branche supprimée" in views.announce_text
    assert any(e.lost for e in views.graph.edges)
    assert build_views(gone, gone).announce_text == "Vues à jour : le dépôt n'a pas changé."
    assert build_views(gone).announce_text.startswith("Dépôt chargé : ")

    box.write("a.txt", "a\n")
    box.run("add", "a.txt")
    box.write("README.md", "# Modifié\n")
    box.write("b.txt", "b\n")
    staging = build_views(box.state()).staging
    assert [(i.path, i.letter, i.element_id) for i in staging.staged] == [
        ("a.txt", "A", element_id("path", "index", "a.txt"))
    ]
    assert [(i.path, i.letter) for i in staging.unstaged] == [("README.md", "M")]
    assert [(i.path, i.letter) for i in staging.untracked] == [("b.txt", "?")]
    # Noms accessibles écrits par le serveur (AD-2), pas par le front.
    names = [i.a11y_name_text for i in [*staging.staged, *staging.unstaged, *staging.untracked]]
    assert names == [
        "Indexé : a.txt, ajouté",
        "Modifié, non indexé : README.md, modifié",
        "Non suivi : b.txt, non suivi",
    ]
    box.run("commit", "-qm", "a")
    box.run("mv", "a.txt", "c.txt")
    renamed = build_views(box.state()).staging.staged
    assert [i.a11y_name_text for i in renamed] == ["Indexé : a.txt → c.txt, renommé"]


def test_passages_liables(sandbox: Sandbox) -> None:
    box = sandbox
    box.run("tag", "v1.0")
    state = box.state()
    head = state.head.commit
    link = Linker(state)
    text = f"[main {head[:7]}] Ajoute ✓ 𝄞 origin/main v1.0 src/bonjour.py:3 inconnu deadbeef."
    spans = link(text)
    found = {s["text"]: s["element_id"] for s in spans}
    assert found == {
        "main": element_id("ref", "refs/heads/main"),
        head[:7]: element_id("commit", head),
        "origin/main": element_id("ref", "refs/remotes/origin/main"),
        "v1.0": element_id("tag", "v1.0"),
        "src/bonjour.py": element_id("path", "worktree", "src/bonjour.py"),
    }
    utf16 = text.encode("utf-16-le")
    for span in spans:
        assert utf16[2 * span["start"] : 2 * span["end"]].decode("utf-16-le") == span["text"]
    diff = link("diff --git a/README.md b/README.md")
    assert [s["text"] for s in diff] == ["README.md", "README.md"]
    assert link("rien à lier ici") == []


def test_previous_state_tolere_une_vue_absente_ou_ancienne() -> None:
    assert previous_state(None) is None
    assert previous_state({}) is None
    assert previous_state({"repo": {"schema_version": 999}}) is None
    assert previous_state({"repo": {"schema_version": 1, "head": "x"}}) is None


def test_depot_vide(tmp_path: Path, settings: Settings, git_path: Path) -> None:
    layout = Layout(tmp_path / "ws")
    layout.repo.mkdir(parents=True)
    git = Git.for_workspace(git_path, layout.root, settings)
    git.internal("init", "-q", cwd=layout.repo)
    projected = project(git, layout)
    views = projected.views
    assert views.repo.commits == [] and views.graph.nodes == []
    assert views.prompt.text == "main" and views.graph.head_text == "HEAD sur main, sans commit"
    assert views.announce_text == "Dépôt chargé : 0 commit, branche courante main."


def _fast_import(git: Git, repo: Path, commits: int) -> None:
    lines: list[str] = []
    for i in range(1, commits + 1):
        branch = "main" if i % 10 < 6 else f"f{i // 10}"
        lines += [
            f"commit refs/heads/{branch}",
            f"mark :{i}",
            f"committer A <a@exemple.test> {1_700_000_000 + 60 * i} +0000",
            f"data {len(f'c{i}')}",
            f"c{i}",
        ]
        if i > 1:
            lines.append(f"from :{i - 1}")
        if i % 10 == 0 and i > 10:
            lines.append(f"merge :{i - 5}")
        lines += ["M 644 inline f.txt", f"data {len(str(i))}", str(i), ""]
    data = ("\n".join(lines) + "\n").encode()
    subprocess.run(
        [str(git.executable), "fast-import", "--quiet"],
        input=data,
        cwd=repo,
        env=git.env(),
        check=True,
        capture_output=True,
    )


def test_performance_quelques_centaines_de_commits(
    tmp_path: Path, settings: Settings, git_path: Path
) -> None:
    layout = Layout(tmp_path / "ws")
    layout.repo.mkdir(parents=True)
    git = Git.for_workspace(git_path, layout.root, settings)
    git.internal("init", "-q", cwd=layout.repo)
    _fast_import(git, layout.repo, 400)
    git.internal("reset", "-q", "--hard", "main", cwd=layout.repo)
    started = time.perf_counter()
    projected = project(git, layout)
    elapsed = time.perf_counter() - started
    assert len(projected.views.graph.nodes) == 400
    assert elapsed < 10.0, f"projection en {elapsed:.1f} s"
    Views.model_validate(projected.views.model_dump(mode="json"))


@pytest.fixture
def events() -> Iterator[list[Envelope]]:
    yield []


def test_la_file_publie_les_vues_et_les_passages_relies(
    sandbox: Sandbox, settings: Settings, git_path: Path, events: list[Envelope]
) -> None:
    box = sandbox
    log = EventLog("llm.bac-a-sable-libre.A", "boot", 1000)
    log.attach(None, events.append)
    engine = WorkspaceEngine(
        "llm.bac-a-sable-libre.A",
        box.layout,
        log,
        settings,
        projector=repo_projector(settings, git_path),
    )
    engine.start()
    try:

        def body(ctx: OpContext) -> int:
            sha = box.commit("Nouveau commit")
            ctx.output(f"[main {sha[:7]}] Nouveau commit", lang="fr")
            return 0

        result = engine.submit(Operation("terminal_line", body)).result(WAIT)
    finally:
        engine.close()
    projected = [e for e in events if e.kind == Kind.STATE_PROJECTED]
    assert len(projected) == 2  # ouverture, puis l'opération
    opening = Views.model_validate(projected[0].payload["views"])
    assert opening.announce_text.startswith("Dépôt chargé : 2 commits")
    views = Views.model_validate(projected[1].payload["views"])
    assert [n.subject for n in views.graph.nodes if n.new] == ["Nouveau commit"]
    assert views.announce_text == "Vues mises à jour : 1 commit nouveau."
    assert projected[1].payload["fingerprint"] == result.projection.fingerprint != ""

    output = next(e for e in events if e.kind == Kind.TERMINAL_OUTPUT)
    assert output.payload["lang"] == "fr"
    # Émise avant la projection : le nouveau SHA n'existait pas encore, `main` si.
    assert [s["text"] for s in output.payload["spans"]] == ["main"]
    relinked = projected[1].payload["output_spans"]
    assert [r["seq"] for r in relinked] == [output.seq]
    new_sha = views.repo.head.commit
    assert {s["element_id"] for s in relinked[0]["spans"]} == {
        element_id("ref", "refs/heads/main"),
        element_id("commit", new_sha),
    }
    assert engine.snapshot()["views"]["prompt"]["text"] == "main"


def test_ref_au_nom_unicode_et_stash(sandbox: Sandbox) -> None:
    """Revue 2.6 : U+2028 ou U+0085 dans un nom de ref ne coupe pas la lecture."""
    box = sandbox
    box.commit("un")
    box.run("branch", "a b")
    box.run("branch", "c\u0085d")
    box.write("f.txt", "x")
    box.run("stash", "push", "-u", "-q", "-m", "essai suite")
    state = box.state()
    names = {r.short_name for r in state.refs}
    assert {"a b", "c\u0085d"} <= names
    assert len(state.stash) == 1
    assert state.stash[0].sha == box.run("rev-parse", "refs/stash").strip()
    assert state.stash[0].message.endswith("essai suite")


def test_projection_garde_les_cases_malgre_une_date_ancienne(
    sandbox: Sandbox, settings: Settings
) -> None:
    """Revue 2.6 : un commit daté avant les autres ne déplace aucun commit publié."""
    box = sandbox
    base = box.commit("base")
    for i in range(3):
        box.commit(f"main {i}")
    box.run("switch", "-q", "-c", "feature", base)
    box.commit("feature 1")
    first = project(box.git, box.layout)
    before = {n.sha: (n.column, n.row) for n in first.views.graph.nodes}
    box.run("switch", "-q", "main")
    box.clock = 1_700_000_000  # horloge reculée
    box.commit("ancien")
    second = project(box.git, box.layout, first.views.model_dump(mode="json"))
    after = {n.sha: (n.column, n.row) for n in second.views.graph.nodes}
    assert all(after[sha] == cell for sha, cell in before.items())
