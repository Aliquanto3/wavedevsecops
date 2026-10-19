"""Le pipeline simulé d'un espace : runs liés au SHA, un run actif, résultats par la file
(AD-1, AD-8, AD-10).

Après chaque opération (et à l'ouverture), le fil de la file appelle `PipelineRunner.scan` :
si le scénario déclare `pipeline: true`, chaque PR ouverte dont un check du pipeline manque ou
est `queued`/`running` pour ses SHA courants demande un run de clé `(pr, head_sha, base_sha)`
et `epoch`. Un seul run actif par espace, les autres attendent en file ; un nouveau SHA de la
même PR annule le run en cours (`Handle.terminate`, donc `procs.terminate_tree`).

Le fil du runner clone, prépare l'environnement et lance les jobs en série (`ci`). Chaque
changement d'état d'un check (`running`, puis le résultat) est une opération de la file qui
porte l'`epoch` du run : seule elle écrit `github.json` (`github_sim.set_check_state`) et émet
`check_updated`. Un résultat tardif (autre `epoch`, autres SHA) est rejeté.
"""

from __future__ import annotations

import logging
import threading
import time
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from wavedevsecops import ci, github_sim
from wavedevsecops.config import Settings
from wavedevsecops.contracts.github import JOB_ID_PATTERN, PullRequest
from wavedevsecops.engine.intents import INTENTS, Intent, register_intent
from wavedevsecops.engine.operations import (
    OpContext,
    Operation,
    OperationRefused,
    WorkspaceEngine,
)
from wavedevsecops.engine.pr_intents import announce
from wavedevsecops.engine.runfile import load_run
from wavedevsecops.engine.workspace import resolve_git
from wavedevsecops.events import Kind
from wavedevsecops.github_sim import GithubSimError, StaleCheck
from wavedevsecops.gitio import Git, GitError

log = logging.getLogger("wavedevsecops")

PENDING_STATES = frozenset({"queued", "running"})
STOP_WAIT_S = 10.0
"""Attente maximale de l'arrêt du run en cours (annulation, Recommencer, mise en veille)."""
PIPELINE_OFF_TEXT = "Le pipeline simulé ne tourne pas dans ce scénario."
INTERNAL_ERROR_TEXT = "n'a pas pu tourner : le pipeline simulé a rencontré une erreur interne"

RunKey = tuple[int, str, str]
"""`(pr, head_sha, base_sha)`."""


@dataclass
class Run:
    """Un run : sa clé, son `epoch` et ses jobs (dans l'ordre du pipeline)."""

    number: int
    head_sha: str
    base_sha: str
    epoch: int
    todo: deque[str] = field(default_factory=deque)
    current: str | None = None
    awaiting: set[str] = field(default_factory=set)
    """Jobs dont le résultat est soumis à la file mais pas encore écrit."""
    cancelled: bool = False
    done: bool = False
    handle: Any = None
    started: float = 0.0
    duration_ms: int | None = None
    states: dict[str, str] = field(default_factory=dict)

    @property
    def key(self) -> RunKey:
        return (self.number, self.head_sha, self.base_sha)

    def matches(self, key: RunKey, epoch: int) -> bool:
        return self.key == key and self.epoch == epoch

    @property
    def settled(self) -> bool:
        """Fini et tous ses résultats écrits (ou rejetés) par la file."""
        return self.done and not self.awaiting


def pending_jobs(pr: PullRequest, job_ids: list[str]) -> list[str]:
    """Jobs du pipeline à faire tourner pour les SHA courants de la PR."""
    checks = {c.job_id: c for c in pr.checks}
    pending = []
    for job in job_ids:
        check = checks.get(job)
        if (
            check is None
            or check.state in PENDING_STATES
            or (check.head_sha, check.base_sha) != (pr.head_sha, pr.base_sha)
        ):
            pending.append(job)
    return pending


