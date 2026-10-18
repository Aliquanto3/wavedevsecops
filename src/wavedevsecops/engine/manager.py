"""Espaces ouverts : une file et un surveillant par espace actif, les autres en veille (AD-1).

`workspace_id` = `<parcours>.<scenario_id>.<mode>` (par exemple `llm.bac-a-sable-libre.A`),
utilisable tel quel dans une URL. Au plus `Settings.max_active_workspaces` espaces sont
actifs ; le moins récemment utilisé s'endort (file et surveillant arrêtés), et se rouvre à la
demande. Son journal d'événements reste : `seq` continue de croître pendant le lancement.
"""

from __future__ import annotations

import logging
import re
import secrets
import threading
from collections import OrderedDict
from collections.abc import Callable
from concurrent.futures import Future
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, get_args

from wavedevsecops.config import Settings
from wavedevsecops.contracts import AppError
from wavedevsecops.engine.fingerprint import fingerprint
from wavedevsecops.engine.operations import (
    SILENT_STATES,
    OpContext,
    Operation,
    OperationRefused,
    OpResult,
    Projection,
    Projector,
    Validator,
    WorkspaceEngine,
    no_validation,
)
from wavedevsecops.engine.watcher import TreeWatcher
from wavedevsecops.engine.workspace import prepare_workspace, resolve_git
from wavedevsecops.events import EngineStateName, EventLog, ExternalChange, Kind
from wavedevsecops.gitio import Git
from wavedevsecops.scenarios import LoadedScenario
from wavedevsecops.scenarios.model import KEBAB_PATTERN, Mode, Track
from wavedevsecops.wsfs import Layout

log = logging.getLogger("wavedevsecops")

_ID = re.compile(
    r"^(?P<track>{tracks})\.(?P<scenario_id>{kebab})\.(?P<mode>{modes})$".format(
        tracks="|".join(get_args(Track)),
        kebab=KEBAB_PATTERN.strip("^$"),
        modes="|".join(get_args(Mode)),
    )
)


class WorkspaceNotFound(AppError):
    """Identifiant d'espace invalide, ou espace pas encore préparé (404)."""

    def __init__(self, workspace_id: str) -> None:
        super().__init__(
            f"L'espace « {workspace_id} » n'existe pas.",
            "Ouvrez le scénario depuis l'accueil pour préparer son espace.",
        )


def workspace_id_for(track: str, scenario_key: str) -> str:
    """`workspace_id` de l'espace `<parcours>/<scenario_id>.<mode>`."""
    return f"{track}.{scenario_key}"


def parse_workspace_id(workspace_id: str) -> tuple[str, str, str]:
    """`(parcours, scenario_id, mode)` ; lève `WorkspaceNotFound` si l'identifiant est invalide."""
    match = _ID.match(workspace_id)
    if match is None:
        raise WorkspaceNotFound(workspace_id)
    return match["track"], match["scenario_id"], match["mode"]


def fingerprint_projector(settings: Settings, git_path: Path | None = None) -> Projector:
    """Projection de 2.2 : l'empreinte canonique (les vues arrivent avec `projections`)."""
    resolved: dict[str, Path] = {}

    def project(ctx: OpContext) -> Projection:
        if not (ctx.layout.repo / ".git").exists():
            return Projection({}, "")
        if "git" not in resolved:
            resolved["git"] = git_path or resolve_git(settings)
        git = Git.for_workspace(resolved["git"], ctx.layout.root, settings)
        return Projection({}, fingerprint(ctx.layout, git))

    return project


def external_change(engine: WorkspaceEngine, projector: Projector) -> Operation:
    """Opération « changement externe » : porte l'`epoch` de sa création (AD-1).

    La pré-vérification l'abandonne sans bruit si l'empreinte n'a pas changé depuis la
    dernière projection.
    """

    def precheck(ctx: OpContext) -> bool:
        projection = projector(ctx)
        ctx.data["fingerprint"] = projection.fingerprint
        return projection.fingerprint != ctx.last_fingerprint

    def body(ctx: OpContext) -> int:
        ctx.emit(Kind.EXTERNAL_CHANGE, ExternalChange(fingerprint=ctx.data["fingerprint"]))
        return 0

    return Operation(
        "external_change",
        body,
        epoch=engine.epoch,
        writes=False,
        precheck=precheck,
        reason_text="Mise à jour après une modification faite hors de l'application.",
    )


def setup_operation(
    loaded: LoadedScenario,
    track: str,
    settings: Settings,
    *,
    git_path: Path | None = None,
    replace: bool = False,
) -> Operation:
    """Opération de préparation de l'espace (état `setup`, nouvel `epoch`)."""

    def body(ctx: OpContext) -> int:
        ctx.output("Préparation de l'espace du scénario…", "app")
        prepare_workspace(loaded, track, settings=settings, git_path=git_path, replace=replace)
        ctx.output("L'espace est prêt.", "app")
        return 0

    return Operation("setup", body, state="setup", validate=False)


@dataclass
class _Active:
    engine: WorkspaceEngine
    watcher: Any = None
    watch_options: dict[str, Any] = field(default_factory=dict)


WatcherFactory = Callable[[Path, Callable[[], None]], Any]


