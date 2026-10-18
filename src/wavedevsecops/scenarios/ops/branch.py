"""Crée une branche sur une révision (par défaut HEAD), sans changer de branche."""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar, Literal

from pydantic import field_validator

from wavedevsecops.contracts import element_id
from wavedevsecops.scenarios.ops._base import OpArgs, check_branch, check_revision

if TYPE_CHECKING:
    from wavedevsecops.scenarios.context import SetupContext


class Args(OpArgs):
    op: Literal["branch"]
    name: str
    start: str = "HEAD"
    """Révision de départ : `HEAD`, un nom, ou `@alias` d'un commit ou d'une ref."""

    reference_fields: ClassVar[tuple[str, ...]] = ("start",)

    @field_validator("name")
    @classmethod
    def _name(cls, value: str) -> str:
        if value.startswith("@"):
            raise ValueError("le nom d'une nouvelle branche ne peut pas être un alias")
        return check_branch(value)

    @field_validator("start")
    @classmethod
    def _start(cls, value: str) -> str:
        return check_revision(value)


def apply(args: Args, ctx: SetupContext) -> str:
    ctx.git.internal("branch", args.name, ctx.revision(args.start), cwd=ctx.layout.repo)
    return element_id("ref", f"refs/heads/{args.name}")
