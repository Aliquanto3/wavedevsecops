"""File d'opérations d'un espace : un seul écrivain, ordre fixe, `epoch` (AD-1, AD-17).

Chaque espace a un fil qui exécute ses opérations en série. Pour chacune, la file émet
toujours, dans cet ordre :

    engine_state(état de l'opération) → op_started → sortie (terminal_output…) → op_exit
    → state_projected → [step_verdict → step_explanation] → engine_state(repos)

Une opération n'émet jamais elle-même un `kind` de cette séquence (`SEQUENCE_KINDS`) :
seule la file publie une explication, après les projections et le verdict.
"""

from __future__ import annotations

import logging
import queue
import threading
import time
import uuid
from collections.abc import Callable
from concurrent.futures import Future
from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel

from wavedevsecops.config import Settings
from wavedevsecops.contracts import AppError
from wavedevsecops.engine.runfile import load_run, save_run
from wavedevsecops.events import (
    SEQUENCE_KINDS,
    AppErrorPayload,
    EngineState,
    EngineStateName,
    EventLog,
    Kind,
    OpExit,
    OpStarted,
    StateProjected,
    StepExplanation,
    StepVerdict,
    Stream,
    TerminalOutput,
)
from wavedevsecops.wsfs import Layout

log = logging.getLogger("wavedevsecops")

EPOCH_STATES: frozenset[EngineStateName] = frozenset({"restoring", "setup"})
"""États dont l'entrée incrémente l'`epoch` (AD-1)."""
SILENT_STATES: frozenset[EngineStateName] = frozenset({"command", "setup", "restoring"})
"""États pendant lesquels le surveillant de l'arbre est suspendu (AD-1)."""
REST_STATES: frozenset[EngineStateName] = frozenset({"idle", "quiz_altered"})
"""États de repos, entre deux opérations."""

GENERIC_CAUSE = "Une erreur inattendue a interrompu l'opération."
GENERIC_ACTION = (
    "Réessayez ; si l'erreur revient, ouvrez le diagnostic ou consultez le journal de "
    "WaveDevSecOps."
)
_STATE_TEXTS: dict[str, str] = {
    "idle": "",
    "command": "Une commande est en cours.",
    "setup": "Préparation de l'espace en cours.",
    "restoring": "Rétablissement de l'état en cours.",
    "exporting": "Export en cours.",
    "quiz_altered": "Le dépôt est dans l'état du quiz : seules les commandes de lecture passent.",
}


class OperationRefused(Exception):
    """Intention ou opération refusée : 409 avec `reason_text` en français (AD-17)."""

    def __init__(self, reason_text: str) -> None:
        super().__init__(reason_text)
        self.reason_text = reason_text


class StaleOperation(OperationRefused):
    """Opération produite hors de la file avec un `epoch` qui n'est plus le courant (AD-1)."""


@dataclass(frozen=True)
class Projection:
    views: dict[str, Any]
    fingerprint: str


@dataclass(frozen=True)
class StepOutcome:
    """Résultat de la validation d'étape : un verdict, puis son explication éventuelle."""

    verdict: StepVerdict
    explanation: StepExplanation | None = None


@dataclass(frozen=True)
class OpResult:
    op_id: str
    code: int | None
    projection: Projection | None


