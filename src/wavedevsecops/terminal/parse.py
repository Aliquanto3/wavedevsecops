"""Découpeur POSIX et garde du terminal (AD-4) : pas de shell, pas de PTY.

Une ligne devient un argv par un découpeur de type POSIX (guillemets simples et doubles,
antislash). Les métacaractères d'un shell sont refusés avec explication, jamais interprétés.
Une commande git doit figurer dans la liste blanche (sous-commande et options) ; aucun glob
n'est développé ici : git reçoit ses pathspecs telles quelles.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from wavedevsecops import wsfs
from wavedevsecops.terminal.allowlist import Allowlist, GitSubcommand, ReadRule, ToolSpec

_NUMBER = re.compile(r"-\d+")
_NAME_START = re.compile(r"[A-Za-z0-9_{(@*#?$!\-]")


class Refused(Exception):
    """Ligne refusée : `text` explique pourquoi et cite la liste acceptée."""

    def __init__(self, text: str) -> None:
        super().__init__(text)
        self.text = text


@dataclass(frozen=True)
class Token:
    text: str
    operator: bool = False
    """Vrai pour une redirection `>` ou `>>` non protégée par des guillemets."""


def _dollar_active(line: str, i: int, *, quoted: bool) -> bool:
    """`$` suivi d'un nom, de `(`, `{` ou d'un paramètre spécial : une expansion en shell."""
    nxt = line[i + 1] if i + 1 < len(line) else ""
    if not nxt:
        return False
    if quoted and nxt in "\"'":
        return False
    return bool(_NAME_START.match(nxt)) or nxt in "'\""


def _found(line: str, i: int) -> str:
    c = line[i]
    if c in "|&<>" and line[i : i + 2] == c * 2:
        return c * 2
    if c == "$":
        j = i + 1
        if j < len(line) and line[j] in "({":
            return line[i : j + 1] + "…"
        while j < len(line) and (line[j].isalnum() or line[j] == "_"):
            j += 1
        return line[i : max(j, i + 2)]
    return c


def tokenize(line: str, allow: Allowlist) -> list[Token]:
    """Découpe `line` en mots (règles POSIX) ; lève `Refused` sur un métacaractère de shell."""

    def refuse(i: int) -> Refused:
        reason = allow.message("metachar", found=_found(line, i))
        return Refused(f"{reason} {allow.accepted()}")

    tokens: list[Token] = []
    current: list[str] = []
    started = False
    state = "normal"
    i = 0
    n = len(line)

    def flush() -> None:
        nonlocal started
        if started:
            tokens.append(Token("".join(current)))
        current.clear()
        started = False

    while i < n:
        c = line[i]
        if state == "single":
            if c == "'":
                state = "normal"
            else:
                current.append(c)
        elif state == "double":
            if c == '"':
                state = "normal"
            elif c == "\\" and i + 1 < n and line[i + 1] in '"\\$`':
                current.append(line[i + 1])
                i += 1
            elif c == "`" or (c == "$" and _dollar_active(line, i, quoted=True)):
                raise refuse(i)
            else:
                current.append(c)
        else:
            if c in " \t":
                flush()
            elif c in "\r\n":
                raise refuse(i)
            elif c == "'":
                state, started = "single", True
            elif c == '"':
                state, started = "double", True
            elif c == "\\":
                if i + 1 >= n:
                    raise Refused(f"{allow.message('unterminated')} {allow.accepted()}")
                current.append(line[i + 1])
                started = True
                i += 1
            elif c in "|&;<`" or (c == "$" and _dollar_active(line, i, quoted=False)):
                raise refuse(i)
            elif c == ">":
                flush()
                op = ">>" if line[i : i + 2] == ">>" else ">"
                tokens.append(Token(op, operator=True))
                i += len(op) - 1
            else:
                current.append(c)
                started = True
        i += 1
    if state != "normal":
        raise Refused(f"{allow.message('unterminated')} {allow.accepted()}")
    flush()
    return tokens


@dataclass(frozen=True)
class GitCommand:
    """Commande git acceptée par la garde."""

    sub: str
    args: tuple[str, ...]
    """Arguments transmis à git après la sous-commande, tels que tapés (sans guillemets)."""
    read: bool
    """Vrai pour une lecture, seule admise en `quiz_altered`."""
    options: frozenset[str]
    positionals: tuple[str, ...]
    touches_origin: bool = False
    remote_argument: str | None = None
    """Dépôt visé par `push`, `pull` ou `fetch` : à vérifier comme remote existant."""
    remote_names: tuple[str, ...] = ()
    """Noms passés à `remote show` ou `remote get-url` : à vérifier comme remotes existants."""
    missing_message: bool = False
    """`commit` ou `tag -a` sans message : si git échoue, le terminal explique pourquoi."""


def _refuse(allow: Allowlist, reason: str, sub: str | None = None) -> Refused:
    tail = allow.accepted_options(sub) if sub else allow.accepted()
    return Refused(f"{reason} {tail}")


def _is_read(spec: GitSubcommand, options: set[str], positionals: list[str]) -> bool:
    rule = spec.read
    if isinstance(rule, bool):
        return rule
    return _rule_holds(rule, options, positionals)


def _rule_holds(rule: ReadRule, options: set[str], positionals: list[str]) -> bool:
    if rule.options_within is not None:
        if not (options - {"--"}) <= set(rule.options_within):
            return False
    if rule.positionals_max is not None and len(positionals) > rule.positionals_max:
        return False
    if rule.first_positional_in is not None:
        if not positionals or positionals[0] not in rule.first_positional_in:
            return False
    return True


def check_git(args: list[str], allow: Allowlist) -> GitCommand:
    """Valide les arguments de `git` (sans le mot `git`) contre la liste blanche."""
    if not args:
        raise Refused(f"{allow.message('hint')} {allow.accepted()}")
    first = args[0]
    if first.startswith("-"):
        key = "forbidden_option" if first in allow.forbidden_options else "global_option"
        raise _refuse(allow, allow.message(key, option=first))
    sub = first
    spec = allow.git.get(sub)
    if spec is None:
        raise _refuse(allow, allow.message("unknown_subcommand", sub=sub))

    rest = args[1:]
    options: set[str] = set()
    positionals: list[str] = []
    allowed = set(spec.options)
    valued = set(spec.value_options)

    def bad_option(option: str) -> Refused:
        key = "forbidden_option" if option in allow.forbidden_options else "unknown_option"
        return _refuse(allow, allow.message(key, option=option, sub=sub), sub)

    i = 0
    after_separator = False
    while i < len(rest):
        token = rest[i]
        i += 1
        if after_separator or not token.startswith("-") or token == "-":
            positionals.append(token)
            continue
        if token == "--":
            after_separator = True
            options.add("--")
            continue
        if token.startswith("--"):
            name, equals, _ = token.partition("=")
            if name not in allowed:
                raise bad_option(name)
            options.add(name)
            if name in valued and not equals:
                i += 1
            continue
        if token in allowed:  # option courte exacte (`-m`, `-uno`, `-vv`)
            options.add(token)
            if token in valued:
                i += 1
            continue
        if spec.number_option and _NUMBER.fullmatch(token):
            continue
        for index, char in enumerate(token[1:]):  # regroupement : `-am`, `-sn`, `-U3`
            option = f"-{char}"
            if option not in allowed:
                raise bad_option(option if len(token) > 2 else token)
            options.add(option)
            if option in valued:
                if index == len(token) - 2:
                    i += 1  # la valeur est l'argument suivant
                break

    if positionals and spec.choices and positionals[0] not in spec.choices:
        raise _refuse(
            allow,
            allow.message(
                "bad_positional", sub=sub, value=positionals[0], choices=", ".join(spec.choices)
            ),
        )
    if positionals and positionals[0] in spec.refused_arguments:
        raise _refuse(allow, allow.message("refused_argument", sub=sub, value=positionals[0]))
    if spec.positionals_max is not None and len(positionals) > spec.positionals_max:
        raise _refuse(allow, allow.message("too_many", sub=sub))
    if spec.writable_keys and len(positionals) >= 2 and positionals[0] not in spec.writable_keys:
        raise _refuse(allow, allow.message("config_write"))

    has_message = bool(options & {"-m", "--message"})
    # `--no-edit` seul ne fournit pas de message (sauf merge en cours : git réussit alors).
    exempt = {"--amend", "--allow-empty-message"}
    missing = (spec.needs_message and not (has_message or options & exempt)) or (
        bool(spec.needs_message_with)
        and bool(options & set(spec.needs_message_with))
        and not has_message
    )
    return GitCommand(
        sub=sub,
        args=tuple(rest),
        read=_is_read(spec, options, positionals),
        options=frozenset(options),
        positionals=tuple(positionals),
        touches_origin=spec.touches_origin,
        remote_argument=positionals[0] if spec.remote_argument and positionals else None,
        remote_names=(
            tuple(positionals[spec.remote_names_from :])
            if spec.remote_names_from is not None
            else ()
        ),
        missing_message=bool(missing),
    )


@dataclass(frozen=True)
class FileCommand:
    """Commande de fichiers acceptée par la garde (story 2.5) ; exécutée par `terminal.files`."""

    name: str
    options: frozenset[str]
    args: tuple[str, ...]
    """Chemins (ou, pour `echo`, mots du texte), sans les options."""
    read: bool
    redirect: str | None = None
    """`>` ou `>>` pour `echo texte > fichier`."""
    target: str | None = None
    """Fichier visé par la redirection."""


def _file_refuse(allow: Allowlist, reason: str) -> Refused:
    return Refused(f"{reason} {allow.accepted()}")


def check_file(name: str, tokens: list[Token], allow: Allowlist) -> FileCommand:
    """Valide une commande de fichiers (`tokens` : après le nom) contre la liste blanche."""
    spec = allow.files[name]
    redirect: str | None = None
    target: str | None = None
    operators = [i for i, token in enumerate(tokens) if token.operator]
    if operators:
        last_ok = (
            spec.redirect
            and len(operators) == 1
            and operators[0] == len(tokens) - 2
            and not tokens[-1].operator
        )
        if not last_ok:
            only = len(operators) == 1 and operators[0] == len(tokens) - 1
            if spec.redirect and only:
                key = allow.message("redirect_target", operator=tokens[operators[0]].text)
                raise _file_refuse(allow, key)
            raise _file_refuse(allow, allow.message("redirect_misplaced"))
        redirect, target = tokens[-2].text, tokens[-1].text
        tokens = tokens[:-2]

    options: set[str] = set()
    args: list[str] = []
    allowed = set(spec.options)
    after_separator = spec.text
    for token in tokens:
        word = token.text
        if after_separator or not word.startswith("-") or word == "-":
            args.append(word)
        elif word == "--":
            after_separator = True
        else:
            letters = [f"-{c}" for c in word[1:]] if not word.startswith("--") else [word]
            for option in letters:
                if option not in allowed:
                    where = (
                        allow.message("file_options_some", options=", ".join(spec.options))
                        if spec.options
                        else allow.message("file_options_none")
                    )
                    reason = allow.message(
                        "file_unknown_option", option=option, command=name, accepted=where
                    )
                    raise _file_refuse(allow, reason)
                options.add(option)
    if len(args) < spec.min_args:
        raise _file_refuse(allow, allow.message("file_too_few", command=name, count=spec.min_args))
    if spec.max_args is not None and len(args) > spec.max_args:
        raise _file_refuse(allow, allow.message("file_too_many", command=name))
    return FileCommand(
        name=name,
        options=frozenset(options),
        args=tuple(args),
        read=spec.read or (spec.redirect and redirect is None),
        redirect=redirect,
        target=target,
    )


@dataclass(frozen=True)
class ToolCommand:
    """Outil de la chaîne accepté par la garde (story 7.2) ; lancé par `terminal.tools`."""

    name: str
    args: tuple[str, ...]
    """Arguments transmis à l'outil, tels que tapés (sous-commande comprise)."""
    barrier_id: str
    write: bool
    """Vrai si une option écrit dans l'arbre de travail (`ruff check --fix`)."""

    @property
    def read(self) -> bool:
        return not self.write


