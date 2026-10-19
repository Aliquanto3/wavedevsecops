"""Alias d'une ligne du diff d'un commit (`diffline:…`), bonne réponse d'une désignation."""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar, Literal

from pydantic import Field, field_validator

from wavedevsecops import wsfs
from wavedevsecops.contracts import element_id, parse_element_id
from wavedevsecops.scenarios.context import SetupError
from wavedevsecops.scenarios.ops._base import OpArgs

if TYPE_CHECKING:
    from wavedevsecops.scenarios.context import SetupContext


class Args(OpArgs):
    op: Literal["diff_line"]
    commit: str
    """Commit dont le diff porte la ligne : `@alias` d'un commit."""
    path: str
    line: int = Field(ge=1)
    """Numéro de la ligne dans le fichier du commit (côté `new`) ou dans son parent (`old`)."""
    side: Literal["old", "new"] = "new"
    contains: str | None = None
    """Texte que la ligne doit contenir : garde-fou contre un numéro qui dérive du contenu."""

    reference_fields: ClassVar[tuple[str, ...]] = ("commit",)

    @field_validator("commit")
    @classmethod
    def _alias(cls, value: str) -> str:
        if not value.startswith("@") or len(value) < 2:
            raise ValueError("`commit` doit être un @alias")
        return value

    @field_validator("path")
    @classmethod
    def _relative(cls, value: str) -> str:
        try:
            wsfs.check_relative(value)
        except wsfs.SandboxPathError as exc:
            raise ValueError(exc.cause_text) from None
        return value


def apply(args: Args, ctx: SetupContext) -> str:
    """Rend le `diffline` de la ligne ; l'op ne touche pas au dépôt."""
    kind, segments = parse_element_id(ctx.element(args.commit))
    if kind != "commit":
        raise SetupError(f"L'alias « {args.commit} » ne désigne pas un commit.")
    sha = segments[0]
    revision = sha if args.side == "new" else f"{sha}^"
    text = ctx.git.internal("show", f"{revision}:{args.path}", cwd=ctx.layout.repo)
    lines = text.splitlines()
    if args.line > len(lines):
        raise SetupError(f"« {args.path} » n'a pas de ligne {args.line}.")
    if args.contains and args.contains not in lines[args.line - 1]:
        raise SetupError(
            f"La ligne {args.line} de « {args.path} » ne contient pas « {args.contains} »."
        )
    return element_id("diffline", sha, args.path, args.side, str(args.line))