class OpContext:
    """Ce qu'une opération voit de son espace pendant qu'elle s'exécute."""

    def __init__(self, engine: WorkspaceEngine, op: Operation) -> None:
        self._engine = engine
        self.op = op
        self.op_id = op.op_id
        self.layout = engine.layout
        self.settings = engine.settings
        self.workspace_id = engine.workspace_id
        self.data: dict[str, Any] = {}
        """Valeurs partagées entre la pré-vérification et le corps de l'opération."""

    @property
    def epoch(self) -> int:
        return self._engine.epoch

    @property
    def last_fingerprint(self) -> str:
        return self._engine.last_projection.fingerprint

    def set_rest_state(self, state: EngineStateName) -> None:
        """État de repos après l'opération : `quiz_altered` (quiz) ou `idle` (rétablissement)."""
        self._engine.set_rest_state(state)

    def output(self, text: str, stream: Stream = "stdout", *, lang: str = "") -> None:
        """Émet une sortie de l'opération (`terminal_output`)."""
        self.emit(Kind.TERMINAL_OUTPUT, TerminalOutput(stream=stream, text=text, lang=lang))

    def emit(self, kind: Kind | str, payload: BaseModel | dict[str, Any]) -> None:
        """Émet un événement de l'opération ; les `kind` de la séquence sont réservés."""
        if Kind(kind) in SEQUENCE_KINDS:
            raise ValueError(f"« {kind} » est réservé à la file d'opérations")
        self._engine.publish(kind, payload, op_id=self.op_id)


OpBody = Callable[[OpContext], int | None]
Precheck = Callable[[OpContext], bool]
Projector = Callable[[OpContext], Projection]
Validator = Callable[[OpContext, Projection], StepOutcome | None]


def _new_op_id() -> str:
    return uuid.uuid4().hex[:16]


@dataclass(frozen=True)
class Operation:
    """Une opération typée de la file (AD-1, AD-17)."""

    intent: str
    """Nom de l'intention (`terminal_line`…) ou de l'opération interne (`external_change`)."""
    body: OpBody
    """Corps : émet sa sortie par le contexte et rend un code de sortie."""
    state: EngineStateName = "command"
    """État de l'espace pendant l'opération."""
    epoch: int | None = None
    """`epoch` de création d'une opération produite hors de la file ; `None` : intention."""
    writes: bool = True
    """Vrai si l'opération peut modifier l'espace : refusée en `quiz_altered` (AD-1)."""
    precheck: Precheck | None = None
    """Exécutée dans la file avant tout événement ; `False` : opération abandonnée sans bruit."""
    validate: bool = True
    """Faux : pas de validation d'étape (opérations internes)."""
    reason_text: str = ""
    """Texte de `engine_state` pendant l'opération ; vide : texte par défaut de l'état."""
    op_id: str = field(default_factory=_new_op_id)

    def __post_init__(self) -> None:
        if self.state in REST_STATES:
            raise ValueError(f"état de repos interdit pour une opération : {self.state}")


_STOP = object()


def no_projection(ctx: OpContext) -> Projection:
    return Projection({}, "")


def no_validation(ctx: OpContext, projection: Projection) -> StepOutcome | None:
    return None