class PipelineRunner:
    """Runs du pipeline simulé d'un espace : un fil, un run actif, une file de runs."""

    def __init__(
        self,
        engine: WorkspaceEngine,
        settings: Settings,
        *,
        enabled: Callable[[], bool],
        git_path: Callable[[], Path],
        osv_url: str = "",
    ) -> None:
        self.engine = engine
        self.settings = settings
        self._enabled = enabled
        self._git_path = git_path
        self._osv_url = osv_url
        self._lock = threading.Condition()
        self._queue: deque[Run] = deque()
        self._inflight: list[Run] = []
        """Runs pas encore réglés : l'actif, et les finis dont un résultat attend la file."""
        self._active: Run | None = None
        self._stopped = False
        self._thread: threading.Thread | None = None
        self.history: deque[Run] = deque(maxlen=20)
        """Derniers runs terminés (clé, états, `duration_ms`) : suivi à part de l'état (AD-1)."""

    # ------------------------------------------------------------ lecture des PR (file)
    def scan(self) -> None:
        """Fil de la file, au repos : demande un run pour chaque PR qui en attend un."""
        if self._stopped or not self._enabled():
            return
        try:
            pipeline = ci.load_pipeline(self.settings)
            state = github_sim.load(self.engine.layout)
        except (ci.PipelineError, GithubSimError) as error:
            log.warning("Pipeline de %s illisible : %s", self.engine.workspace_id, error)
            return
        open_pulls = {p.number: p for p in state.pulls if p.state == "open"}
        epoch = self.engine.epoch
        with self._lock:
            # Une PR fermée, mergée ou poussée à nouveau : ses runs dépassés sont annulés.
            for run in [*self._inflight, *self._queue]:
                pr = open_pulls.get(run.number)
                current = pr is not None and (pr.head_sha, pr.base_sha) == run.key[1:]
                if not current or run.epoch != epoch:
                    self._cancel(run)
            for pr in open_pulls.values():
                pending = pending_jobs(pr, pipeline.job_ids)
                if pending:
                    self._request((pr.number, pr.head_sha, pr.base_sha), epoch, pending)
            self._inflight = [r for r in self._inflight if not r.settled and not r.cancelled]
            self._lock.notify_all()

    def _request(self, key: RunKey, epoch: int, jobs: list[str]) -> None:
        """Sous le verrou : ajoute les jobs à un run de même clé, sinon met un run en file."""
        for run in [*self._inflight, *self._queue]:
            if not run.matches(key, epoch) or run.cancelled:
                continue
            known = set(run.todo) | run.awaiting | ({run.current} if run.current else set())
            if not run.done:
                run.todo.extend(job for job in jobs if job not in known)
                return
            jobs = [job for job in jobs if job not in known]
        if jobs:
            self._queue.append(Run(*key, epoch=epoch, todo=deque(jobs)))
            self._ensure_thread()

    def _cancel(self, run: Run) -> None:
        """Sous le verrou : annule un run (arrêt de l'arbre de l'outil en cours)."""
        if run.cancelled:
            return
        run.cancelled = True
        if run in self._queue:
            self._queue.remove(run)
        handle = run.handle
        if handle is not None:
            handle.terminate()

    def cancel_all(self, *, wait: bool = True) -> None:
        """Annule tous les runs (Recommencer, rétablissement, mise en veille) ; attend au plus
        `STOP_WAIT_S` que l'outil en cours soit arrêté (`ci/` peut alors être vidé)."""
        with self._lock:
            for run in [*self._inflight, *self._queue]:
                self._cancel(run)
            self._queue.clear()
            self._inflight.clear()
            deadline = time.monotonic() + STOP_WAIT_S
            while wait and self._active is not None and time.monotonic() < deadline:
                self._lock.wait(0.05)

    def stop(self) -> None:
        """Arrête le runner (mise en veille de l'espace)."""
        with self._lock:
            self._stopped = True
            self._lock.notify_all()
        self.cancel_all()

    @property
    def busy(self) -> bool:
        with self._lock:
            return self._active is not None or bool(self._queue)

    def _ensure_thread(self) -> None:
        if self._thread is None or not self._thread.is_alive():
            self._thread = threading.Thread(
                target=self._loop, name=f"wds-ci-{self.engine.workspace_id}", daemon=True
            )
            self._thread.start()

    # ------------------------------------------------------------ fil du runner
    def _loop(self) -> None:
        while True:
            with self._lock:
                while not self._queue and not self._stopped:
                    self._lock.wait(1.0)
                if self._stopped:
                    return
                run = self._queue.popleft()
                self._active = run
                self._inflight.append(run)
            try:
                self._execute(run)
            except Exception:  # noqa: BLE001 - un run en échec ne tue pas le runner
                log.exception("Run du pipeline de %s", self.engine.workspace_id)
                self._fail_remaining(run)
            finally:
                with self._lock:
                    run.done = True
                    run.handle = None
                    self._active = None
                    self.history.append(run)
                    self._lock.notify_all()

    def _fail_remaining(self, run: Run) -> None:
        """Après une erreur interne du run : ses jobs non écrits passent en erreur de l'outil.

        Les checks atteignent ainsi un état terminal (« Relancer le check » possible) au lieu de
        rester `queued`/`running` sans run pour les faire avancer.
        """
        with self._lock:
            if run.cancelled:
                return
            jobs = [*([run.current] if run.current else []), *run.todo]
            run.todo.clear()
            run.current = None
            run.done = True  # un job demandé ensuite part dans un nouveau run
        try:
            pipeline = ci.load_pipeline(self.settings)
        except ci.PipelineError:
            return
        ensure: ci.Pipeline | None = pipeline
        for job_id in jobs:
            job = pipeline.job(job_id)
            if job is None:
                continue
            result = ci.error_result(job, INTERNAL_ERROR_TEXT)
            if not self._submit(run, job_id, result=result, ensure=ensure):
                return
            ensure = None

    def covers(self, number: int, head_sha: str, base_sha: str, job_id: str) -> bool:
        """Vrai si un run vivant de l'`epoch` courant fera avancer ce check."""
        key = (number, head_sha, base_sha)
        epoch = self.engine.epoch
        with self._lock:
            for run in [*self._inflight, *self._queue]:
                if run.cancelled or not run.matches(key, epoch):
                    continue
                if job_id in run.todo or job_id in run.awaiting or job_id == run.current:
                    return True
        return False

    def _attach(self, run: Run, handle: Any) -> None:
        with self._lock:
            run.handle = handle
            if run.cancelled:
                handle.terminate()

    def _next_job(self, run: Run) -> str | None:
        with self._lock:
            if run.cancelled or not run.todo:
                # Fini sous le verrou : un job demandé ensuite part dans un nouveau run.
                run.current = None
                run.done = True
                return None
            run.current = run.todo.popleft()
            return run.current

    def _execute(self, run: Run) -> None:
        pipeline = ci.load_pipeline(self.settings)
        run.started = time.monotonic()
        layout = self.engine.layout
        tree: Path | None = None
        tree_error = ""
        environment: ci.Environment | None = None
        tokens = {"base_sha": run.base_sha, "osv_url": self._osv_url}
        first = True
        try:
            while (job_id := self._next_job(run)) is not None:
                job = pipeline.job(job_id)
                if job is None:
                    continue
                if not self._submit(run, job_id, "running", ensure=pipeline if first else None):
                    return
                first = False
                if tree is None and not tree_error:
                    try:
                        git = Git.for_workspace(self._git_path(), layout.root, self.settings)
                        tree = ci.prepare_tree(git, layout, run.number, run.head_sha)
                        tokens["repo"] = str(tree)
                    except (GitError, OSError) as exc:
                        log.warning("Arbre du run %s : %s", run.key, exc)
                        tree_error = "ne peut pas tourner : le commit testé n'a pas pu être extrait"
                if tree is None:
                    result = ci.error_result(job, tree_error)
                else:
                    venv = None
                    if ci.needs_environment(job, self.settings):
                        if environment is None:
                            environment = ci.prepare_environment(
                                tree, layout, self.settings, on_start=lambda h: self._attach(run, h)
                            )
                        if run.cancelled:
                            return
                        venv = environment.venv
                    if ci.needs_environment(job, self.settings) and venv is None:
                        assert environment is not None
                        why = f"ne peut pas tourner : {environment.error}"
                        result = ci.error_result(job, why)
                    else:
                        result = ci.run_job(
                            job,
                            tree=tree,
                            venv=venv,
                            tokens=tokens,
                            settings=self.settings,
                            on_start=lambda h: self._attach(run, h),
                        )
                if result.interrupted or run.cancelled:
                    return
                if not self._submit(run, job_id, result=result):
                    return
        finally:
            run.duration_ms = int((time.monotonic() - run.started) * 1000)
            if tree is not None:
                ci.discard_tree(tree)
            log.info(
                "Run du pipeline %s de %s : %s en %d ms",
                run.key,
                self.engine.workspace_id,
                "annulé" if run.cancelled else run.states,
                run.duration_ms,
            )

    # ------------------------------------------------------------ opérations de la file
    def _submit(
        self,
        run: Run,
        job_id: str,
        state: str = "",
        *,
        result: ci.JobResult | None = None,
        ensure: ci.Pipeline | None = None,
    ) -> bool:
        """Soumet un changement de check à la file ; faux si l'espace le refuse (run arrêté)."""
        if result is not None:
            with self._lock:
                run.awaiting.add(job_id)
                run.current = None
            run.states[job_id] = result.state
        op = check_operation(
            self,
            run,
            job_id,
            state or (result.state if result else ""),
            result=result,
            ensure=ensure,
        )
        try:
            future = self.engine.submit(op)
        except OperationRefused as refused:
            log.info("Run %s arrêté : %s", run.key, refused.reason_text)
            with self._lock:
                run.awaiting.discard(job_id)
                self._cancel(run)
            return False
        if result is not None:
            # Refusée à l'exécution (autre `epoch`) ou abandonnée à la mise en veille, l'opération
            # ne passe pas par son corps : le résultat est réglé quand même.
            future.add_done_callback(lambda _done: self.settle(run, job_id))
        return True

    def git(self) -> Git:
        return Git.for_workspace(self._git_path(), self.engine.layout.root, self.settings)

    def settle(self, run: Run, job_id: str) -> None:
        """Appelé par l'opération (fil de la file) : le résultat de `job_id` est traité."""
        with self._lock:
            run.awaiting.discard(job_id)


