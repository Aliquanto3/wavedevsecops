"""Instantanés d'un espace et restauration exacte (AD-6, AD-1).

Un instantané est une copie de `repo/`, `origin.git/`, `github.json` et `hooks/`
(`wsfs.SNAPSHOT_ENTRIES`) dans `snapshots/<id>/`, avec son manifeste `snapshot.json` :
identifiant, motif et **empreinte canonique calculée sur la copie**. Les identifiants croissent
sans jamais être réutilisés ; l'instantané 0 est pris à la fin du setup (`prepare_workspace`),
avant tout run du pipeline. Rétention : au plus `Settings.max_snapshots`, le 0 et le dernier
toujours gardés.

Restauration (dans la file, état `restoring`, `epoch` incrémenté par la file) : `ci/` vidé,
surveillant arrêté par le gestionnaire, `run.json` reçoit `restoring{snapshot_id, phase, epoch}`
avant le premier renommage ; l'instantané est copié à côté, puis chaque entrée courante est
renommée vers une corbeille et remplacée par sa copie (trois essais espacés si un fichier est
verrouillé sous Windows) ; l'empreinte est enfin comparée à celle du manifeste. Tout écart ou
toute exception donne `restore_failed` (consigné dans `run.json`), avec la seule action
« Recommencer ». Au démarrage, un `restoring` résiduel reprend la copie (`resume_restore`).

Seul `wsfs` écrit dans le bac à sable ; seul le moteur écrit `run.json` et `snapshots/`.
"""

from __future__ import annotations

import dataclasses
import json
import logging
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from wavedevsecops import wsfs
from wavedevsecops.config import Settings
from wavedevsecops.contracts import AppError
from wavedevsecops.engine.fingerprint import fingerprint
from wavedevsecops.engine.operations import OpContext, Operation
from wavedevsecops.engine.runfile import load_run, save_run
from wavedevsecops.events import Kind, RestoreEnded, RestoreStarted
from wavedevsecops.gitio import Git
from wavedevsecops.wsfs import SNAPSHOT_ENTRIES, Layout

log = logging.getLogger("wavedevsecops")

SNAPSHOT_SCHEMA_VERSION = 1
MANIFEST_FILE = "snapshot.json"
WORK_DIR = ".restore"
"""Sous `snapshots/` : copie en attente et corbeille d'une restauration."""
RESTORED_KEY = "restored"
"""Clé de `OpContext.data` : la projection marque les éléments revenus `restored` (AD-2)."""

Sleep = Callable[[float], Any]


class SnapshotError(AppError):
    """Instantané impossible à prendre (copie, empreinte de la copie)."""


class RestoreFailed(AppError):
    """Restauration en échec : l'espace est en `restore_failed` (seule action : Recommencer)."""

    def __init__(self, snapshot_id: int | None, why: str) -> None:
        super().__init__(
            f"Le rétablissement de l'état a échoué : {why}.",
            "Recommencez le scénario pour repartir de son état de départ.",
        )
        self.snapshot_id = snapshot_id
        self.why = why


@dataclass(frozen=True)
class Snapshot:
    snapshot_id: int
    fingerprint: str
    """Empreinte canonique de la copie (AD-6)."""
    reason: str
    """Motif : `setup` (instantané 0), `quiz`, `exercise`…"""
    path: Path


# ------------------------------------------------------------------ lecture
def _numeric_dirs(layout: Layout) -> list[int]:
    if not layout.snapshots.is_dir():
        return []
    return sorted(
        int(p.name) for p in layout.snapshots.iterdir() if p.name.isdigit() and p.is_dir()
    )


def _read(path: Path, snapshot_id: int) -> Snapshot | None:
    data = wsfs.read_bytes(path, MANIFEST_FILE)
    if data is None:
        return None
    try:
        manifest = json.loads(data.decode("utf-8"))
        digest = manifest["fingerprint"]
        reason = manifest.get("reason", "")
    except ValueError, KeyError, TypeError:
        return None
    if manifest.get("snapshot_id") != snapshot_id or not isinstance(digest, str) or not digest:
        return None
    return Snapshot(snapshot_id, digest, str(reason), path)


def get_snapshot(layout: Layout, snapshot_id: int) -> Snapshot | None:
    """Instantané complet `snapshot_id` (manifeste lisible), ou `None`."""
    path = layout.snapshots / str(snapshot_id)
    return _read(path, snapshot_id) if path.is_dir() else None


