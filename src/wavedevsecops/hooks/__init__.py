"""Point d'entrée des hooks git de l'espace (AD-9) : `python -m wavedevsecops.hooks <nom> ...`.

Chaque hook posé par l'op `install_hooks` est un script `#!/bin/sh` d'une ligne qui appelle ce
point d'entrée. Un seul dossier `hooks/` sert `repo/` et `origin.git/` : le point d'entrée
distingue le dépôt appelant par son dossier de travail (git lance un hook depuis la racine du
dépôt, ou depuis le dépôt nu), et `pre-receive` n'agit que dans `origin.git/`.

Contrat (stories 3.5, 5.7, 7.3) :

- code 0 : git continue ; autre code : git refuse et affiche la sortie d'erreur (`remote:` pour
  un hook côté `origin`) ;
- le refus s'écrit en français sur la sortie d'erreur ;
- un hook ne modifie jamais l'état : il lit `github.json` par `github_sim` et rien d'autre.
"""

from __future__ import annotations

import sys
from collections.abc import Callable
from pathlib import Path
from typing import TextIO

from wavedevsecops import github_sim
from wavedevsecops.wsfs import Layout

HOOK_NAMES = ("pre-receive",)
"""Hooks que l'op `install_hooks` sait poser ; un hook de plus s'ajoute ici et dans `HANDLERS`."""

BRANCH_PREFIX = "refs/heads/"
EXIT_REFUSED = 1


def hook_script(name: str, python: Path) -> str:
    """Script d'une ligne (LF) du hook `name` : chemins posix entre guillemets, sans bash."""
    if name not in HOOK_NAMES:
        raise ValueError(f"hook inconnu : « {name} »")
    return f'#!/bin/sh\nexec "{python.as_posix()}" -m wavedevsecops.hooks {name} "$@"\n'


def refusal_text(branch: str) -> str:
    return (
        f"La branche « {branch} » est protégée : un push direct est refusé.\n"
        "Poussez une autre branche, puis ouvrez une pull request.\n"
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
    refused: list[str] = []
    for line in stdin.read().splitlines():
        parts = line.split()
        if len(parts) != 3 or not parts[2].startswith(BRANCH_PREFIX):
            continue
        branch = parts[2].removeprefix(BRANCH_PREFIX)
        if branch not in refused and github_sim.direct_push_blocked(layout, branch):
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
    return handler(Path.cwd(), stdin or sys.stdin, stderr or sys.stderr)