def check_operation(
    runner: PipelineRunner,
    run: Run,
    job_id: str,
    state: str,
    *,
    result: ci.JobResult | None = None,
    ensure: ci.Pipeline | None = None,
) -> Operation:
    """Opération de la file qui écrit l'état d'un check, portant l'`epoch` du run (AD-1)."""

    def body(ctx: OpContext) -> int:
        try:
            if run.cancelled:
                return 0
            git = runner.git()
            if ensure is not None:
                jobs = [(job.job_id, job.required) for job in ensure.jobs]
                github_sim.ensure_checks(git, ctx.layout, run.number, jobs)
            try:
                pr = github_sim.set_check_state(
                    git,
                    ctx.layout,
                    run.number,
                    job_id,
                    state,  # type: ignore[arg-type]
                    output=result.output if result else "",
                    findings=result.findings if result else (),
                    duration_ms=result.duration_ms if result else None,
                    expected=(run.head_sha, run.base_sha),
                )
            except StaleCheck:
                log.info("Résultat tardif ignoré : %s %s", run.key, job_id)
                return 0
            except GithubSimError as error:
                log.info("Check %s non écrit : %s", job_id, error.cause_text)
                return 0
            check = next(c for c in pr.checks if c.job_id == job_id)
            ctx.emit(
                Kind.CHECK_UPDATED,
                {
                    "number": run.number,
                    "job_id": job_id,
                    "state": check.state,
                    "head_sha": check.head_sha,
                    "element_id": check.element(run.number),
                    "duration_ms": check.duration_ms,
                },
            )
            announce(ctx, [run.number])
            return 0
        finally:
            if result is not None:
                runner.settle(run, job_id)

    return Operation(
        "check_update",
        body,
        epoch=run.epoch,
        writes=False,
        reason_text=f"Le pipeline simulé met à jour le check « {job_id} » de la PR n°{run.number}.",
    )