class WorkspaceManager:
    """Registre des espaces : ouverture, veille, réveil ; un journal par espace et par lancement."""

    def __init__(
        self,
        settings: Settings,
        *,
        boot_id: str | None = None,
        projector: Projector | None = None,
        validator: Validator = no_validation,
        watcher_factory: WatcherFactory | None = None,
        watch: bool = True,
        git_path: Path | None = None,
    ) -> None:
        """`watch=False` : aucun surveillant (tests) ; `watcher_factory` remplace `TreeWatcher`."""
        self.settings = settings
        self.boot_id = boot_id or secrets.token_hex(8)
        self._git_path = git_path
        self._projector = projector or fingerprint_projector(settings, git_path)
        self._validator = validator
        if watch and watcher_factory is None:
            quiet_s = settings.watch_quiet_ms / 1000

            def watcher_factory(repo: Path, on_change: Callable[[], None]) -> TreeWatcher:
                return TreeWatcher(repo, on_change, quiet_s=quiet_s)

        self._watcher_factory = watcher_factory if watch else None
        self._lock = threading.RLock()
        self._active: OrderedDict[str, _Active] = OrderedDict()
        self._logs: dict[str, EventLog] = {}
        self._closed = False

    # ------------------------------------------------------------ lecture
    def layout(self, workspace_id: str) -> Layout:
        track, scenario_id, mode = parse_workspace_id(workspace_id)
        return Layout.for_scenario(self.settings.workspaces_path(), track, scenario_id, mode)

    def active_ids(self) -> list[str]:
        """Espaces actifs, du moins récent au plus récent."""
        with self._lock:
            return list(self._active)

    def events(self, workspace_id: str) -> EventLog:
        """Journal de l'espace (créé à la première demande d'un espace valide)."""
        parse_workspace_id(workspace_id)
        with self._lock:
            found = self._logs.get(workspace_id)
            if found is None:
                found = EventLog(workspace_id, self.boot_id, self.settings.event_buffer)
                self._logs[workspace_id] = found
            return found

    @property
    def closed(self) -> bool:
        return self._closed

    # ---------------------------------------------------- ouverture, veille
    def get(self, workspace_id: str) -> WorkspaceEngine:
        """File de l'espace, réveillé au besoin ; `WorkspaceNotFound` s'il n'existe pas."""
        layout = self.layout(workspace_id)
        with self._lock:
            active = self._active.get(workspace_id)
            if active is not None:
                self._active.move_to_end(workspace_id)
                return active.engine
            if not layout.root.is_dir():
                raise WorkspaceNotFound(workspace_id)
            engine, evicted = self._open(workspace_id, layout)
        self._sleep_all(evicted)
        return engine

    def create(
        self, loaded: LoadedScenario, track: str, *, replace: bool = False
    ) -> tuple[WorkspaceEngine, Future[OpResult]]:
        """Prépare l'espace de `loaded` pour `track` par une opération `setup` de sa file."""
        workspace_id = workspace_id_for(track, loaded.scenario.key)
        layout = self.layout(workspace_id)
        with self._lock:
            active = self._active.get(workspace_id)
            if active is not None:
                self._active.move_to_end(workspace_id)
                engine, evicted = active.engine, []
            else:
                engine, evicted = self._open(workspace_id, layout)
        self._sleep_all(evicted)
        op = setup_operation(loaded, track, self.settings, git_path=self._git_path, replace=replace)
        return engine, engine.submit(op)

    def _open(self, workspace_id: str, layout: Layout) -> tuple[WorkspaceEngine, list[_Active]]:
        if self._closed:
            raise OperationRefused("WaveDevSecOps s'arrête : l'espace ne peut plus être ouvert.")
        holder: dict[str, _Active] = {}

        def on_state(state: EngineStateName) -> None:
            active = holder.get("active")
            if active is not None:
                self._follow_state(active, state)

        engine = WorkspaceEngine(
            workspace_id,
            layout,
            self.events(workspace_id),
            self.settings,
            projector=self._projector,
            validator=self._validator,
            on_state=on_state,
        )
        active = _Active(engine)
        holder["active"] = active
        self._active[workspace_id] = active
        evicted = []
        while len(self._active) > self.settings.max_active_workspaces:
            _, oldest = self._active.popitem(last=False)
            evicted.append(oldest)
        engine.start()
        return engine, evicted

    def _follow_state(self, active: _Active, state: EngineStateName) -> None:
        """Suspend ou reprend le surveillant selon l'état (appelé par le fil de la file)."""
        if self._watcher_factory is None or active.engine.closed:
            return
        if state in SILENT_STATES:
            if active.watcher is not None:
                active.watcher.suspend()
            return
        if active.watcher is None:
            if not (active.engine.layout.repo / ".git").exists():
                return
            active.watcher = self._watcher_factory(
                active.engine.layout.repo, lambda: self._propose_external(active)
            )
            active.watcher.start()
        else:
            active.watcher.resume()

    def _propose_external(self, active: _Active) -> None:
        try:
            active.engine.submit(external_change(active.engine, self._projector))
        except OperationRefused as refused:
            log.info("Changement externe ignoré : %s", refused.reason_text)

    def _sleep_all(self, evicted: list[_Active]) -> None:
        for active in evicted:
            self._sleep(active)

    def _sleep(self, active: _Active) -> None:
        if active.watcher is not None:
            active.watcher.stop()
        active.engine.close()
        # Les runs du pipeline de l'espace s'arrêteront ici aussi (AD-10).

    def sleep(self, workspace_id: str) -> None:
        """Endort un espace actif (sans effet s'il dort déjà)."""
        with self._lock:
            active = self._active.pop(workspace_id, None)
        if active is not None:
            self._sleep(active)

    def close(self) -> None:
        """Endort tous les espaces : fin du lancement."""
        with self._lock:
            self._closed = True
            actives = list(self._active.values())
            self._active.clear()
        self._sleep_all(actives)