def list_snapshots(layout: Layout) -> list[Snapshot]:
    """Instantanés complets de l'espace, du plus ancien au plus récent."""
    found = (get_snapshot(layout, snapshot_id) for snapshot_id in _numeric_dirs(layout))
    return [snapshot for snapshot in found if snapshot is not None]


def latest_snapshot(layout: Layout) -> Snapshot | None:
    """Instantané le plus récent (celui qu'un quiz rétablit), ou `None`."""
    snapshots = list_snapshots(layout)
    return snapshots[-1] if snapshots else None


# ------------------------------------------------------------------ prise
def _copy_git(git: Git, root: Path) -> Git:
    """git borné à une copie d'espace (hooks et plafond de recherche de la copie)."""
    return dataclasses.replace(git, hooks_dir=root / "hooks", ceiling=root)


def take_snapshot(
    layout: Layout,
    git: Git,
    settings: Settings,
    *,
    reason: str,
    expected: str | None = None,
) -> Snapshot:
    """Copie l'espace dans `snapshots/<id>/` et rend l'instantané.

    À appeler depuis une opération de la file (seul écrivain). L'empreinte est calculée sur
    la copie ; `expected` (empreinte de l'espace) la contrôle. La copie est montée à côté puis
    renommée : jamais d'instantané à moitié écrit. Les plus anciens sont ensuite retirés.
    """
    ids = _numeric_dirs(layout)
    snapshot_id = ids[-1] + 1 if ids else 0
    staging = layout.snapshots / f".staging-{snapshot_id}"
    target = layout.snapshots / str(snapshot_id)
    wsfs.remove_tree(staging)
    try:
        wsfs.copy_entries(layout.root, SNAPSHOT_ENTRIES, staging)
        digest = fingerprint(Layout(staging), _copy_git(git, staging))
        if expected is not None and digest != expected:
            raise SnapshotError(
                "La copie de l'instantané ne correspond pas à l'état de l'espace.",
                "Réessayez ; si l'erreur revient, ouvrez le diagnostic.",
            )
        wsfs.write_json(
            staging / MANIFEST_FILE,
            {
                "schema_version": SNAPSHOT_SCHEMA_VERSION,
                "snapshot_id": snapshot_id,
                "reason": reason,
                "fingerprint": digest,
            },
        )
        wsfs.move(staging, target, attempts=1)
    except BaseException:
        wsfs.remove_tree(staging)
        raise
    prune_snapshots(layout, settings)
    return Snapshot(snapshot_id, digest, reason, target)


def prune_snapshots(layout: Layout, settings: Settings) -> list[int]:
    """Retire les plus anciens au-delà de `max_snapshots` ; le 0 et le dernier restent."""
    ids = _numeric_dirs(layout)
    excess = len(ids) - settings.max_snapshots
    removable = [i for i in ids[:-1] if i != 0][: max(excess, 0)]
    for snapshot_id in removable:
        wsfs.remove_tree(layout.snapshots / str(snapshot_id))
    return removable


# ------------------------------------------------------------ restauration
def _update_run(layout: Layout, **changes: Any) -> None:
    data = load_run(layout) if layout.run_json.exists() else {}
    save_run(layout, {**data, **changes})


def _discard(path: Path) -> None:
    """Suppression au mieux (une corbeille encore verrouillée attendra la prochaine fois)."""
    try:
        wsfs.remove_tree(path)
    except OSError:
        log.warning("Corbeille de restauration non supprimée : %s", path, exc_info=True)


def _fail(
    layout: Layout, snapshot_id: int | None, why: str, *, keep_pending: bool = False
) -> RestoreFailed:
    """Consigne `restore_failed` ; `keep_pending` garde `restoring` quand les entrées sont
    dans un état mélangé : le prochain démarrage reprendra alors la copie (AD-6)."""
    failed = RestoreFailed(snapshot_id, why)
    changes: dict[str, Any] = {
        "restore_failed": {"snapshot_id": snapshot_id, "reason_text": failed.cause_text}
    }
    if not keep_pending:
        changes["restoring"] = None
    try:
        _update_run(layout, **changes)
    except Exception:  # noqa: BLE001 - l'échec reste signalé même si run.json est illisible
        log.exception("restore_failed non consigné dans run.json (%s)", layout.root)
    return failed


