"""Instantanés et restauration exacte (Story 4.3, AD-6, AD-1) — avec un vrai git."""

from __future__ import annotations

import json
import os
import shutil
from collections.abc import Callable, Iterator
from pathlib import Path

import pytest

from wavedevsecops import wsfs
from wavedevsecops.config import Settings
from wavedevsecops.engine import (
    OpContext,
    Operation,
    PreparedWorkspace,
    RestoreFailed,
    SnapshotError,
    WorkspaceManager,
    fingerprint,
    get_snapshot,
    list_snapshots,
    load_references,
    load_run,
    prepare_workspace,
    reference_key,
    restore_snapshot,
    save_run,
    take_snapshot,
    workspace_id_for,
)
from wavedevsecops.events import Envelope, Kind
from wavedevsecops.gitio import Git
from wavedevsecops.scenarios import load_scenario
from wavedevsecops.wsfs import SNAPSHOT_ENTRIES, Layout

FREE = Path(__file__).resolve().parent.parent / "content" / "scenarios" / "bac-a-sable-libre.A.yaml"
WAIT = 60.0
WS = workspace_id_for("llm", "bac-a-sable-libre.A")
IDENTITY = {
    "GIT_AUTHOR_NAME": "t",
    "GIT_AUTHOR_EMAIL": "t@exemple.test",
    "GIT_COMMITTER_NAME": "t",
    "GIT_COMMITTER_EMAIL": "t@exemple.test",
}


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(data_dir=tmp_path / "data", restore_retry_ms=1)


@pytest.fixture(scope="module")
def template(tmp_path_factory: pytest.TempPathFactory, git_path: Path) -> tuple[Path, object]:
    """Un seul setup par module (vrai git), recopié pour chaque test."""
    base = tmp_path_factory.mktemp("modele") / "data"
    settings = Settings(data_dir=base)
    prepared = prepare_workspace(
        load_scenario(FREE, settings), "llm", settings=settings, git_path=git_path
    )
    return base, prepared


@pytest.fixture
def prepared(template: tuple[Path, object], settings: Settings):
    base, original = template
    shutil.copytree(base, settings.data_dir, symlinks=True)
    relative = original.layout.root.relative_to(base)
    return PreparedWorkspace(
        Layout(settings.data_dir / relative), original.fingerprint, original.aliases
    )


@pytest.fixture
def git(prepared, settings: Settings, git_path: Path) -> Git:
    return Git.for_workspace(git_path, prepared.layout.root, settings)


def _alter(git: Git, layout: Layout, name: str = "nouveau.txt") -> str:
    """Change l'espace : commit, branche, fichier non suivi ; rend le SHA du commit."""
    (layout.repo / name).write_text("contenu\n", encoding="utf-8")
    git.internal("add", name, cwd=layout.repo)
    git.internal("commit", "-q", "-m", f"Ajoute {name}", cwd=layout.repo, extra_env=IDENTITY)
    git.internal("branch", "-q", f"essai-{name.split('.')[0]}", cwd=layout.repo)
    (layout.repo / "brouillon.txt").write_text("non suivi\n", encoding="utf-8")
    return git.internal("rev-parse", "HEAD", cwd=layout.repo).strip()


# ------------------------------------------------------------ instantané 0
def test_instantane_0_a_la_fin_du_setup(prepared, settings: Settings) -> None:
    layout = prepared.layout
    snapshots = list_snapshots(layout)
    assert [s.snapshot_id for s in snapshots] == [0]
    zero = snapshots[0]
    assert zero.reason == "setup"
    assert sorted(p.name for p in zero.path.iterdir()) == sorted(
        [*SNAPSHOT_ENTRIES, "snapshot.json"]
    )
    # L'empreinte de la copie est celle de fin de setup, et celle de référence (AD-18).
    assert zero.fingerprint == prepared.fingerprint
    assert load_run(layout)["setup_fingerprint"] == zero.fingerprint
    references = load_references(settings)
    assert zero.fingerprint == references[reference_key("llm", "bac-a-sable-libre.A")]
    # Avant tout run du pipeline : ni `ci/` ni travail de restauration.
    assert not layout.ci.exists()
    assert sorted(p.name for p in layout.snapshots.iterdir()) == ["0"]