class WorkspaceEngine:
    """File d'opérations d'un espace : seul écrivain de cet espace."""

    def __init__(
        self,
        workspace_id: str,
        layout: Layout,
        log_: EventLog,
        settings: Settings,
        *,
        projector: Projector = no_projection,
        validator: Validator = no_validation,
        on_state: Callable[[EngineStateName], None] | None = None,
    ) -> None:
        self.workspace_id = workspace_id
        self.layout = layout
        self.events = log_
        self.settings = settings
        self._projector = projector
        self._validator = validator
        self._on_state = on_state
        self._lock = threading.Lock()
        self._queue: queue.Queue[Any] = queue.Queue()
        self._pending: list[tuple[Operation, Future[OpResult]]] = []
        self._closed = False
        self._state: EngineStateName = "idle"
        self._rest: EngineStateName = "idle"
        self._reason_text = ""
        self.last_projection = Projection({}, "")
        self.epoch = self._read_epoch()
        self._thread = threading.Thread(
            target=self._run, name=f"wds-ops-{workspace_id}", daemon=True
        )

    # ------------------------------------------------------------------ état
    def _read_epoch(self) -> int:
        if not self.layout.run_json.exists():
            return 0
        epoch = load_run(self.layout).get("epoch", 0)
        return epoch if isinstance(epoch, int) and epoch >= 0 else 0

    def _persist_epoch(self) -> None:
        if not self.layout.run_json.exists():
            return
        data = load_run(self.layout)
        if data.get("epoch") != self.epoch:
            save_run(self.layout, {**data, "epoch": self.epoch})

    @property
    def state(self) -> EngineStateName:
        return self._state

    @property
    def reason_text(self) -> str:
        return self._reason_text

    @property
    def closed(self) -> bool:
        return self._closed

    def snapshot(self) -> dict[str, Any]:
        """État courant, pour `GET /api/ws/<id>/state`."""
        return {
            "workspace_id": self.workspace_id,
            "boot_id": self.events.boot_id,
            "seq": self.events.seq,
            "epoch": self.epoch,
            "state": self._state,
            "reason_text": self._reason_text,
            "fingerprint": self.last_projection.fingerprint,
            "views": self.last_projection.views,
        }

    def publish(self, kind: Kind | str, payload: BaseModel | dict[str, Any], *, op_id: str | None):
        return self.events.publish(kind, payload, epoch=self.epoch, op_id=op_id)

    def _set_state(self, state: EngineStateName, reason_text: str, op_id: str | None) -> None:
        self._state = state
        self._reason_text = reason_text or _STATE_TEXTS.get(state, "")
        self.publish(
            Kind.ENGINE_STATE,
            EngineState(state=state, reason_text=self._reason_text),
            op_id=op_id,
        )
        if self._on_state is not None:
            try:
                self._on_state(state)
            except Exception:  # noqa: BLE001 - le surveillant ne fait pas échouer la file
                log.exception("Rappel d'état de l'espace %s", self.workspace_id)

    def set_rest_state(self, state: EngineStateName) -> None:
        """Fixe l'état de repos (`idle` ou `quiz_altered`) ; appelé depuis une opération."""
        if state not in REST_STATES:
            raise ValueError(f"« {state} » n'est pas un état de repos")
        self._rest = state

    # ---------------------------------------------------------------- file
    def start(self) -> None:
        self._thread.start()

    def submit(self, op: Operation) -> Future[OpResult]:
        """Place `op` dans la file ; lève `OperationRefused` (409) si elle est refusée."""
        with self._lock:
            if self._closed:
                raise OperationRefused(
                    "Cet espace vient de se mettre en veille : l'action n'a pas été faite. "
                    "Réessayez."
                )
            self._check_epoch(op)
            if op.writes and self._rest == "quiz_altered":
                raise OperationRefused(_STATE_TEXTS["quiz_altered"])
            if len(self._pending) >= self.settings.max_pending_ops:
                raise OperationRefused(
                    "Trop d'actions sont en attente dans cet espace. Attendez la fin des "
                    "actions en cours, puis réessayez."
                )
            future: Future[OpResult] = Future()
            self._pending.append((op, future))
            self._queue.put((op, future))
            return future

    def _check_epoch(self, op: Operation) -> None:
        if op.epoch is not None and op.epoch != self.epoch:
            raise StaleOperation(
                "Ce résultat concerne un état de l'espace qui a été remplacé : il est ignoré."
            )

    def close(self) -> None:
        """Met l'espace en veille : refuse les opérations en attente, attend celle en cours."""
        with self._lock:
            if self._closed:
                return
            self._closed = True
            dropped = list(self._pending)
            self._pending.clear()
        for _, future in dropped:
            if future.set_running_or_notify_cancel():
                future.set_exception(
                    OperationRefused(
                        "Cet espace s'est mis en veille avant d'exécuter l'action. Réessayez."
                    )
                )
        self._queue.put(_STOP)
        if self._thread.is_alive() and threading.current_thread() is not self._thread:
            self._thread.join(timeout=self.settings.engine_stop_timeout_s)

    def join(self, timeout: float | None = None) -> None:
        self._thread.join(timeout)

    def _run(self) -> None:
        self._initial_projection()
        while True:
            item = self._queue.get()
            if item is _STOP:
                return
            op, future = item
            with self._lock:
                if (op, future) not in self._pending:
                    continue  # refusée à la mise en veille
                self._pending.remove((op, future))
            if not future.set_running_or_notify_cancel():
                continue
            try:
                future.set_result(self._execute(op))
            except OperationRefused as refused:
                future.set_exception(refused)
            except BaseException as exc:  # noqa: BLE001 - la file survit à tout
                log.exception("Opération %s en échec dans %s", op.intent, self.workspace_id)
                future.set_exception(exc)

    def _initial_projection(self) -> None:
        """Projection d'ouverture : l'état réel est relu avant la première opération."""
        ctx = OpContext(self, Operation("open", lambda _ctx: 0, writes=False, validate=False))
        try:
            self.last_projection = self._projector(ctx)
        except Exception:  # noqa: BLE001 - un espace illisible reste ouvrable
            log.exception("Projection d'ouverture de %s", self.workspace_id)
        self.publish(
            Kind.STATE_PROJECTED,
            StateProjected(
                views=self.last_projection.views, fingerprint=self.last_projection.fingerprint
            ),
            op_id=None,
        )
        self._set_state(self._rest, "", None)

    def _fail(self, ctx: OpContext, cause_text: str, action_text: str) -> None:
        self.publish(
            Kind.APP_ERROR,
            AppErrorPayload(cause_text=cause_text, action_text=action_text),
            op_id=ctx.op_id,
        )

    def _guarded(self, ctx: OpContext, what: str, call: Callable[[], Any]) -> tuple[bool, Any]:
        """Appelle `call` ; une exception devient un `app_error`, jamais une trace (NFR-7)."""
        try:
            return True, call()
        except AppError as error:
            self._fail(ctx, error.cause_text, error.action_text)
        except Exception:  # noqa: BLE001 - jamais de trace Python montrée à l'apprenant
            log.exception("%s de %s (%s)", what, ctx.op.intent, self.workspace_id)
            self._fail(ctx, GENERIC_CAUSE, GENERIC_ACTION)
        return False, None

    def _execute(self, op: Operation) -> OpResult:
        # L'epoch est revérifié à l'exécution : un Recommencer passé devant l'a peut-être changé.
        self._check_epoch(op)
        ctx = OpContext(self, op)
        if op.precheck is not None:
            try:
                wanted = op.precheck(ctx)
            except Exception:  # noqa: BLE001 - une pré-vérification en échec abandonne l'opération
                log.exception("Pré-vérification de %s (%s)", op.intent, self.workspace_id)
                wanted = False
            if not wanted:
                return OpResult(op.op_id, None, None)
        if op.state in EPOCH_STATES:
            self.epoch += 1
        self._set_state(op.state, op.reason_text, op.op_id)
        try:
            self.publish(Kind.OP_STARTED, OpStarted(intent=op.intent), op_id=op.op_id)
            started = time.monotonic()
            ok, code = self._guarded(ctx, "Corps", lambda: op.body(ctx))
            if op.state in EPOCH_STATES:
                self._guarded(ctx, "Epoch", self._persist_epoch)
            self.publish(
                Kind.OP_EXIT,
                OpExit(
                    code=code if ok else None,
                    duration_ms=int((time.monotonic() - started) * 1000),
                ),
                op_id=op.op_id,
            )
            projected, projection = self._guarded(ctx, "Projection", lambda: self._projector(ctx))
            if not projected:
                return OpResult(op.op_id, code if ok else None, None)
            self.last_projection = projection
            self.publish(
                Kind.STATE_PROJECTED,
                StateProjected(views=projection.views, fingerprint=projection.fingerprint),
                op_id=op.op_id,
            )
            if ok and op.validate:
                checked, outcome = self._guarded(
                    ctx, "Validation", lambda: self._validator(ctx, projection)
                )
                if checked and outcome is not None:
                    self.publish(Kind.STEP_VERDICT, outcome.verdict, op_id=op.op_id)
                    if outcome.explanation is not None:
                        self.publish(Kind.STEP_EXPLANATION, outcome.explanation, op_id=op.op_id)
            return OpResult(op.op_id, code if ok else None, projection)
        finally:
            self._set_state(self._rest, "", op.op_id)