def _tool_refuse(allow: Allowlist, reason: str) -> Refused:
    return Refused(f"{reason} {allow.accepted()}")


def check_tool(name: str, tokens: list[Token], allow: Allowlist) -> ToolCommand:
    """Valide les arguments d'un outil (`tokens` : après son nom) contre la liste blanche."""
    spec: ToolSpec = allow.tools[name]
    rest = [token.text for token in tokens]
    if spec.subcommands and (not rest or rest[0] not in spec.subcommands):
        subcommands = ", ".join(spec.subcommands)
        raise _tool_refuse(
            allow, allow.message("tool_subcommand", tool=name, subcommands=subcommands)
        )
    allowed, valued = set(spec.options), set(spec.value_options)
    shown = ", ".join(spec.options)

    def unknown(option: str) -> Refused:
        accepted = allow.message("tool_options", options=shown) if shown else ""
        reason = allow.message("tool_unknown_option", tool=name, option=option, accepted=accepted)
        return _tool_refuse(allow, reason)

    def missing(option: str) -> Refused:
        return _tool_refuse(allow, allow.message("tool_missing_value", tool=name, option=option))

    def take_value(option: str, index: int) -> int:
        # Valeur séparée : jamais une option. pytest relit tous ses arguments à la recherche
        # de `-p` avant de les analyser (`consider_preparse`) : `-k -p greffon` chargerait un
        # greffon, comme `-- -p greffon` (le séparateur `--` est donc refusé, lui aussi).
        if index >= len(rest) or rest[index].startswith("-"):
            raise missing(option)
        return index + 1

    options: set[str] = set()
    positionals: list[str] = []
    i = 1 if spec.subcommands else 0
    while i < len(rest):
        token = rest[i]
        i += 1
        if not token.startswith("-") or token == "-":
            positionals.append(token)
            continue
        if token.startswith("--"):  # `--` lui-même n'est pas dans la liste : refusé
            option, equals, _ = token.partition("=")
            if option not in allowed:
                raise unknown(option)
            options.add(option)
            if option in valued and not equals:
                i = take_value(option, i)
            continue
        if token in allowed:  # option courte exacte (`-q`, `-x`, `-k`)
            options.add(token)
            if token in valued:
                i = take_value(token, i)
            continue
        if token[:2] in valued:  # valeur collée : `-kmot`, `-rA`
            options.add(token[:2])
            continue
        for char in token[1:]:  # regroupement : `-qx`
            option = f"-{char}"
            if option not in allowed or option in valued:
                raise unknown(option if len(token) > 2 else token)
            options.add(option)
    if spec.paths:
        for value in positionals:
            # `tests/test_a.py::test_x` : seul le chemin est confiné au dépôt.
            base = value.split("::", 1)[0]
            if base == ".":
                continue  # la racine du dépôt, cwd de l'outil
            try:
                wsfs.check_relative(base)
            except wsfs.SandboxPathError:
                raise _tool_refuse(allow, allow.message("tool_path", value=value)) from None
    return ToolCommand(
        name=name,
        args=tuple(rest),
        barrier_id=spec.barrier_id,
        write=bool(options & set(spec.write_options)),
    )