def test_empreinte_controlee_sur_la_copie(prepared, git: Git, settings: Settings) -> None:
    layout = prepared.layout
    with pytest.raises(SnapshotError):
        take_snapshot(layout, git, settings, reason="quiz", expected="0" * 64)
    assert sorted(p.name for p in layout.snapshots.iterdir()) == ["0"]


def test_verrous_de_git_non_copies(prepared, git: Git, settings: Settings) -> None:
    layout = prepared.layout
    (layout.repo / ".git" / "index.lock").write_bytes(b"")
    snapshot = take_snapshot(layout, git, settings, reason="quiz")
    assert not (snapshot.path / "repo" / ".git" / "index.lock").exists()
    assert (snapshot.path / "repo" / ".git" / "index").exists()


def test_retention(prepared, git: Git, settings: Settings) -> None:
    layout = prepared.layout
    small = settings.model_copy(update={"max_snapshots": 3})
    for _ in range(4):
        take_snapshot(layout, git, small, reason="quiz")
    assert [s.snapshot_id for s in list_snapshots(layout)] == [0, 3, 4]
    # Les identifiants ne sont jamais réutilisés.
    assert take_snapshot(layout, git, small, reason="quiz").snapshot_id == 5
    assert [s.snapshot_id for s in list_snapshots(layout)] == [0, 4, 5]


# ------------------------------------------------------------ restauration
def test_restauration_exacte(prepared, git: Git, settings: Settings) -> None:
    layout = prepared.layout
    _alter(git, layout)
    (layout.ci / "1-abcdef0").mkdir(parents=True)
    assert fingerprint(layout, git) != prepared.fingerprint
    restore_snapshot(layout, git, settings, 0, epoch=7)
    assert fingerprint(layout, git) == prepared.fingerprint
    assert not (layout.repo / "brouillon.txt").exists()
    assert not layout.ci.exists()
    run = load_run(layout)
    assert run["epoch"] == 7 and run["restoring"] is None and run["restore_failed"] is None
    assert sorted(p.name for p in layout.snapshots.iterdir()) == ["0"]  # corbeille vidée


def test_ecart_d_empreinte_donne_restore_failed(prepared, git: Git, settings: Settings) -> None:
    layout = prepared.layout
    manifest = layout.snapshots / "0" / "snapshot.json"
    data = json.loads(manifest.read_text(encoding="utf-8"))
    manifest.write_text(json.dumps({**data, "fingerprint": "f" * 64}), encoding="utf-8")
    with pytest.raises(RestoreFailed) as failed:
        restore_snapshot(layout, git, settings, 0)
    assert "diffère" in failed.value.cause_text
    assert "Recommencez" in failed.value.action_text
    run = load_run(layout)
    assert run["restoring"] is None and run["restore_failed"]["snapshot_id"] == 0


def test_instantane_absent(prepared, git: Git, settings: Settings) -> None:
    with pytest.raises(RestoreFailed):
        restore_snapshot(prepared.layout, git, settings, 9)
    assert load_run(prepared.layout)["restore_failed"]["snapshot_id"] == 9


