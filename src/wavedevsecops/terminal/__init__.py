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
from wavedevsecops.contracts import AppError, element_id
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
from wavedevsecops.events import Stream
from wavedevsecops.scenarios import load_scenario
from wavedevsecops.scenarios.steps.push_refused import REFUSED_KEY
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
    confirmed: bool = False
    """Vrai quand l'apprenant a confirmé une commande qui efface tout le bac à sable."""
    cancelled: bool = False
    """Vrai quand l'apprenant a annulé cette confirmation : rien ne s'exécute."""


def _refused_operation(text: str) -> Operation:
    def body(ctx: OpContext) -> int:
        hints.settle(ctx)  # une commande tapée, même refusée, est un essai (story 4.6)
        ctx.output(text, "refused")
        return EXIT_REFUSED

    return Operation(INTENT, body, writes=False, validate=False)


def _notice_operation(text: str, stream: Stream) -> Operation:
    """Message sans exécution : la confirmation demandée, ou l'annulation."""

    def body(ctx: OpContext) -> int:
        hints.settle(ctx)  # la commande tapée est un essai, même en attente de confirmation
        ctx.output(text, stream)
        return 0

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
    guarded = command.sub == "commit" and hooks.pre_commit_installed(ctx.layout.hooks)
    if guarded and "--no-verify" in command.options:
        # Story 7.3 : contourner la barrière que le scénario fait voir ne valide rien.
        ctx.output(allow.message("no_verify"), "refused")
        return EXIT_REFUSED
    if command.sub == "commit":
        hooks.clear_refusal(ctx.layout)
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
    # Hook `pre-commit` de l'application (story 7.3) : la sortie du commit est tenue jusqu'à la
    # fin, pour l'afficher en bloc `tool-output` si le hook refuse. Sans lui, elle coule au fil
    # de l'eau.
    held: list[tuple[str, str]] | None = [] if guarded else None
    for chunk in handle.chunks():
        if chunk is None:
            continue
        if held is not None:
            held.append((chunk.text, chunk.stream))
        else:
            ctx.output(chunk.text, chunk.stream, lang=language.lang)

    killed = handle.timed_out or handle.interrupted or ctx.interrupted
    code = handle.returncode
    refusal = hooks.read_refusal(ctx.layout) if guarded and code and not killed else None
    if held:
        if refusal is not None:
            ctx.output("".join(text for text, _ in held), "stdout", tool=refusal.tool)
        else:
            for text, stream in held:
                ctx.output(text, stream, lang=language.lang)
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
        if refusal is not None:
            _show_hook_refusal(ctx, refusal, allow)
            barrier = allow.hook_barriers.get(refusal.tool)
            if barrier:
                ctx.submit_evidence(barrier)  # la sortie de l'outil s'est affichée (AD-14)
    if code and command.sub == "push" and not killed:
        _explain_protection(ctx, tool, command, allow)
    if command.touches_origin:
        for hook in AFTER_COMMAND_HOOKS:
            try:
                hook(ctx, command, code)
            except Exception:  # noqa: BLE001 - un crochet ne fait pas échouer la commande
                log.exception("Crochet après %s dans %s", command.sub, ctx.workspace_id)
    return code if code is not None else EXIT_INTERRUPTED


def _show_hook_refusal(ctx: OpContext, refusal: hooks.Refusal, allow: Allowlist) -> None:
    """Panneau d'alerte (`role="alert"`) d'un commit refusé par le hook `pre-commit` : le commit
    n'a pas été créé, avec un lien vers la ligne du secret (UX-DR37). La sortie réelle de l'outil
    vient d'être affichée en bloc `tool-output`.

    La cause vient de la trace du hook (une exécution machine de gitleaks), jamais du texte
    de git (AD-2) ; les liens vers les lignes sont fixés par elle (AD-10)."""
    spans: list[dict] = []
    if refusal.tool == "gitleaks":
        message = allow.message("hook_refused_secret")
        found = [(path, rows[0]) for path, rows in sorted(refusal.lines.items()) if rows]
        for path, row in found[:3]:
            label = f"{path}:{row}"
            start = len(message) + 1
            spans.append(
                {
                    "start": start,
                    "end": start + len(label),
                    "text": label,
                    "element_id": element_id("path", "worktree", path),
                }
            )
            message = f"{message} {label}"
    else:
        message = allow.message("hook_refused")
    ctx.output(message, "refused", spans=spans)


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


PROTECTION_BARRIER = "protection"
"""Barrière de `content/chain.yaml` que prouve le refus d'un push direct (story 7.5)."""


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
            ctx.data[REFUSED_KEY] = branch  # valide l'étape « push direct refusé » (7.5)
            ctx.submit_evidence(PROTECTION_BARRIER)  # la preuve de la protection s'affiche
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
        if files.clears_root(command) and body.cancelled:
            return _notice_operation(allow.message("file_confirm_cancelled"), "app")
        if files.clears_root(command) and not body.confirmed:
            return _notice_operation(allow.message("file_confirm_root"), "confirm")
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
