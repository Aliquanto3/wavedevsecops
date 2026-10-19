"""Pipeline simulé : vrais outils, runs liés au SHA, sortie verbatim (AD-10, AD-12).

`ci` lit `content/pipeline.yaml`, prépare l'arbre d'un run (`git clone --shared` de
`origin.git` dans `ci/<pr>-<sha7>/`, checkout du SHA de tête) et son environnement hors ligne
(`cache/venv/` si son `uv.lock` est celui du SHA testé, sinon un environnement propre au
run, créé par `uv sync --offline --frozen` depuis `uv-cache`), puis exécute un job : sortie
humaine verbatim, état tiré du code de sortie, constats tirés des exécutions machine.

`ci` n'écrit jamais `github.json` : le moteur soumet chaque résultat à la file de l'espace
(`engine.pipeline`). Les processus passent par `toolrun` (AD-1) ; un `Handle` remis par
`on_start` permet d'arrêter l'arbre (`procs.terminate_tree`) quand le run est annulé.
"""

from __future__ import annotations

import re
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

from wavedevsecops import toolrun, wsfs
from wavedevsecops.ci.findings import PARSERS
from wavedevsecops.config import Settings
from wavedevsecops.contracts import AppError
from wavedevsecops.contracts.github import JOB_ID_PATTERN, CheckState, Finding
from wavedevsecops.gitio import Git, GitError
from wavedevsecops.registry import load_registry
from wavedevsecops.wsfs import Layout

Parse = Literal["ruff_json", "junit", "gitleaks_json"]
"""Lecteurs de constats livrés (`ci.findings.PARSERS`) ; les stories 8.x en ajoutent."""

TOKENS = frozenset({"repo", "base_sha", "osv_url", "report"})
"""Jetons des argv, remplacés par `ci` ; `report` n'existe que dans une exécution machine."""
_TOKEN = re.compile(r"\{([^{}]*)\}")

TOOL_ERROR_RULE = "tool_error"
"""`rule_id` du constat qui explique une erreur de l'outil (« ⚠ Erreur de l'outil »)."""
NOT_YOUR_CODE = "Ce n'est pas un défaut de votre code."
NO_DETAIL_RULE = "no_detail"
"""Constat d'un échec dont l'exécution machine n'a rien donné : la sortie humaine reste là."""
MAX_OUTPUT_CHARS = 60_000
"""Sortie humaine gardée dans `github.json` : le début et surtout la fin (résumé des outils)."""


class PipelineError(AppError):
    """`content/pipeline.yaml` est absent ou invalide."""


def _tokens_in(argv: list[str], allowed: frozenset[str]) -> list[str]:
    for arg in argv:
        for name in _TOKEN.findall(arg):
            if name not in allowed:
                raise ValueError(f"jeton inconnu « {{{name}}} » dans {argv}")
    return argv


class MachineRun(BaseModel):
    """Exécution machine du même outil sur le même arbre : la source des constats."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    argv: list[str] = Field(min_length=1)
    parse: Parse
    when: Literal["failure", "always"] = "failure"

    @field_validator("argv")
    @classmethod
    def _known_tokens(cls, value: list[str]) -> list[str]:
        return _tokens_in(value, TOKENS)


class ExitCodes(BaseModel):
    """Sens des codes de sortie de la sortie humaine ; tout autre code : erreur de l'outil."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    success: list[int] = Field(default_factory=lambda: [0])
    failure: list[int] = Field(default_factory=lambda: [1])

    @model_validator(mode="after")
    def _disjoint(self) -> ExitCodes:
        if set(self.success) & set(self.failure):
            raise ValueError("un code de sortie ne peut pas valoir succès et échec")
        return self

    def meaning(self, code: int | None) -> CheckState:
        if code in self.success:
            return "success"
        if code in self.failure:
            return "failure"
        return "error"


