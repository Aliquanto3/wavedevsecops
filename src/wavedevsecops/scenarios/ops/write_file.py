"""Écrit un fichier de l'arbre de travail, en UTF-8 et LF, par `wsfs`."""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal

from pydantic import field_validator

from wavedevsecops import wsfs
from wavedevsecops.contracts import element_id
from wavedevsecops.scenarios.ops._base import OpArgs

if TYPE_CHECKING:
    from wavedevsecops.scenarios.context import SetupContext


class Args(OpArgs):
    op: Literal["write_file"]
    path: str
    """Chemin posix relatif au dépôt (`src/app.py`)."""
    content: str

    @field_validator("path")
    @classmethod
    def _relative(cls, value: str) -> str:
        try:
            wsfs.check_relative(value)
        except wsfs.SandboxPathError as exc:
            raise ValueError(exc.cause_text) from None
        return value


def apply(args: Args, ctx: SetupContext) -> str:
    wsfs.write_text(ctx.layout.repo, args.path, args.content)
    return element_id("path", "worktree", args.path)
