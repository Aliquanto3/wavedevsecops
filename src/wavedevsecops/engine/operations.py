"""File d'opérations d'un espace : un seul écrivain, ordre fixe, `epoch` (AD-1, AD-17).

Chaque espace a un fil qui exécute ses opérations en série. Pour chacune, la file émet
toujours, dans cet ordre :

    engine_state(état de l'opération) → op_started → sortie (terminal_output…) → op_exit
    → state_projected → [step_verdict → step_explanation → progress_updated]
    → engine_state(repos)

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
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from wavedevsecops.config import Settings
from wavedevsecops.contracts import AppError
from wavedevsecops.contracts.views import EXPLAIN_TOOL_OUTPUT
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
from wavedevsecops.events.catalog import ProgressUpdated
from wavedevsecops.progress.facts import Fact, ProgressStore
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
DROPPED_TEXT = "Cet espace s'est mis en veille avant d'exécuter l'action."
DROPPED_ACTION = "Réessayez l'action : l'espace se rouvre à la demande."
_STATE_TEXTS: dict[str, str] = {
    "idle": "",
    "command": "Une commande est en cours.",
    "setup": "Préparation de l'espace en cours.",
    "restoring": "Rétablissement de l'état en cours.",
    "exporting": "Export en cours.",
    "quiz_altered": "Le dépôt est dans l'état du quiz : seules les commandes de lecture passent.",
}
QUIZ_REFUSED_TEXT = (
    "Refusée pendant l'état modifié par le quiz : seules les commandes de lecture passent. "
    "Cliquez sur « J'ai compris, rétablir l'état » pour reprendre."
)
RESTORE_FAILED_TEXT = (
    "L'état n'a pas pu être rétabli : cette action est refusée pour ne pas vous laisser sur un "
    "état faux. Recommencez le scénario."
)
REFUSED_IN_QUEUE_ACTION = "L'action n'a pas été faite. Relisez l'état de l'espace, puis réessayez."
RESTART_INTENT = "restart"
"""Seule intention d'écriture admise après un rétablissement échoué (story 4.4)."""


class OperationRefused(Exception):
    """Intention ou opération refusée : 409 avec `reason_text` en français (AD-17)."""

    def __init__(self, reason_text: str) -> None:
        super().__init__(reason_text)
        self.reason_text = reason_text


class StaleOperation(OperationRefused):
    """Opération produite hors de la file avec un `epoch` qui n'est plus le courant (AD-1)."""


SpanLinker = Callable[[str], list[dict[str, Any]]]
"""Passages liables d'un texte de sortie, résolus contre l'état projeté (AD-2)."""


@dataclass(frozen=True)
class Projection:
    views: dict[str, Any]
    fingerprint: str
    linker: SpanLinker | None = field(default=None, compare=False)
    """Résolveur des `spans` des sorties ; `None` : aucune sortie n'est liable."""


