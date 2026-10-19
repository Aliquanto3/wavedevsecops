"""Terminal de l'apprenant : de vraies commandes git, sans shell (AD-4, AD-3, AD-12).

L'intention `terminal_line {line}` découpe la ligne (`parse`), la confronte à la liste blanche
(`content/terminal-allowlist.yaml`) et devient une opération de la file (AD-1) : git tourne dans
`repo/`, en contexte apprenant, et sa sortie est émise telle quelle, au fil de l'eau
(`terminal_output`). Elle n'est jamais analysée pour en tirer un état (AD-2) ; seuls l'argv
et le code de sortie servent à expliquer `commit` ou `tag -a` sans message.

Crochet `AFTER_COMMAND_HOOKS` : appelés après une commande qui agit sur `origin` (`push`,
`pull`, `fetch`) avec `(ctx, commande, code de sortie)`. Le GitHub simulé (story 3.1) y
branchera son `refresh` sans que ce module l'importe.

Story 7.2 : `ruff check` et `pytest` (section `tools` de la liste blanche) tournent par `toolrun`
dans l'environnement d'exercice, si le scénario les déclare ; voir `terminal.tools`.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import replace
from pathlib import Path

from pydantic import BaseModel, Field

from wavedevsecops import github_sim, gitio, hooks
from wavedevsecops.contracts import AppError
from wavedevsecops.engine import (
    INTENTS,
    Intent,
    OpContext,
    Operation,
    WorkspaceEngine,
    hints,
    register_intent,
    resolve_git,
)
from wavedevsecops.engine.runfile import load_run
from wavedevsecops.scenarios import load_scenario
from wavedevsecops.terminal import files, tools
from wavedevsecops.terminal.allowlist import Allowlist, get_allowlist
from wavedevsecops.terminal.parse import (
    FileCommand,
    GitCommand,
    Refused,
    ToolCommand,
    parse_line,
)

log = logging.getLogger("wavedevsecops")

INTENT = "terminal_line"
EXIT_INTERRUPTED = 130
EXIT_TIMEOUT = 124
EXIT_REFUSED = 2

AfterCommand = Callable[[OpContext, GitCommand, int | None], None]
AFTER_COMMAND_HOOKS: list[AfterCommand] = []
"""Rappels après `push`, `pull` ou `fetch` (voir l'en-tête du module)."""


class TerminalLine(BaseModel):
    line: str = Field(max_length=2000)


def _refused_operation(text: str) -> Operation:
    def body(ctx: OpContext) -> int:
        hints.settle(ctx)  # une commande tapée, même refusée, est un essai (story 4.6)
        ctx.output(text, "refused")
        return EXIT_REFUSED

    return Operation(INTENT, body, writes=False, validate=False)


def _run_git(ctx: OpContext, command: GitCommand, allow: Allowlist) -> int:
    repo = ctx.layout.repo
    git_path = ctx.git_path or resolve_git(ctx.settings)
    language = gitio.learner_language(git_path, ctx.settings)
    tool = gitio.Git.for_workspace(git_path, ctx.layout.root, ctx.settings)
    # Identité par défaut de l'apprenant, sans laquelle commit, revert ou merge échouent.
    tool = replace(
        tool, locale=language.locale, learner_gitconfig=gitio.learner_gitconfig(ctx.settings)
    )

    targets = command.remote_names
    if command.remote_argument is not None:
        targets = (command.remote_argument, *targets)
    if targets:
        remotes = tool.internal("remote", cwd=repo).split()
        unknown = next((name for name in targets if name not in remotes), None)
        if unknown is not None:
            reason = allow.message(
                "remote_target",
                value=unknown,
                sub=command.sub,
                remotes=", ".join(remotes) or "aucun",
            )
            ctx.output(f"{reason} {allow.accepted_options(command.sub)}", "refused")
            return EXIT_REFUSED

    if command.sub == "push":
        # Le chemin de Python porté par les hooks suit l'application (environnement recréé).
        hooks.refresh(ctx.layout.hooks)
    try:
        handle = gitio.spawn_learner(
            tool,
            command.sub,
            *command.args,
            cwd=repo,
            timeout=ctx.settings.terminal_timeout_s,
        )
    except OSError as exc:
        raise AppError(
            f"git n'a pas pu être lancé ({type(exc).__name__}).",
            "Ouvrez le diagnostic pour vérifier l'installation de git.",
        ) from exc
    ctx.on_interrupt(handle.terminate)
    for chunk in handle.chunks():
        if chunk is not None:
            ctx.output(chunk.text, chunk.stream, lang=language.lang)

    killed = handle.timed_out or handle.interrupted or ctx.interrupted
    code = handle.returncode
    if killed:
        # L'arbre a été arrêté : un verrou d'index laissé derrière est périmé (AD-12), à
        # condition qu'aucun processus de l'arbre ne vive encore (il pourrait le tenir).
        if not handle.tree_stopped:
            log.warning("Arbre encore vivant dans %s : index.lock conservé", ctx.workspace_id)
        elif gitio.clear_stale_index_lock(repo):
            log.info("index.lock périmé supprimé dans %s", ctx.workspace_id)
        if handle.timed_out:
            seconds = f"{ctx.settings.terminal_timeout_s:g}"
            ctx.output(allow.message("timeout", seconds=seconds), "app")
            code = EXIT_TIMEOUT
        else:
            ctx.output(allow.message("interrupted"), "app")
            code = EXIT_INTERRUPTED
    elif code:
        ctx.output(allow.message("exit_code", code=code), "exit")
        if command.missing_message:
            ctx.output(allow.message("missing_message"), "app")
    if code and command.sub == "push" and not killed:
        _explain_protection(ctx, tool, command, allow)
    if command.touches_origin:
        for hook in AFTER_COMMAND_HOOKS:
            try:
                hook(ctx, command, code)
            except Exception:  # noqa: BLE001 - un crochet ne fait pas échouer la commande
                log.exception("Crochet après %s dans %s", command.sub, ctx.workspace_id)
    return code if code is not None else EXIT_INTERRUPTED


FORCE_OPTIONS = frozenset({"-f", "--force", "--force-with-lease"})
DELETE_OPTIONS = frozenset({"-d", "--delete"})


def _pushed_updates(tool: gitio.Git, repo: Path, command: GitCommand) -> list[tuple[str, str]]:
    """Mises à jour visées par un `git push` : `(source locale, branche d'origin)`, source vide
    pour une suppression ; sans refspec, la branche courante (ou toutes avec `--all`)."""
    delete = bool(command.options & DELETE_OPTIONS)
    updates = []
    for spec in command.positionals[1:]:
        source, colon, target = spec.removeprefix("+").partition(":")
        if not colon:
            target = source
        if delete:
            source = ""
        if target == "HEAD":
            head = tool.run("symbolic-ref", "-q", "--short", "HEAD", cwd=repo)
            target = head.stdout.strip() if head.ok else ""
        if target:
            updates.append((source, target.removeprefix("refs/heads/")))
    if command.positionals[1:] or "--tags" in command.options:
        return updates  # `--tags` sans refspec ne pousse que des étiquettes
    if "--all" in command.options:
        listed = tool.run("for-each-ref", "--format=%(refname:short)", "refs/heads", cwd=repo)
        return [(name, name) for name in listed.stdout.split()] if listed.ok else []
    head = tool.run("symbolic-ref", "-q", "--short", "HEAD", cwd=repo)
    current = head.stdout.strip() if head.ok else ""
    return [(current, current)] if current else []


def _reaches_hook(
    tool: gitio.Git, ctx: OpContext, command: GitCommand, source: str, branch: str
) -> bool:
    """Vrai si git a transmis cette mise à jour à `origin`, donc à son hook `pre-receive` :
    suppression, push forcé, création, ou avance rapide. Un push sans avance rapide est
    refusé par git lui-même avant tout hook ; la protection n'en est alors pas la cause."""
    if (
        not source
        or command.options & FORCE_OPTIONS
        or any(spec.startswith("+") for spec in command.positionals[1:])
    ):
        return True
    ref = f"refs/heads/{branch}"
    remote = tool.run("rev-parse", "-q", "--verify", f"{ref}^{{commit}}", cwd=ctx.layout.origin)
    if not remote.ok:
        return True
    local = tool.run("rev-parse", "-q", "--verify", f"{source}^{{commit}}", cwd=ctx.layout.repo)
    if not local.ok:
        return False
    ancestor = tool.run(
        "merge-base",
        "--is-ancestor",
        remote.stdout.strip(),
        local.stdout.strip(),
        cwd=ctx.layout.repo,
    )
    return ancestor.ok


def _explain_protection(
    ctx: OpContext, tool: gitio.Git, command: GitCommand, allow: Allowlist
) -> None:
    """Après un `push` en échec : si une mise à jour transmise à `origin` vise une branche
    protégée, dit pourquoi git l'a refusée.

    Lu dans l'état du GitHub simulé (AD-8) et dans les refs, jamais dans la sortie de git
    (AD-2)."""
    for source, branch in _pushed_updates(tool, ctx.layout.repo, command):
        if github_sim.direct_push_blocked(ctx.layout, branch) and _reaches_hook(
            tool, ctx, command, source, branch
        ):
            ctx.output(allow.message("protected_branch", branch=branch), "app")
            return


def _run_file(ctx: OpContext, command: FileCommand, allow: Allowlist) -> int:
    """Commande de fichiers : Python sur `wsfs`, dans `repo/` (story 2.5)."""
    result = files.execute(ctx.layout.repo, command, allow)
    for text, stream in result.lines:
        ctx.output(text, stream)
    if result.code == files.EXIT_FAILED:
        ctx.output(allow.message("exit_code", code=result.code), "exit")
    return result.code


_DECLARED: dict[Path, tuple[tuple[int, int], frozenset[str]]] = {}


def declared_tools(engine: WorkspaceEngine) -> frozenset[str]:
    """Outils que le scénario de l'espace déclare (`tools`) : seuls ceux-là sont acceptés (AD-4).

    Relu quand le fichier du scénario change ; illisible ou absent : aucun outil.
    """
    try:
        run = load_run(engine.layout)
        path = engine.settings.scenarios_path() / f"{run['scenario_id']}.{run['mode']}.yaml"
        info = path.stat()
        stamp = (info.st_mtime_ns, info.st_size)
        cached = _DECLARED.get(path)
        if cached is None or cached[0] != stamp:
            declared = frozenset(load_scenario(path, engine.settings).scenario.tools)
            cached = _DECLARED[path] = (stamp, declared)
        return cached[1]
    except Exception:  # noqa: BLE001 - un scénario illisible ne déclare aucun outil
        log.warning("Outils déclarés illisibles pour %s", engine.workspace_id, exc_info=True)
        return frozenset()


def build_terminal_line(engine: WorkspaceEngine, body: TerminalLine) -> Operation:
    """Traduit une ligne tapée en opération : refusée à l'écran, ou git dans `repo/`."""
    allow = get_allowlist(engine.settings)
    try:
        command = parse_line(body.line, allow)
    except Refused as refused:
        return _refused_operation(refused.text)
    if command is None:
        return Operation(
            INTENT, lambda ctx: 0, writes=False, validate=False, precheck=lambda ctx: False
        )
    if isinstance(command, ToolCommand):
        if command.name not in declared_tools(engine):
            reason = allow.message("tool_not_declared", tool=command.name)
            return _refused_operation(f"{reason} {allow.accepted()}")
        return Operation(
            INTENT,
            lambda ctx: tools.run(ctx, command, allow),
            # En `quiz_altered`, seules les lectures passent : `ruff check --fix` écrit.
            writes=command.write,
        )
    if isinstance(command, FileCommand):
        return Operation(
            INTENT, lambda ctx: _run_file(ctx, command, allow), writes=not command.read
        )
    return Operation(
        INTENT,
        lambda ctx: _run_git(ctx, command, allow),
        # En `quiz_altered`, seules les lectures passent (AD-1, AD-4).
        writes=not command.read,
    )


def register_intents() -> None:
    """Enregistre `terminal_line` (idempotent : l'application peut être créée plusieurs fois)."""
    if INTENT not in INTENTS:
        register_intent(Intent(INTENT, TerminalLine, build_terminal_line))
    from wavedevsecops.terminal import quiz  # importé ici : quiz réutilise `_run_git`

    quiz.register_intents()
