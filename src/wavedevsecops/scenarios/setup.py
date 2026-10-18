"""Exécution du setup d'un scénario dans un espace vide (AD-3, AD-5, AD-7).

Crée `repo/` (remote `origin`), `origin.git/` (dépôt nu) et `hooks/`, puis applique les ops
dans l'ordre. git est lancé par `gitio` en contexte interne ; les fichiers sont écrits par
`wsfs`. Le setup ne lance jamais `ci`.
"""

from __future__ import annotations

from wavedevsecops import wsfs
from wavedevsecops.gitio import Git
from wavedevsecops.scenarios.context import SetupContext, SetupError
from wavedevsecops.scenarios.model import Scenario
from wavedevsecops.scenarios.ops import REGISTRY
from wavedevsecops.wsfs import Layout

ORIGIN_URL = "../origin.git"
"""URL du remote `origin`, relative à `repo/` : l'espace reste déplaçable (AD-5)."""


def run_setup(scenario: Scenario, layout: Layout, git: Git) -> dict[str, str]:
    """Prépare l'espace et rend les alias résolus (`alias -> element_id`)."""
    if scenario.template != "empty":
        raise SetupError(f"Le gabarit « {scenario.template} » n'est pas disponible.")
    wsfs.make_dirs(layout.root)
    wsfs.make_dirs(layout.hooks)
    # `--template=` : aucun gabarit du poste (`info/exclude`, exemples de hooks), dont le
    # contenu varie selon l'installation de git.
    git.internal("init", "-q", "--template=", "--bare", layout.origin.name, cwd=layout.root)
    git.internal("init", "-q", "--template=", layout.repo.name, cwd=layout.root)
    git.internal("remote", "add", "origin", ORIGIN_URL, cwd=layout.repo)
    ctx = SetupContext(layout=layout, git=git)
    for op in scenario.setup:
        produced = REGISTRY[op.op].apply(op, ctx)
        if op.as_ is not None:
            ctx.aliases[op.as_] = produced
    return dict(ctx.aliases)