@dataclass(frozen=True)
class StepOutcome:
    """Résultat de la validation d'étape : un verdict, puis son explication éventuelle."""

    verdict: StepVerdict
    explanation: StepExplanation | None = None
    facts: tuple[dict[str, Any], ...] = ()
    """Faits du premier passage que le verdict produit (`kind`, `step_id`, …) : la file les
    complète (clé d'idempotence) et les soumet à `progress` après `run.json` (AD-14)."""
    views: dict[str, Any] | None = None
    """Vues re-marquées pour l'étape suivante (`designable`, story 5.2) : la file les republie
    dans un dernier `state_projected` ; `None` : les vues publiées restent valables."""

    @classmethod
    def explained(
        cls, verdict: StepVerdict, explanation_text: str, explain_ref: str = ""
    ) -> StepOutcome:
        """Verdict suivi de l'explication de son étape (publiée par la file, après le verdict)."""
        explanation = StepExplanation(
            step_id=verdict.step_id, explanation_text=explanation_text, explain_ref=explain_ref
        )
        return cls(verdict, explanation)


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
        self.git_path = engine.git_path
        """git du registre si l'application l'a déjà résolu ; `None` : à résoudre."""
        self.interrupted = False
        self._interrupt_lock = threading.Lock()
        self._on_interrupt: Callable[[], None] | None = None
        self.workspace_id = engine.workspace_id
        self.before_views: dict[str, Any] = engine.last_projection.views
        """Vues projetées avant l'opération : la validation d'étape les compare au nouvel état."""
        self.data: dict[str, Any] = {}
        """Valeurs partagées entre la pré-vérification et le corps de l'opération."""
        self.outputs: list[tuple[int, str, list[dict[str, Any]]]] = []
        """Sorties émises par `output` : `(seq, texte, spans)`, relues après la projection."""

    @property
    def epoch(self) -> int:
        return self._engine.epoch

    @property
    def last_fingerprint(self) -> str:
        return self._engine.last_projection.fingerprint

    @property
    def last_views(self) -> dict[str, Any]:
        """Vues de la dernière projection publiée (l'état d'avant l'opération)."""
        return self._engine.last_projection.views

    def set_rest_state(self, state: EngineStateName) -> None:
        """État de repos après l'opération : `quiz_altered` (quiz) ou `idle` (rétablissement)."""
        self._engine.set_rest_state(state)

    def submit_facts(self, drafts: list[dict[str, Any]]) -> None:
        """Soumet des faits du premier passage à `progress`, après l'écriture de `run.json`."""
        self._engine.submit_facts(drafts, self.op_id)

    def output(
        self,
        text: str,
        stream: Stream = "stdout",
        *,
        lang: str = "",
        tool: str = "",
        spans: list[dict[str, Any]] | None = None,
    ) -> None:
        """Émet une sortie de l'opération (`terminal_output`).

        Ses `spans` sont résolus contre le dernier état projeté ; après l'opération,
        `state_projected.output_spans` donne ceux qui changent avec le nouvel état.
        `tool` : la sortie est celle d'un outil (bloc `tool-output`). `spans` explicites
        (liens tirés d'une exécution machine, AD-10) : fixés, jamais recalculés.
        """
        linker = self._engine.last_projection.linker
        fixed = spans is not None
        resolved = spans if spans is not None else (linker(text) if linker is not None else [])
        envelope = self._engine.publish(
            Kind.TERMINAL_OUTPUT,
            TerminalOutput(
                stream=stream,
                text=text,
                lang=lang,
                spans=resolved,  # type: ignore[arg-type]
                tool=tool,
                explain_ref=EXPLAIN_TOOL_OUTPUT if tool else "",
            ),
            op_id=self.op_id,
        )
        if not fixed:
            self.outputs.append((envelope.seq, text, resolved))

    def submit_evidence(self, barrier_id: str) -> None:
        """Soumet à `progress` le fait `evidence_seen{barrier_id}` : la preuve s'affiche (AD-14)."""
        self._engine.submit_evidence(barrier_id, self.op_id)

    def emit(self, kind: Kind | str, payload: BaseModel | dict[str, Any]) -> None:
        """Émet un événement de l'opération ; les `kind` de la séquence sont réservés."""
        if Kind(kind) in SEQUENCE_KINDS:
            raise ValueError(f"« {kind} » est réservé à la file d'opérations")
        self._engine.publish(kind, payload, op_id=self.op_id)

    def on_interrupt(self, callback: Callable[[], None]) -> None:
        """Déclare comment arrêter l'opération (Ctrl+C, mise en veille) : arrêt d'arbre, etc.

        Si l'interruption a déjà été demandée, `callback` est appelé aussitôt.
        """
        with self._interrupt_lock:
            self._on_interrupt = callback
            pending = self.interrupted
        if pending:
            callback()

    def interrupt(self) -> bool:
        """Demande l'arrêt de l'opération ; rend faux si elle ne sait pas s'arrêter."""
        with self._interrupt_lock:
            self.interrupted = True
            callback = self._on_interrupt
        if callback is None:
            return False
        callback()
        return True


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
        git_path: Path | None = None,
        panel: Callable[[WorkspaceEngine], dict[str, Any] | None] | None = None,
        progress: ProgressStore | None = None,
        replay: Callable[[WorkspaceEngine], list[dict[str, Any]]] | None = None,
    ) -> None:
        """`progress` reçoit les faits du premier passage ; `replay` rend, au démarrage, ceux que
        `run.json` établit déjà (les doublons sont ignorés : seuls les manquants s'ajoutent)."""
        self.workspace_id = workspace_id
        self.git_path = git_path
        self._current: OpContext | None = None
        self.layout = layout
        self.events = log_
        self.settings = settings
        self._projector = projector
        self._validator = validator
        self._on_state = on_state
        self._panel = panel
        self._progress = progress
        self._replay = replay
        self._lock = threading.Lock()
        self._queue: queue.Queue[Any] = queue.Queue()
        self._pending: list[tuple[Operation, Future[OpResult]]] = []
        self._closed = False
        self._state: EngineStateName = "idle"
        self._rest: EngineStateName = self._read_rest()
        self._reason_text = ""
        self.last_projection = Projection({}, "")
        self.epoch = self._read_epoch()
        self.after_op: Callable[[], None] | None = None
        """Appelé par le fil de la file après chaque opération et après la projection
        d'ouverture, au repos : le pipeline simulé y relit les PR à faire tourner (AD-10)."""
        self._thread = threading.Thread(
            target=self._run, name=f"wds-ops-{workspace_id}", daemon=True
        )

    # ------------------------------------------------------------------ état
    def _read_epoch(self) -> int:
        if not self.layout.run_json.exists():
            return 0
        epoch = load_run(self.layout).get("epoch", 0)
        return epoch if isinstance(epoch, int) and epoch >= 0 else 0

    def _read_rest(self) -> EngineStateName:
        """`quiz_altered` si un quiz attend son rétablissement (`run.json.quiz`), sinon `idle`."""
        if not self.layout.run_json.exists():
            return "idle"
        try:
            return "quiz_altered" if load_run(self.layout).get("quiz") else "idle"
        except AppError:
            return "idle"

    def _restore_failed(self) -> bool:
        if not self.layout.run_json.exists():
            return False
        try:
            return bool(load_run(self.layout).get("restore_failed"))
        except AppError:
            return False

    @property
    def rest_state(self) -> EngineStateName:
        """État de repos : `idle` ou `quiz_altered`."""
        return self._rest

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
            "step_panel": self._step_panel(),
        }

    def _step_panel(self) -> dict[str, Any] | None:
        """Panneau Scénario (titre, étapes, étape courante) écrit par le serveur (AD-2)."""
        if self._panel is None:
            return None
        try:
            return self._panel(self)
        except Exception:  # noqa: BLE001 - un panneau illisible ne bloque pas la lecture de l'état
            log.exception("Panneau Scénario de %s", self.workspace_id)
            return None

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
            refusal = self._write_refusal(op)
            if refusal:
                raise OperationRefused(refusal)
            if len(self._pending) >= self.settings.max_pending_ops:
                raise OperationRefused(
                    "Trop d'actions sont en attente dans cet espace. Attendez la fin des "
                    "actions en cours, puis réessayez."
                )
            future: Future[OpResult] = Future()
            self._pending.append((op, future))
            self._queue.put((op, future))
            return future

    def _write_refusal(self, op: Operation) -> str:
        """Texte du refus d'une écriture (`restore_failed`, `quiz_altered`), vide si admise.

        Vérifié à la soumission et de nouveau à l'exécution : une écriture placée dans la file
        avant qu'un choix de quiz ou un rétablissement échoué ne change l'état ne passe pas.
        « Recommencer » (`restart`) et l'installation restent admises : elles reconstruisent.
        """
        if not op.writes or op.state == "setup" or op.intent == RESTART_INTENT:
            return ""
        if self._restore_failed():
            return RESTORE_FAILED_TEXT
        if self._rest == "quiz_altered":
            return QUIZ_REFUSED_TEXT
        return ""

    def _check_epoch(self, op: Operation) -> None:
        if op.epoch is not None and op.epoch != self.epoch:
            raise StaleOperation(
                "Ce résultat concerne un état de l'espace qui a été remplacé : il est ignoré."
            )

    @property
    def alive(self) -> bool:
        """Vrai tant que le fil de la file tourne (une opération peut encore écrire)."""
        return self._thread.is_alive()

    @property
    def busy(self) -> bool:
        """Vrai si une opération tourne ou attend."""
        with self._lock:
            return bool(self._pending) or self._state not in REST_STATES

    def interrupt(self) -> bool:
        """Arrête l'opération en cours si elle sait s'arrêter (Ctrl+C), hors de la file (AD-17)."""
        with self._lock:
            ctx = self._current
        return ctx.interrupt() if ctx is not None else False

    def request_stop(self) -> None:
        """Met l'espace en veille sans attendre : refuse les opérations en attente.

        Leur `app_error` est publié par le fil de la file (seul écrivain), après
        l'opération en cours, que la veille interrompt (arrêt d'arbre) si elle sait s'arrêter.
        """
        with self._lock:
            if self._closed:
                return
            self._closed = True
            dropped = list(self._pending)
            self._pending.clear()
            current = self._current
        for _, future in dropped:
            if future.set_running_or_notify_cancel():
                future.set_exception(OperationRefused(DROPPED_TEXT))
        if current is not None:
            current.interrupt()
        self._queue.put(_STOP)

    def close(self) -> None:
        """Met l'espace en veille : refuse les opérations en attente, attend celle en cours."""
        self.request_stop()
        self.join(self.settings.engine_stop_timeout_s)

    def join(self, timeout: float | None = None) -> None:
        if self._thread.is_alive() and threading.current_thread() is not self._thread:
            self._thread.join(timeout)

    def _run(self) -> None:
        self._replay_facts()
        self._initial_projection()
        while True:
            item = self._queue.get()
            if item is _STOP:
                return
            op, future = item
            with self._lock:
                dropped = (op, future) not in self._pending
                if not dropped:
                    self._pending.remove((op, future))
            if dropped:
                # Refusée à la mise en veille : l'apprenant a reçu un 202, il voit pourquoi.
                self.publish(
                    Kind.APP_ERROR,
                    AppErrorPayload(cause_text=DROPPED_TEXT, action_text=DROPPED_ACTION),
                    op_id=op.op_id,
                )
                continue
            if not future.set_running_or_notify_cancel():
                continue
            try:
                future.set_result(self._execute(op))
            except OperationRefused as refused:
                future.set_exception(refused)
            except BaseException as exc:  # noqa: BLE001 - la file survit à tout
                log.exception("Opération %s en échec dans %s", op.intent, self.workspace_id)
                future.set_exception(exc)

    def submit_facts(self, drafts: list[dict[str, Any]], op_id: str | None) -> None:
        """Soumission des faits par une opération qui en produit hors d'un verdict (indices)."""
        try:
            self._submit_facts(drafts, op_id)
        except Exception:  # noqa: BLE001 - un suivi illisible ne bloque pas l'opération
            log.exception("Faits de %s", self.workspace_id)

    def _submit_facts(self, drafts: list[dict[str, Any]], op_id: str | None) -> None:
        """Soumet les faits à `progress` (après `run.json`) ; `progress_updated` si du neuf."""
        if self._progress is None or not drafts:
            return
        key = {"workspace_id": self.workspace_id, "epoch": self.epoch, "op_id": op_id or "replay"}
        added = self._progress.submit([Fact(**draft, **key) for draft in drafts])
        if added:
            first = added[0]
            self.publish(
                Kind.PROGRESS_UPDATED,
                ProgressUpdated(
                    track=first.track,
                    scenario_id=first.scenario_id,
                    mode=first.mode,
                    facts=[f.kind for f in added],
                    step_ids=[f.step_id for f in added if f.step_id],
                ),
                op_id=op_id,
            )

    def submit_evidence(self, barrier_id: str, op_id: str | None) -> None:
        """`evidence_seen` du scénario de l'espace (premier passage seulement, AD-14)."""
        if not self.layout.run_json.exists():
            return
        run = load_run(self.layout)
        where = {
            "track": run.get("track"),
            "scenario_id": run.get("scenario_id"),
            "mode": run.get("mode"),
        }
        draft = {"kind": "evidence_seen", "barrier_id": barrier_id, **where}
        self._submit_facts([draft], op_id)

    def _replay_facts(self) -> None:
        """Reprise après un arrêt brutal : `run.json` est écrit avant les faits (AD-14)."""
        if self._replay is None or self._progress is None or not self.layout.run_json.exists():
            return
        try:
            self._submit_facts(self._replay(self), None)
        except Exception:  # noqa: BLE001 - un suivi illisible ne bloque pas l'ouverture
            log.exception("Rejeu des faits de %s", self.workspace_id)

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
        self._run_after_op()

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

    @staticmethod
    def _relinked(ctx: OpContext, projection: Projection) -> list[dict[str, Any]]:
        """Sorties de l'opération dont les passages liables changent avec le nouvel état."""
        if projection.linker is None:
            return []
        changed = []
        for seq, text, spans in ctx.outputs:
            fresh = projection.linker(text)
            if fresh != spans:
                changed.append({"seq": seq, "spans": fresh})
        return changed

    def _execute(self, op: Operation) -> OpResult:
        # L'epoch est revérifié à l'exécution : un Recommencer passé devant l'a peut-être changé.
        self._check_epoch(op)
        ctx = OpContext(self, op)
        refusal = self._write_refusal(op)
        if refusal:
            self._fail(ctx, refusal, REFUSED_IN_QUEUE_ACTION)
            return OpResult(op.op_id, None, None)
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
        with self._lock:
            self._current = ctx
        try:
            self.publish(Kind.OP_STARTED, OpStarted(intent=op.intent), op_id=op.op_id)
            started = time.monotonic()
            ok, code = self._guarded(ctx, "Corps", lambda: op.body(ctx))
            with self._lock:
                self._current = None  # le corps est fini : plus rien à interrompre
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
                StateProjected(
                    views=projection.views,
                    fingerprint=projection.fingerprint,
                    output_spans=self._relinked(ctx, projection),  # type: ignore[arg-type]
                ),
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
                    self._guarded(
                        ctx,
                        "Progression",
                        lambda: self._submit_facts(list(outcome.facts), op.op_id),
                    )
                    if outcome.views is not None:
                        projection = replace(projection, views=outcome.views)
                        self.last_projection = projection
                        self.publish(
                            Kind.STATE_PROJECTED,
                            StateProjected(
                                views=projection.views, fingerprint=projection.fingerprint
                            ),
                            op_id=op.op_id,
                        )
            return OpResult(op.op_id, code if ok else None, projection)
        finally:
            with self._lock:
                self._current = None
            self._set_state(self._rest, "", op.op_id)
            self._run_after_op()

    def _run_after_op(self) -> None:
        if self.after_op is None:
            return
        try:
            self.after_op()
        except Exception:  # noqa: BLE001 - le pipeline ne fait pas échouer la file
            log.exception("Après l'opération dans %s", self.workspace_id)
