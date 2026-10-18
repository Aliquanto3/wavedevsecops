"""Commandes de fichiers du terminal (story 2.5) : écrites en Python, sur `wsfs` seulement.

Aucune ne lance de processus et aucune ne touche le disque sans passer par le confinement de
`wsfs` : chemin relatif au dépôt, sans `..`, sans lien sortant, hors `.git/`, avec les règles
de portabilité de Windows (noms réservés, `:`, `\\`). Même comportement sous Windows, macOS
et Linux. Seuls `rm`, `mv` et `cp` développent `*` et `?` (dans le bac à sable, jamais
au-delà d'un segment de chemin) ; les autres commandes reçoivent les caractères tels quels.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from wavedevsecops import wsfs
from wavedevsecops.contracts import AppError
from wavedevsecops.terminal.allowlist import Allowlist
from wavedevsecops.terminal.parse import FileCommand

EXIT_FAILED = 1
EXIT_REFUSED = 2

Line = tuple[str, str]
"""Une sortie : `(texte, flux)`."""


@dataclass
class FileResult:
    lines: list[Line] = field(default_factory=list)
    code: int = 0

    def out(self, text: str) -> None:
        self.lines.append((text if text.endswith("\n") else text + "\n", "stdout"))

    def fail(self, text: str, *, refused: bool = False) -> None:
        self.lines.append((text + "\n", "refused" if refused else "app"))
        self.code = max(self.code, EXIT_REFUSED if refused else EXIT_FAILED)


def _check(path: str) -> str:
    """Refuse d'emblée un chemin non portable ou hors de l'espace, lectures comprises."""
    wsfs.check_relative(path, portable=True)
    return path


def _each(
    result: FileResult,
    allow: Allowlist,
    command: str,
    paths: list[str],
    action: Callable[[str], object],
) -> None:
    for path in paths:
        try:
            action(_check(path))
        except wsfs.SandboxPathError as exc:
            result.fail(f"{exc.cause_text} {exc.action_text}", refused=True)
        except AppError as exc:
            result.fail(
                allow.message(
                    "file_error", command=command, cause=f"{exc.cause_text} {exc.action_text}"
                )
            )
        except OSError as exc:
            cause = f"opération impossible ({type(exc).__name__})."
            result.fail(allow.message("file_error", command=command, cause=cause))


def _expand(
    root: Path, result: FileResult, allow: Allowlist, command: FileCommand, patterns: list[str]
) -> list[str]:
    """Développe les globs de `rm`, `mv`, `cp` ; un motif sans correspondance est signalé."""
    paths: list[str] = []
    for pattern in patterns:
        try:
            _check(pattern)
            matches = wsfs.expand_glob(root, pattern)
        except wsfs.SandboxPathError as exc:
            result.fail(f"{exc.cause_text} {exc.action_text}", refused=True)
            continue
        if not matches:
            if "-f" not in command.options:
                result.fail(allow.message("file_no_match", command=command.name, pattern=pattern))
            continue
        paths.extend(matches)
    return paths


def _ls(root: Path, command: FileCommand, result: FileResult, allow: Allowlist) -> None:
    target = command.args[0] if command.args else "."
    try:
        if target != ".":
            _check(target)
            if wsfs.kind_of(root, target) in ("file", "symlink"):
                result.out(target)
                return
        for name, is_dir in wsfs.list_dir(root, target, hidden="-a" in command.options):
            result.out(name + ("/" if is_dir else ""))
    except wsfs.SandboxPathError as exc:
        result.fail(f"{exc.cause_text} {exc.action_text}", refused=True)
    except AppError as exc:
        result.fail(allow.message("file_error", command="ls", cause=exc.cause_text))


def _cat(root: Path, command: FileCommand, result: FileResult, allow: Allowlist) -> None:
    def show(path: str) -> None:
        text = wsfs.read_text(root, path)
        result.lines.append((text, "stdout"))

    _each(result, allow, "cat", list(command.args), show)


def _echo(root: Path, command: FileCommand, result: FileResult, allow: Allowlist) -> None:
    text = " ".join(command.args) + "\n"
    if command.redirect is None:
        result.out(text.rstrip("\n") if text == "\n" else text)
        return

    def write(path: str) -> None:
        if command.redirect == ">>":
            wsfs.append_text(root, path, text)
        else:
            if wsfs.kind_of(root, path) == "dir":
                raise wsfs.SandboxFileError(f"« {path} » est un dossier.")
            wsfs.write_text(root, path, text)

    _each(result, allow, "echo", [command.target or ""], write)


def _mv_cp(root: Path, command: FileCommand, result: FileResult, allow: Allowlist) -> None:
    sources = _expand(root, result, allow, command, list(command.args[:-1]))
    dest = command.args[-1]
    if not sources:
        return
    try:
        _check(dest)
        dest_is_dir = wsfs.kind_of(root, dest) == "dir"
    except wsfs.SandboxPathError as exc:
        result.fail(f"{exc.cause_text} {exc.action_text}", refused=True)
        return
    if len(sources) > 1 and not dest_is_dir:
        result.fail(allow.message("file_multi_dest", command=command.name))
        return
    recursive = bool(command.options & {"-r", "-R"})

    def act(source: str) -> None:
        if command.name == "mv":
            wsfs.move_path(root, source, dest)
        else:
            wsfs.copy_path(root, source, dest, recursive=recursive)

    _each(result, allow, command.name, sources, act)


def execute(root: Path, command: FileCommand, allow: Allowlist) -> FileResult:
    """Exécute `command` dans le dépôt `root` ; ne lève pas d'erreur métier."""
    result = FileResult()
    name = command.name
    if name == "ls":
        _ls(root, command, result, allow)
    elif name == "cat":
        _cat(root, command, result, allow)
    elif name == "echo":
        _echo(root, command, result, allow)
    elif name == "touch":
        _each(result, allow, name, list(command.args), lambda p: wsfs.touch(root, p))
    elif name == "mkdir":
        parents = "-p" in command.options
        _each(
            result,
            allow,
            name,
            list(command.args),
            lambda p: wsfs.make_directory(root, p, parents=parents),
        )
    elif name == "rm":
        recursive = bool(command.options & {"-r", "-R"})
        force = "-f" in command.options
        paths = _expand(root, result, allow, command, list(command.args))

        def remove(path: str) -> None:
            try:
                wsfs.remove_path(root, path, recursive=recursive)
            except wsfs.SandboxFileError:
                if not (force and wsfs.kind_of(root, path) == "missing"):
                    raise

        _each(result, allow, name, paths, remove)
    elif name in ("mv", "cp"):
        _mv_cp(root, command, result, allow)
    elif name == "pwd":
        result.out(allow.message("pwd_output"))
    # `clear` : l'affichage est effacé par l'interface ; rien à faire côté serveur.
    return result