class Job(BaseModel):
    """Un job du pipeline : un check du même `job_id`."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    job_id: str = Field(pattern=JOB_ID_PATTERN)
    label_text: str = Field(min_length=1)
    tool: str = Field(min_length=1)
    required: bool = False
    barrier: str | None = None
    human: list[str] = Field(default_factory=list)
    machine: list[MachineRun] = Field(default_factory=list)
    exit_codes: ExitCodes = Field(default_factory=ExitCodes)

    @field_validator("human")
    @classmethod
    def _known_tokens(cls, value: list[str]) -> list[str]:
        return _tokens_in(value, TOKENS - {"report"})


class Pipeline(BaseModel):
    """`content/pipeline.yaml`."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: Literal[1]
    jobs: list[Job] = Field(min_length=1)

    @field_validator("jobs")
    @classmethod
    def _unique(cls, value: list[Job]) -> list[Job]:
        ids = [job.job_id for job in value]
        if len(set(ids)) != len(ids):
            raise ValueError("job_id en double dans le pipeline")
        return value

    def job(self, job_id: str) -> Job | None:
        return next((job for job in self.jobs if job.job_id == job_id), None)

    @property
    def job_ids(self) -> list[str]:
        return [job.job_id for job in self.jobs]


def load_pipeline(settings: Settings, path: Path | None = None) -> Pipeline:
    """Lit et valide le pipeline ; `PipelineError` s'il est absent ou invalide."""
    target = path or settings.pipeline_path()
    try:
        data = yaml.safe_load(target.read_text(encoding="utf-8"))
        return Pipeline.model_validate(data)
    except (OSError, UnicodeDecodeError, yaml.YAMLError, ValidationError) as exc:
        raise PipelineError(
            f"Le pipeline simulé ({target.name}) est absent ou invalide : {exc}",
            "Réinstallez WaveDevSecOps pour retrouver le contenu d'origine.",
        ) from None


def expand(argv: list[str], tokens: Mapping[str, str]) -> list[str]:
    """Remplace les jetons `{nom}` ; un jeton sans valeur lève `KeyError`."""

    def value(match: re.Match[str]) -> str:
        found = tokens.get(match[1], "")
        if not found:
            raise KeyError(match[1])
        return found

    return [_TOKEN.sub(value, arg) for arg in argv]


def needs_environment(job: Job, settings: Settings) -> bool:
    """Vrai si l'outil du job vit dans l'environnement Python du run (`uv-lock`)."""
    try:
        return load_registry(settings=settings).get(job.tool).resolution == "uv-lock"
    except OSError, ValueError, KeyError:
        return False


# --- Arbre et environnement d'un run -------------------------------------------------------


def run_name(number: int, head_sha: str) -> str:
    """`<pr>-<sha7>` : dossier de l'arbre d'un run dans `ci/`."""
    return f"{number}-{head_sha[:7]}"


def prepare_tree(git: Git, layout: Layout, number: int, head_sha: str) -> Path:
    """Clone `origin.git` dans `ci/<pr>-<sha7>/` (`--shared`, sans checkout), puis extrait
    `head_sha` en tête détachée. Un arbre resté d'un run arrêté est remplacé. `GitError`."""
    tree = layout.ci / run_name(number, head_sha)
    wsfs.remove_tree(tree)
    wsfs.make_dirs(layout.ci)
    git.internal(
        "clone",
        "--shared",
        "--no-checkout",
        "--quiet",
        str(layout.origin),
        str(tree),
        cwd=layout.ci,
    )
    git.internal("-c", "advice.detachedHead=false", "checkout", "--quiet", head_sha, cwd=tree)
    # Sans remote : un test ou un plugin de l'apprenant ne pousse pas dans `origin.git` hors de
    # la file (les objets restent partagés en lecture par `--shared`).
    git.internal("remote", "remove", "origin", cwd=tree)
    return tree


def reports_dir(tree: Path) -> Path:
    """Rapports des exécutions machine d'un run : à côté de l'arbre, jamais dedans."""
    return tree.with_name(tree.name + ".reports")


def discard_tree(tree: Path) -> None:
    """Supprime l'arbre d'un run et ses rapports (`ci/` est jetable) ; jamais d'exception."""
    for path in (tree, reports_dir(tree)):
        try:
            wsfs.remove_tree(path)
        except OSError:
            pass