PRE_COMMIT_SETUP = frozenset({"install", "uninstall", "install-hooks"})
"""Sous-commandes de `pre-commit` qui posent ou retirent des hooks : refusées avec explication."""


def parse_line(line: str, allow: Allowlist) -> GitCommand | FileCommand | ToolCommand | None:
    """Ligne tapée -> commande acceptée, `None` si la ligne est vide ; sinon `Refused`."""
    tokens = tokenize(line, allow)
    if not tokens:
        return None
    head = tokens[0].text
    if tokens[0].operator:
        raise Refused(f"{allow.message('metachar', found=head)} {allow.accepted()}")
    if head in allow.files:
        return check_file(head, tokens[1:], allow)
    if head in allow.tools:
        if any(token.operator for token in tokens):
            symbol = next(token.text for token in tokens if token.operator)
            raise Refused(f"{allow.message('metachar', found=symbol)} {allow.accepted()}")
        return check_tool(head, tokens[1:], allow)
    if any(token.operator for token in tokens):
        # Une redirection n'est permise qu'après `echo` : ici, jamais.
        symbol = next(token.text for token in tokens if token.operator)
        raise Refused(f"{allow.message('metachar', found=symbol)} {allow.accepted()}")
    if head == "cd":
        raise Refused(f"{allow.message('cd')} {allow.accepted()}")
    if head == "pre-commit" and len(tokens) > 1 and tokens[1].text in PRE_COMMIT_SETUP:
        # Story 7.3 : les hooks sont posés par le scénario (`install_hooks`), pas par l apprenant.
        reason = allow.message("pre_commit_install", sub=tokens[1].text)
        raise Refused(f"{reason} {allow.accepted()}")
    if head != "git":
        raise Refused(f"{allow.message('unknown_command', command=head)} {allow.accepted()}")
    return check_git([token.text for token in tokens[1:]], allow)