# --- Activation par le scénario ----------------------------------------------------------------


def scenario_enabled(engine: WorkspaceEngine, scenario_of: Callable[[dict], Any]) -> bool:
    """Vrai si le scénario de l'espace déclare `pipeline: true`."""
    if not engine.layout.run_json.exists():
        return False
    try:
        scenario = scenario_of(load_run(engine.layout))
    except Exception:  # noqa: BLE001 - un run.json illisible n'active rien
        return False
    return bool(scenario is not None and getattr(scenario, "pipeline", False))


# --- Intention check_rerun ---------------------------------------------------------------------


class CheckRerun(BaseModel):
    number: int = Field(ge=1)
    job_id: str = Field(max_length=64, pattern=JOB_ID_PATTERN)


RUNNERS: dict[str, PipelineRunner] = {}
"""Runner de chaque espace actif (posé par le gestionnaire) : `check_rerun` le consulte."""


def _rerun_refusal(engine: WorkspaceEngine, body: CheckRerun) -> str:
    runner = RUNNERS.get(engine.workspace_id)
    if runner is None or not runner._enabled():
        return PIPELINE_OFF_TEXT
    try:
        pipeline = ci.load_pipeline(engine.settings)
        pr = github_sim.load(engine.layout).pull(body.number)
    except (ci.PipelineError, GithubSimError) as error:
        return f"{error.cause_text} {error.action_text}"
    if pipeline.job(body.job_id) is None:
        return f"Le pipeline simulé n'a pas de job « {body.job_id} »."
    if pr is None or pr.state != "open":
        return f"La PR n°{body.number} n'est pas ouverte."
    check = next((c for c in pr.checks if c.job_id == body.job_id), None)
    if check is None:
        return f"La PR n°{body.number} n'a pas de check « {body.job_id} »."
    if check.state in PENDING_STATES and runner.covers(
        body.number, pr.head_sha, pr.base_sha, body.job_id
    ):
        return f"Le check « {body.job_id} » est déjà en attente ou en cours."
    return ""


