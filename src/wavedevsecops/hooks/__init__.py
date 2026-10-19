"""Point d'entrée des hooks git de l'espace (AD-9) : `python -m wavedevsecops.hooks <nom> ...`.

Chaque hook posé par l'op `install_hooks` est un script `#!/bin/sh` d'une ligne qui appelle ce
point d'entrée. Un seul dossier `hooks/` sert `repo/` et `origin.git/` : le point d'entrée
distingue le dépôt appelant par son dossier de travail (git lance un hook depuis la racine du
dépôt, ou depuis le dépôt nu), et `pre-receive` n'agit que dans `origin.git/`.

Contrat (stories 3.5, 5.7, 7.3) :

- code 0 : git continue ; autre code : git refuse et affiche la sortie d'erreur (`remote:` pour
  un hook côté `origin`) ;
- le refus s'écrit en français sur la sortie d'erreur ;
- un hook ne modifie jamais l'état : il lit `github.json` par `github_sim` et rien d'autre ;
- `github.json` illisible : la protection n'est pas appliquée (l'apprenant peut travailler),
  avec un avertissement en français ; toute autre erreur du hook refuse le push avec un texte
  en français qui renvoie au diagnostic (AD-9), jamais une trace Python.

Le script porte le chemin de l'interpréteur de l'application (`sys.executable`). Si ce chemin
change (environnement recréé ailleurs), `refresh` réécrit les scripts posés : le terminal
l'appelle avant chaque `git push`. L'empreinte (AD-6) lit `canonical_script`, sans ce chemin,
pour rester la même d'un poste à l'autre (empreintes de référence d'AD-18).
"""

from __future__ import annotations

import re
import sys
from collections.abc import Callable
from pathlib import Path
from typing import TextIO

from wavedevsecops import github_sim, wsfs
from wavedevsecops.wsfs import Layout

HOOK_NAMES = ("pre-receive",)
"""Hooks que l'op `install_hooks` sait poser ; un hook de plus s'ajoute ici et dans `HANDLERS`."""

BRANCH_PREFIX = "refs/heads/"
EXIT_REFUSED = 1

_SH_SPECIAL = re.compile(r'([\\"$`])')
_INTERPRETER = re.compile(rb'^exec ".*" -m wavedevsecops\.hooks ', re.MULTILINE)


def _sh_quote(text: str) -> str:
    """`text` entre guillemets doubles sh, avec `\\`, `"`, `$` et l'accent grave échappés."""
    return '"' + _SH_SPECIAL.sub(r"\\\1", text) + '"'


def hook_script(name: str, python: Path) -> str:
    """Script d'une ligne (LF) du hook `name` : chemins posix entre guillemets, sans bash."""
    if name not in HOOK_NAMES:
        raise ValueError(f"hook inconnu : « {name} »")
    interpreter = _sh_quote(python.as_posix())
    return f'#!/bin/sh\nexec {interpreter} -m wavedevsecops.hooks {name} "$@"\n'


def canonical_script(data: bytes) -> bytes:
    """Contenu d'un fichier de `hooks/` sans le chemin de l'interpréteur (empreinte, AD-6)."""
    return _INTERPRETER.sub(b'exec "<python>" -m wavedevsecops.hooks ', data)


def refresh(hooks_dir: Path, python: Path | None = None) -> list[str]:
    """Réécrit les hooks posés dont l'interpréteur n'est plus celui de l'application ; rend
    leurs noms. Un hook absent n'est pas posé (seule l'op `install_hooks` le fait)."""
    python = python or Path(sys.executable)
    rewritten = []
    for name in HOOK_NAMES:
        expected = hook_script(name, python)
        current = wsfs.read_bytes(hooks_dir, name)
        if current is not None and current != expected.encode("utf-8"):
            wsfs.write_executable(hooks_dir, name, expected)
            rewritten.append(name)
    return rewritten


def refusal_text(branch: str) -> str:
    return (
        f"La branche « {branch} » est protégée : un push direct est refusé.\n"
        "Poussez une autre branche, puis ouvrez une pull request.\n"
    )


UNREADABLE_STATE_TEXT = (
    "Avertissement : l'état du GitHub simulé de cet espace est illisible ; "
    "la protection des branches n'est pas appliquée à ce push.\n"
)
HOOK_FAILED_TEXT = (
    "Le hook « {name} » a échoué ({error}) : le push est refusé par prudence.\n"
    "Ouvrez le diagnostic, ou recommencez le scénario pour reconstruire l'espace.\n"
)


def origin_layout(cwd: Path) -> Layout | None:
    """Espace dont `cwd` est le dépôt nu `origin.git/`, ou `None` si `cwd` est un autre dépôt
    (`repo/` : un dossier `.git`, pas de `HEAD` à sa racine)."""
    if (cwd / ".git").exists() or not (cwd / "HEAD").is_file() or not (cwd / "objects").is_dir():
        return None
    return Layout(cwd.parent)


def pre_receive(cwd: Path, stdin: TextIO, stderr: TextIO) -> int:
    """Refuse toute mise à jour d'une branche protégée contre le push direct.

    `stdin` porte une ligne `<ancien> <nouveau> <ref>` par ref poussée."""
    layout = origin_layout(cwd)
    if layout is None:
        return 0
    try:
        state = github_sim.load(layout)
    except github_sim.GithubSimError:
        stderr.write(UNREADABLE_STATE_TEXT)
        return 0
    blocked = {p.branch for p in state.protections if p.block_direct_push}
    refused: list[str] = []
    for line in stdin.read().splitlines():
        parts = line.split()
        if len(parts) != 3 or not parts[2].startswith(BRANCH_PREFIX):
            continue
        branch = parts[2].removeprefix(BRANCH_PREFIX)
        if branch in blocked and branch not in refused:
            refused.append(branch)
    for branch in refused:
        stderr.write(refusal_text(branch))
    return EXIT_REFUSED if refused else 0


HANDLERS: dict[str, Callable[[Path, TextIO, TextIO], int]] = {"pre-receive": pre_receive}


def main(argv: list[str], stdin: TextIO | None = None, stderr: TextIO | None = None) -> int:
    """Exécute le hook nommé par `argv[0]` ; un hook inconnu ne fait rien (code 0)."""
    handler = HANDLERS.get(argv[0]) if argv else None
    if handler is None:
        return 0
    err = stderr or sys.stderr
    try:
        return handler(Path.cwd(), stdin or sys.stdin, err)
    except Exception as exc:  # noqa: BLE001 - jamais de trace Python dans la sortie de git
        err.write(HOOK_FAILED_TEXT.format(name=argv[0], error=type(exc).__name__))
        return EXIT_REFUSED