def _verify(layout: Layout, git: Git, snapshot: Snapshot) -> None:
    digest = fingerprint(layout, git)
    if digest != snapshot.fingerprint:
        raise _fail(layout, snapshot.snapshot_id, "l'état rétabli diffère de l'instantané")
    _discard(layout.snapshots / WORK_DIR)
    _update_run(layout, restoring=None, restore_failed=None)


def _rollback(
    layout: Layout,
    staging: Path,
    trash: Path,
    moved: list[str],
    placed: list[str],
    *,
    pause_s: float,
    sleep: Sleep,
) -> bool:
    """Remet les entrées d'avant la restauration (au mieux) ; `False` si l'une n'a pas pu."""
    complete = True
    for name in reversed(placed):
        try:
            wsfs.move(layout.root / name, staging / name, pause_s=pause_s, sleep=sleep)
        except OSError:
            complete = False
            log.warning("Retour arrière impossible pour %s", name, exc_info=True)
    for name in reversed(moved):
        try:
            wsfs.move(trash / name, layout.root / name, pause_s=pause_s, sleep=sleep)
        except OSError:
            complete = False
            log.warning("Retour arrière impossible pour %s", name, exc_info=True)
    return complete


def restore_snapshot(
    layout: Layout,
    git: Git,
    settings: Settings,
    snapshot_id: int,
    *,
    epoch: int | None = None,
    sleep: Sleep = time.sleep,
) -> Snapshot:
    """Rétablit l'instantané `snapshot_id` ; lève `RestoreFailed` (consigné dans `run.json`).

    À appeler depuis une opération de la file en état `restoring`, surveillant arrêté.
    """
    snapshot = get_snapshot(layout, snapshot_id)
    if snapshot is None:
        raise _fail(layout, snapshot_id, f"l'instantané {snapshot_id} est absent ou illisible")
    work = layout.snapshots / WORK_DIR
    _discard(work)
    token = uuid.uuid4().hex[:8]
    staging, trash = work / f"staging-{token}", work / f"trash-{token}"
    pending = {"snapshot_id": snapshot_id, "epoch": epoch}
    extra = {} if epoch is None else {"epoch": epoch}
    _update_run(layout, restoring={**pending, "phase": "copy"}, **extra)
    # Les runs du pipeline de l'espace s'arrêteront ici aussi (AD-10) ; `ci/` est jetable.
    try:
        wsfs.remove_tree(layout.ci)
        wsfs.copy_entries(snapshot.path, SNAPSHOT_ENTRIES, staging)
    except OSError as error:
        log.warning("Copie de l'instantané %s", snapshot_id, exc_info=True)
        raise _fail(layout, snapshot_id, "la copie de l'instantané a échoué") from error
    _update_run(layout, restoring={**pending, "phase": "swap"})
    pause_s = settings.restore_retry_ms / 1000
    moved: list[str] = []
    placed: list[str] = []
    try:
        for name in SNAPSHOT_ENTRIES:
            current = layout.root / name
            if current.exists() or current.is_symlink():
                wsfs.move(current, trash / name, pause_s=pause_s, sleep=sleep)
                moved.append(name)
            if (staging / name).exists():
                wsfs.move(staging / name, current, pause_s=pause_s, sleep=sleep)
                placed.append(name)
    except OSError as error:
        log.warning("Renommage refusé pendant la restauration", exc_info=True)
        restored = _rollback(layout, staging, trash, moved, placed, pause_s=pause_s, sleep=sleep)
        raise _fail(
            layout,
            snapshot_id,
            "un fichier de l'espace est verrouillé par un autre programme",
            keep_pending=not restored,
        ) from error
    _update_run(layout, restoring={**pending, "phase": "verify"})
    _verify(layout, git, snapshot)
    return snapshot


def pending_restore(layout: Layout) -> dict[str, Any] | None:
    """`restoring` résiduel de `run.json` (arrêt pendant une restauration), ou `None`."""
    if not layout.run_json.exists():
        return None
    try:
        pending = load_run(layout).get("restoring")
    except AppError:
        return None
    return pending if isinstance(pending, dict) else None


