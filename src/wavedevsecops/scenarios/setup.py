"""Exécution du setup d'un scénario dans un espace vide (AD-3, AD-5, AD-7).

Crée `repo/` (remote `origin`), `origin.git/` (dépôt nu), `hooks/` et `github.json` (vide, écrit
par `github_sim`), puis applique les ops dans l'ordre et recalcule enfin les PR ouvertes contre
les refs finales de `origin` (AD-8). git est lancé par `gitio` en contexte interne ; les
fichiers sont écrits par `wsfs`. Le setup ne lance jamais `ci`.
"""

from __future__ import annotations

from pathlib import Path

from wavedevsecops import github_sim, wsfs
from wavedevsecops.gitio import Git
from wavedevsecops.scenarios.context import SetupContext, SetupError
from wavedevsecops.scenarios.model import Scenario
from wavedevsecops.scenarios.ops import REGISTRY
from wavedevsecops.wsfs import Layout

ORIGIN_URL = "../origin.git"
"""URL du remote `origin`, relative à `repo/` : l'espace reste déplaçable (AD-5)."""


def run_setup(
    scenario: Scenario, layout: Layout, git: Git, exercise_root: Path | None = None
) -> dict[str, str]:
    """Prépare l'espace et rend les alias résolus (`alias -> element_id`).

    `exercise_root` : `content/exercise/` ; par défaut celui des réglages."""
    if scenario.template != "empty":
        raise SetupError(f"Le gabarit « {scenario.template} » n'est pas disponible.")
    wsfs.make_dirs(layout.root)
    wsfs.make_dirs(layout.hooks)
    # `--template=` : aucun gabarit du poste (`info/exclude`, exemples de hooks), dont le
    # contenu varie selon l'installation de git. SHA-1 imposé : la grammaire `commit:<sha>`
    # (AD-17) attend 40 caractères hexadécimaux, quel que soit le format par défaut de git.
    init = ("init", "-q", "--template=", "--object-format=sha1")
    git.internal(*init, "--bare", layout.origin.name, cwd=layout.root)
    git.internal(*init, layout.repo.name, cwd=layout.root)
    git.internal("remote", "add", "origin", ORIGIN_URL, cwd=layout.repo)
    github_sim.init(layout)
    ctx = SetupContext(layout=layout, git=git)
    if exercise_root is not None:
        ctx.exercise_root = exercise_root
    for op in scenario.setup:
        produced = REGISTRY[op.op].apply(op, ctx)
        if op.as_ is not None:
            ctx.aliases[op.as_] = produced
    github_sim.refresh(git, layout)
    return dict(ctx.aliases)