def build_check_rerun(engine: WorkspaceEngine, body: CheckRerun) -> Operation:
    """« Relancer le check » : le check repasse à `queued` ; le pipeline le relance seul."""
    refusal = _rerun_refusal(engine, body)
    if refusal:
        raise OperationRefused(refusal)

    def run(ctx: OpContext) -> int:
        refusal = _rerun_refusal(engine, body)
        if refusal:
            ctx.output(refusal, "refused")
            return 2
        git = Git.for_workspace(
            ctx.git_path or resolve_git(ctx.settings), ctx.layout.root, ctx.settings
        )
        pr = github_sim.set_check_state(git, ctx.layout, body.number, body.job_id, "queued")
        check = next(c for c in pr.checks if c.job_id == body.job_id)
        ctx.emit(
            Kind.CHECK_UPDATED,
            {
                "number": body.number,
                "job_id": body.job_id,
                "state": check.state,
                "head_sha": check.head_sha,
                "element_id": check.element(body.number),
                "duration_ms": None,
            },
        )
        announce(ctx, [body.number])
        return 0

    return Operation("check_rerun", run, writes=False, validate=False)


# --- Intention check_output_seen ---------------------------------------------------------------


def build_check_output_seen(engine: WorkspaceEngine, body: CheckRerun) -> Operation:
    """« Voir la sortie » d'un check du pipeline : la preuve `evidence_seen` de sa barrière
    (`barrier` de `content/pipeline.yaml`) est soumise, si le check a un résultat pour les SHA
    courants de la PR. Sinon rien : l'ouverture d'une sortie n'est jamais refusée."""

    def run(ctx: OpContext) -> int:
        runner = RUNNERS.get(engine.workspace_id)
        if runner is None or not runner._enabled():
            return 0
        try:
            job = ci.load_pipeline(engine.settings).job(body.job_id)
            pr = github_sim.load(ctx.layout).pull(body.number)
        except (ci.PipelineError, GithubSimError):
            return 0
        if job is None or not job.barrier or pr is None:
            return 0
        check = next((c for c in pr.checks if c.job_id == body.job_id), None)
        if (
            check is None
            or check.state in PENDING_STATES
            or (check.head_sha, check.base_sha) != (pr.head_sha, pr.base_sha)
        ):
            return 0
        ctx.submit_evidence(job.barrier)
        return 0

    return Operation("check_output_seen", run, writes=False, validate=False)


def register_intents() -> None:
    """Enregistre `check_rerun` et `check_output_seen` (idempotent)."""
    if "check_rerun" not in INTENTS:
        register_intent(Intent("check_rerun", CheckRerun, build_check_rerun))
    if "check_output_seen" not in INTENTS:
        register_intent(Intent("check_output_seen", CheckRerun, build_check_output_seen))
