"""Remplace un texte, présent une seule fois, dans un fichier de l'arbre de travail."""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal

from pydantic import field_validator

from wavedevsecops import wsfs
from wavedevsecops.contracts import element_id
from wavedevsecops.scenarios.context import SetupError
from wavedevsecops.scenarios.ops._base import OpArgs

if TYPE_CHECKING:
    from wavedevsecops.scenarios.context import SetupContext


class Args(OpArgs):
    op: Literal["replace_in_file"]
    path: str
    """Chemin posix relatif au dépôt (`uv.lock`)."""
    old: str
    """Texte à remplacer : il doit figurer exactement une fois (fins de ligne en LF)."""
    new: str

    @field_validator("path")
    @classmethod
    def _relative(cls, value: str) -> str:
        try:
            wsfs.check_relative(value)
        except wsfs.SandboxPathError as exc:
            raise ValueError(exc.cause_text) from None
        return value

    @field_validator("old")
    @classmethod
    def _not_empty(cls, value: str) -> str:
        if not value:
            raise ValueError("le texte à remplacer est vide")
        return value


def apply(args: Args, ctx: SetupContext) -> str:
    target = wsfs.confine(ctx.layout.repo, args.path)
    try:
        text = wsfs.to_lf(target.read_text("utf-8"))
    except (OSError, UnicodeDecodeError):
        raise SetupError(f"« {args.path} » n'a pas pu être lu.") from None
    found = text.count(wsfs.to_lf(args.old))
    if found != 1:
        raise SetupError(
            f"« {args.path} » : le texte à remplacer figure {found} fois (une seule attendue)."
        )
    wsfs.write_text(ctx.layout.repo, args.path, text.replace(wsfs.to_lf(args.old), args.new, 1))
    return element_id("path", "worktree", args.path)