@dataclass(frozen=True)
class Environment:
    """Environnement Python d'un run, ou la raison de son absence."""

    venv: Path | None
    shared: bool = False
    """Vrai : `cache/venv/` de l'espace est réutilisé (même `uv.lock`)."""
    error: str = ""


def prepare_environment(
    tree: Path,
    layout: Layout,
    settings: Settings,
    *,
    on_start: Callable[[Any], None] | None = None,
) -> Environment:
    """`cache/venv/` si le `uv.lock` du SHA testé est celui dont il a été créé, sinon un
    environnement du run (`ci/venv-<hash12>/`, gardé pour les runs du même `uv.lock`), créé
    hors ligne par `uv sync --offline --frozen` depuis `uv-cache` (AD-12)."""
    digest = toolrun.lock_digest(tree)
    if digest is None:
        return Environment(None, error="le dépôt testé n'a pas de uv.lock")
    shared = toolrun.venv_dir(layout.root)
    if toolrun.environment_digest(shared) == digest:
        return Environment(shared, shared=True)
    own = layout.ci / f"venv-{digest[:12]}"
    if toolrun.environment_digest(own) == digest:
        return Environment(own)
    synced = toolrun.sync_environment(tree, own, settings, on_start=on_start)
    if not synced.ok:
        reason = synced.error or synced.stderr.strip()[-300:] or "uv sync a échoué"
        return Environment(None, error=f"uv sync hors ligne a échoué ({reason})")
    return Environment(own)


# --- Exécution d'un job --------------------------------------------------------------------


@dataclass
class JobResult:
    """Résultat d'un job : état du check, sortie humaine verbatim, constats, durée."""

    job_id: str
    state: CheckState
    output: str = ""
    findings: list[Finding] = field(default_factory=list)
    duration_ms: int = 0
    interrupted: bool = False


def tool_error(job: Job, why: str) -> Finding:
    """Constat d'une erreur de l'outil : ce n'est pas un défaut du code de l'apprenant."""
    return Finding(
        rule_id=TOOL_ERROR_RULE,
        severity="error",
        message_text=f"{job.tool} {why}. {NOT_YOUR_CODE}",
    )


def error_result(job: Job, why: str, started: float | None = None) -> JobResult:
    """Check en erreur de l'outil, sans sortie (outil introuvable, arbre ou environnement)."""
    elapsed = 0 if started is None else int((time.monotonic() - started) * 1000)
    return JobResult(job.job_id, "error", findings=[tool_error(job, why)], duration_ms=elapsed)


def bound_output(text: str) -> str:
    """Sortie humaine bornée à `MAX_OUTPUT_CHARS` : début et fin gardés, le milieu signalé."""
    if len(text) <= MAX_OUTPUT_CHARS:
        return text
    head = MAX_OUTPUT_CHARS // 4
    tail = MAX_OUTPUT_CHARS - head
    omitted = len(text) - head - tail
    return f"{text[:head]}\n[… {omitted} caractères de sortie omis …]\n{text[-tail:]}"


def _spawn(
    job: Job,
    argv: list[str],
    *,
    tree: Path,
    venv: Path | None,
    settings: Settings,
    on_start: Callable[[Any], None] | None,
) -> tuple[Any, str]:
    """Lance l'outil ; rend `(handle, "")` ou `(None, raison)`."""
    try:
        handle = toolrun.spawn_tool(
            job.tool,
            argv,
            cwd=tree,
            venv=venv if venv is not None else tree / ".venv-absent",
            timeout=settings.pipeline_job_timeout_s,
            settings=settings,
        )
    except toolrun.ToolUnavailable as exc:
        return None, f"est indisponible ({exc.status.reason or exc.status.state})"
    except OSError as exc:
        return None, f"n'a pas démarré ({type(exc).__name__})"
    if on_start is not None:
        on_start(handle)
    return handle, ""