def test_renommage_refuse_trois_essais_puis_retour_arriere(
    prepared, git: Git, settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verrou simulé (tous OS) : trois essais espacés, retour arrière, `restore_failed`."""
    layout = prepared.layout
    _alter(git, layout)
    altered = fingerprint(layout, git)
    real_rename = os.rename
    refused: list[str] = []

    def rename(source, target) -> None:
        if Path(source).name == "origin.git" and "trash" in str(target):
            refused.append(str(source))
            raise PermissionError(13, "verrouillé", str(source))
        real_rename(source, target)

    monkeypatch.setattr(wsfs.os, "rename", rename)
    pauses: list[float] = []
    with pytest.raises(RestoreFailed) as failed:
        restore_snapshot(layout, git, settings, 0, sleep=pauses.append)
    monkeypatch.undo()
    assert len(refused) == 3
    assert pauses == [0.001, 0.002]  # intervalles croissants
    assert "verrouillé" in failed.value.cause_text
    # Retour arrière : l'espace est resté dans l'état d'avant la tentative.
    assert fingerprint(layout, git) == altered
    assert load_run(layout)["restore_failed"]["snapshot_id"] == 0
    assert load_run(layout)["restoring"] is None  # retour arrière complet : rien à reprendre


def test_retour_arriere_incomplet_garde_restoring(
    prepared, git: Git, settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Revue : si le retour arrière échoue aussi, `restoring` reste pour la reprise."""
    layout = prepared.layout
    _alter(git, layout)
    real_rename = os.rename

    def rename(source, target) -> None:
        if Path(source).name == "origin.git" and "trash" in str(target):
            raise PermissionError(13, "verrouillé", str(source))
        if "staging" in str(target):  # le retour arrière est refusé lui aussi
            raise PermissionError(13, "verrouillé", str(source))
        real_rename(source, target)

    monkeypatch.setattr(wsfs.os, "rename", rename)
    with pytest.raises(RestoreFailed):
        restore_snapshot(layout, git, settings, 0, sleep=lambda _s: None)
    monkeypatch.undo()
    run = load_run(layout)
    assert run["restore_failed"]["snapshot_id"] == 0
    assert run["restoring"]["snapshot_id"] == 0


@pytest.mark.skipif(os.name != "nt", reason="verrou de fichier propre à Windows")
def test_fichier_verrouille_sous_windows(prepared, git: Git, settings: Settings) -> None:
    layout = prepared.layout
    altered = fingerprint(layout, git)
    with open(layout.repo / "README.md", "rb"):  # handle ouvert : `repo/` ne se renomme pas
        with pytest.raises(RestoreFailed):
            restore_snapshot(layout, git, settings, 0)
    assert fingerprint(layout, git) == altered
    assert load_run(layout)["restore_failed"] is not None
    restore_snapshot(layout, git, settings, 0)  # une fois le fichier libéré, elle réussit
    assert load_run(layout)["restore_failed"] is None


# ---------------------------------------------------- dans la file (manager)
class FakeWatcher:
    def __init__(self, repo: Path, on_change: Callable[[], None]) -> None:
        self.calls: list[str] = []

    def start(self) -> None:
        self.calls.append("start")

    def stop(self) -> None:
        self.calls.append("stop")

    def suspend(self) -> None:
        self.calls.append("suspend")

    def resume(self) -> None:
        self.calls.append("resume")


@pytest.fixture
def watchers() -> list[FakeWatcher]:
    return []


@pytest.fixture
def manager(
    settings: Settings, git_path: Path, watchers: list[FakeWatcher]
) -> Iterator[WorkspaceManager]:
    def factory(repo: Path, on_change: Callable[[], None]) -> FakeWatcher:
        watchers.append(FakeWatcher(repo, on_change))
        return watchers[-1]

    m = WorkspaceManager(settings, watcher_factory=factory, git_path=git_path)
    yield m
    m.close()


def _events(manager: WorkspaceManager) -> list[Envelope]:
    events: list[Envelope] = []
    manager.events(WS).attach(None, events.append)
    return events


def _node(views: dict, sha: str) -> dict:
    return next(n for n in views["graph"]["nodes"] if n["sha"] == sha)


def test_restauration_dans_la_file(
    prepared, git: Git, manager: WorkspaceManager, watchers: list[FakeWatcher]
) -> None:
    layout = prepared.layout
    events = _events(manager)
    engine = manager.get(WS)
    engine.submit(Operation("x", lambda ctx: 0)).result(WAIT)
    assert len(watchers) == 1 and watchers[0].calls[0] == "start"
    sha = _alter(git, layout)
    settings = manager.settings
    one = engine.submit(
        Operation(
            "x", lambda ctx: take_snapshot(ctx.layout, git, settings, reason="quiz").snapshot_id
        )
    ).result(WAIT)
    assert one.code == 1
    epoch = engine.epoch

    result = manager.restore(WS, 0).result(WAIT)
    assert fingerprint(layout, git) == prepared.fingerprint
    assert engine.epoch == epoch + 1 and load_run(layout)["epoch"] == epoch + 1
    assert result.projection is not None and result.projection.fingerprint == prepared.fingerprint
    # Surveillant arrêté pendant `restoring`, puis un nouveau lancé au retour au repos.
    assert watchers[0].calls[-1] == "stop" and len(watchers) == 2
    assert watchers[1].calls == ["start"]
    ops = [e for e in events if e.op_id == result.op_id]
    kinds = [e.kind.value for e in ops]
    assert (
        kinds.index("restore_started")
        < kinds.index("restore_ended")
        < kinds.index("state_projected")
    )
    assert ops[0].payload == {
        "state": "restoring",
        "reason_text": "Rétablissement de l'état en cours.",
    }
    ended = next(e for e in ops if e.kind == Kind.RESTORE_ENDED)
    assert ended.payload["status"] == "ok" and ended.payload["snapshot_id"] == 0
    assert all(e.epoch == epoch + 1 for e in ops)
    assert sha not in {n["sha"] for n in result.projection.views["graph"]["nodes"]}

    # Rétablir l'instantané 1 : le commit revient avec la marque `restored`, pas `new`.
    back = manager.restore(WS, 1).result(WAIT)
    node = _node(back.projection.views, sha)
    assert node["restored"] and not node["new"] and "rétabli" in node["a11y_name_text"]
    assert engine.state == "idle"


def test_restauration_admise_en_quiz_altered(prepared, manager: WorkspaceManager) -> None:
    engine = manager.get(WS)
    engine.submit(
        Operation("quiz", lambda ctx: ctx.set_rest_state("quiz_altered"), writes=False)
    ).result(WAIT)
    assert engine.state == "quiz_altered"
    manager.restore(WS, 0).result(WAIT)
    assert engine.state == "idle"


def test_restore_failed_dans_la_file(prepared, manager: WorkspaceManager) -> None:
    events = _events(manager)
    result = manager.restore(WS, 4).result(WAIT)
    assert result.code is None
    ops = [e for e in events if e.op_id == result.op_id]
    ended = next(e for e in ops if e.kind == Kind.RESTORE_ENDED)
    assert ended.payload["status"] == "restore_failed"
    error = next(e for e in ops if e.kind == Kind.APP_ERROR)
    assert "Recommencez" in error.payload["action_text"]
    assert manager.get(WS).state == "idle"  # refus des autres intentions : story 4.4


def test_exception_inattendue_donne_restore_failed(
    prepared, manager: WorkspaceManager, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Revue : une exception hors `RestoreFailed` (ici à la vérification) donne aussi
    `restore_failed`, et `restoring` reste pour que le démarrage suivant reprenne la copie."""
    from wavedevsecops.engine import snapshots

    def broken(*_args, **_kwargs):
        raise RuntimeError("git introuvable")

    monkeypatch.setattr(snapshots, "fingerprint", broken)
    events = _events(manager)
    result = manager.restore(WS, 0).result(WAIT)
    ended = next(e for e in events if e.op_id == result.op_id and e.kind == Kind.RESTORE_ENDED)
    assert ended.payload["status"] == "restore_failed"
    run = load_run(prepared.layout)
    assert run["restore_failed"]["snapshot_id"] == 0
    assert run["restoring"]["phase"] == "verify"


def test_reprise_au_demarrage(prepared, git: Git, manager: WorkspaceManager) -> None:
    """Arrêt pendant `restoring` : au redémarrage, la copie reprend puis est vérifiée."""
    layout = prepared.layout
    _alter(git, layout)
    run = load_run(layout)
    save_run(layout, {**run, "restoring": {"snapshot_id": 0, "phase": "swap", "epoch": 1}})
    wsfs.remove_tree(layout.hooks)  # copie à moitié faite
    events = _events(manager)
    engine = manager.get(WS)
    engine.submit(Operation("x", lambda ctx: 0)).result(WAIT)  # après la reprise
    assert fingerprint(layout, git) == prepared.fingerprint
    assert load_run(layout)["restoring"] is None
    assert any(e.kind == Kind.RESTORE_ENDED and e.payload["status"] == "ok" for e in events)


def test_reprise_impossible_donne_restore_failed(prepared, manager: WorkspaceManager) -> None:
    layout = prepared.layout
    run = load_run(layout)
    save_run(layout, {**run, "restoring": {"snapshot_id": 3, "phase": "copy", "epoch": 1}})
    events = _events(manager)
    engine = manager.get(WS)
    engine.submit(Operation("x", lambda ctx: 0, writes=False)).result(WAIT)
    assert any(
        e.kind == Kind.RESTORE_ENDED and e.payload["status"] == "restore_failed" for e in events
    )
    assert load_run(layout)["restore_failed"]["snapshot_id"] == 3
    assert get_snapshot(layout, 0) is not None


def test_un_instantane_pris_dans_une_operation(
    prepared, git: Git, manager: WorkspaceManager
) -> None:
    def body(ctx: OpContext) -> int:
        return take_snapshot(ctx.layout, git, ctx.settings, reason="quiz").snapshot_id

    assert manager.get(WS).submit(Operation("quiz", body)).result(WAIT).code == 1
    assert [s.reason for s in list_snapshots(prepared.layout)] == ["setup", "quiz"]
