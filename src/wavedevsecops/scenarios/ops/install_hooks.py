"""Pose les hooks git de l'espace dans `hooks/` (AD-9) : scripts `sh` d'une ligne, en LF."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import TYPE_CHECKING, Literal

from pydantic import Field, field_validator

from wavedevsecops import wsfs
from wavedevsecops.contracts import element_id
from wavedevsecops.hooks import HOOK_NAMES, hook_script
from wavedevsecops.scenarios.ops._base import OpArgs

if TYPE_CHECKING:
    from wavedevsecops.scenarios.context import SetupContext


HOOKS_PATH_FROM_ORIGIN = "../hooks"


class Args(OpArgs):
    op: Literal["install_hooks"]
    hooks: list[str] = Field(default_factory=lambda: ["pre-receive"], min_length=1)
    """Hooks à poser, parmi ceux que `wavedevsecops.hooks` connaît."""

    @field_validator("hooks")
    @classmethod
    def _known(cls, value: list[str]) -> list[str]:
        for name in value:
            if name not in HOOK_NAMES:
                raise ValueError(f"hook inconnu : « {name} » (connus : {', '.join(HOOK_NAMES)})")
        if len(set(value)) != len(value):
            raise ValueError("hook en double")
        return value


def apply(args: Args, ctx: SetupContext) -> str:
    # Pour un push vers un chemin local, git retire `GIT_CONFIG_COUNT` de l'environnement de
    # `receive-pack` : le `core.hooksPath` forcé par l'application n'atteint pas `origin.git`.
    # Il est donc aussi écrit dans sa configuration, en relatif (l'espace reste déplaçable :
    # git le résout depuis `origin.git/`, où il lance les hooks d'un dépôt nu).
    ctx.git.internal("config", "core.hooksPath", HOOKS_PATH_FROM_ORIGIN, cwd=ctx.layout.origin)
    python = Path(sys.executable)
    for name in args.hooks:
        wsfs.write_executable(ctx.layout.hooks, name, hook_script(name, python))
    # Aucun type d'AD-2 ne désigne un hook (hors du dépôt) : `output:` en tient lieu.
    return element_id("output", f"hook-{args.hooks[0]}")