def resume_restore(layout: Layout, git: Git, settings: Settings) -> Snapshot | None:
    """Au démarrage : reprend une restauration interrompue (`None` s'il n'y en a pas).

    Les entrées courantes, dans un état inconnu, sont supprimées puis l'instantané est recopié
    et vérifié. Lève `RestoreFailed` si l'instantané manque ou si la reprise échoue.
    """
    pending = pending_restore(layout)
    if pending is None:
        return None
    raw = pending.get("snapshot_id")
    snapshot_id = raw if isinstance(raw, int) else None
    snapshot = get_snapshot(layout, snapshot_id) if snapshot_id is not None else None
    if snapshot is None:
        raise _fail(layout, snapshot_id, "l'instantané à rétablir est absent ou illisible")
    _update_run(layout, restoring={**pending, "phase": "resume"})
    try:
        wsfs.remove_tree(layout.ci)
        for path in layout.entries():
            wsfs.remove_entry(path)
        wsfs.copy_entries(snapshot.path, SNAPSHOT_ENTRIES, layout.root)
    except OSError as error:
        log.warning("Reprise de la restauration %s", snapshot_id, exc_info=True)
        # Entrées dans un état inconnu : le prochain démarrage retentera la copie.
        raise _fail(
            layout, snapshot_id, "la reprise de la copie a échoué", keep_pending=True
        ) from error
    _update_run(layout, restoring={**pending, "phase": "verify"})
    _verify(layout, git, snapshot)
    return snapshot


# ------------------------------------------------------------- opérations
def _git_for(ctx: OpContext, git_path: Path) -> Git:
    return Git.for_workspace(git_path, ctx.layout.root, ctx.settings)


def _run_restore(ctx: OpContext, snapshot_id: int | None, call: Callable[[], Snapshot | None]):
    if snapshot_id is not None:
        ctx.emit(Kind.RESTORE_STARTED, RestoreStarted(snapshot_id=snapshot_id))
    try:
        try:
            snapshot = call()
        except RestoreFailed:
            raise
        except Exception as error:
            # « Tout écart ou toute exception donne `restore_failed` » (AD-6) : git en échec
            # pendant la vérification, `run.json` impossible à écrire…
            log.exception("Restauration de %s", ctx.layout.root)
            pending = pending_restore(ctx.layout)
            mixed = pending is not None and pending.get("phase") not in (None, "copy")
            raise _fail(
                ctx.layout, snapshot_id, "une erreur inattendue l'a interrompu", keep_pending=mixed
            ) from error
    except RestoreFailed as failed:
        ctx.emit(
            Kind.RESTORE_ENDED,
            RestoreEnded(
                status="restore_failed",
                snapshot_id=failed.snapshot_id,
                reason_text=failed.cause_text,
            ),
        )
        raise
    if snapshot is not None:
        ctx.data[RESTORED_KEY] = True
        ctx.emit(Kind.RESTORE_ENDED, RestoreEnded(status="ok", snapshot_id=snapshot.snapshot_id))
        ctx.set_rest_state("idle")
    return 0


def restore_operation(snapshot_id: int, git_path: Path, *, sleep: Sleep = time.sleep) -> Operation:
    """Opération « rétablissement » de l'instantané `snapshot_id` (état `restoring`).

    Admise en `quiz_altered` (`writes=False`) : c'est elle qui en sort ; l'espace revient à
    `idle` si elle réussit.
    """

    def body(ctx: OpContext) -> int:
        return _run_restore(
            ctx,
            snapshot_id,
            lambda: restore_snapshot(
                ctx.layout,
                _git_for(ctx, git_path),
                ctx.settings,
                snapshot_id,
                epoch=ctx.epoch,
                sleep=sleep,
            ),
        )

    return Operation(
        "restore_state",
        body,
        state="restoring",
        writes=False,
        validate=False,
        reason_text="Rétablissement de l'état en cours.",
    )


def resume_operation(snapshot_id: int | None, git_path: Path) -> Operation:
    """Opération de reprise d'une restauration interrompue, placée en tête de file à l'ouverture."""

    def body(ctx: OpContext) -> int:
        return _run_restore(
            ctx,
            snapshot_id,
            lambda: resume_restore(ctx.layout, _git_for(ctx, git_path), ctx.settings),
        )

    return Operation(
        "restore_resume",
        body,
        state="restoring",
        writes=False,
        validate=False,
        reason_text="Reprise du rétablissement interrompu.",
    )