def _machine_findings(
    job: Job,
    run: MachineRun,
    index: int,
    *,
    tree: Path,
    venv: Path | None,
    tokens: Mapping[str, str],
    settings: Settings,
    on_start: Callable[[Any], None] | None,
) -> tuple[list[Finding] | None, bool]:
    """Constats d'une exécution machine ; `(None, interrompu)` si elle n'a rien donné."""
    reports = reports_dir(tree)
    wsfs.make_dirs(reports)
    report = reports / f"{job.job_id}-{index}.out"
    report.unlink(missing_ok=True)
    try:
        argv = expand(run.argv, {**tokens, "report": str(report)})
    except KeyError:
        return None, False
    handle, why = _spawn(job, argv, tree=tree, venv=venv, settings=settings, on_start=on_start)
    if handle is None:
        return None, False
    result = toolrun.collect(handle)
    if handle.interrupted:
        return None, True
    if result.timed_out or result.returncode is None:
        return None, False
    try:
        text = report.read_text("utf-8") if report.is_file() else result.stdout
        return PARSERS[run.parse](text, tree), False
    except OSError, UnicodeDecodeError, ValueError:
        return None, False


def run_job(
    job: Job,
    *,
    tree: Path,
    venv: Path | None,
    tokens: Mapping[str, str],
    settings: Settings,
    on_start: Callable[[Any], None] | None = None,
) -> JobResult:
    """Exécute `job` sur `tree` : sortie humaine verbatim, puis exécutions machine dues.

    `on_start` reçoit chaque `Handle` lancé : `handle.terminate()` arrête l'arbre (annulation
    du run). Un job arrêté rend `interrupted=True` ; son résultat ne doit pas être écrit.
    """
    started = time.monotonic()
    try:
        argv = expand(job.human, tokens)
    except KeyError as missing:
        return error_result(job, f"ne peut pas démarrer : la valeur {{{missing}}} manque", started)
    handle, why = _spawn(job, argv, tree=tree, venv=venv, settings=settings, on_start=on_start)
    if handle is None:
        return error_result(job, why, started)
    result = toolrun.collect(handle)
    if handle.interrupted:
        return JobResult(job.job_id, "error", interrupted=True)
    output = bound_output(result.stdout + result.stderr)
    findings: list[Finding] = []
    if result.timed_out:
        state: CheckState = "error"
        delay = f"{settings.pipeline_job_timeout_s:g}"
        findings.append(tool_error(job, f"n'a pas fini en {delay} s et a été arrêté"))
    else:
        state = job.exit_codes.meaning(result.returncode)
        if state == "error":
            code = result.returncode
            findings.append(tool_error(job, f"s'est arrêté sans résultat (code {code})"))
    if state != "error":
        for index, run in enumerate(job.machine):
            if run.when == "failure" and state != "failure":
                continue
            found, stopped = _machine_findings(
                job,
                run,
                index,
                tree=tree,
                venv=venv,
                tokens=tokens,
                settings=settings,
                on_start=on_start,
            )
            if stopped:
                return JobResult(job.job_id, "error", interrupted=True)
            if found is None and state == "failure":
                findings.append(
                    Finding(
                        rule_id=NO_DETAIL_RULE,
                        severity="info",
                        message_text=(
                            f"Le détail de l'échec (fichier, ligne) n'a pas pu être lu dans le "
                            f"rapport de {job.tool} : la sortie de l'outil le donne."
                        ),
                    )
                )
            findings.extend(found or [])
    elapsed = int((time.monotonic() - started) * 1000)
    return JobResult(job.job_id, state, output, findings, elapsed)


__all__ = [
    "MAX_OUTPUT_CHARS",
    "NO_DETAIL_RULE",
    "TOOL_ERROR_RULE",
    "bound_output",
    "Environment",
    "ExitCodes",
    "GitError",
    "Job",
    "JobResult",
    "MachineRun",
    "Parse",
    "Pipeline",
    "PipelineError",
    "discard_tree",
    "error_result",
    "expand",
    "load_pipeline",
    "needs_environment",
    "prepare_environment",
    "prepare_tree",
    "run_job",
    "run_name",
]
