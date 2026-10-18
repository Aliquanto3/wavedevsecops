"""Change de branche, en la créant au besoin (`git switch [-c]`)."""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar, Literal

from pydantic import field_validator, model_validator

from wavedevsecops.contracts import element_id
from wavedevsecops.scenarios.ops._base import OpArgs, check_branch, check_revision

if TYPE_CHECKING:
    from wavedevsecops.scenarios.context import SetupContext


class Args(OpArgs):
    op: Literal["switch"]
    branch: str
    """Branche cible : nom, ou `@alias` d'une ref de branche."""
    create: bool = False
    start: str | None = None
    """Révision de départ d'une branche créée (`create: true`)."""

    reference_fields: ClassVar[tuple[str, ...]] = ("branch", "start")

    @field_validator("branch")
    @classmethod
    def _branch(cls, value: str) -> str:
        return check_branch(value)

    @field_validator("start")
    @classmethod
    def _start(cls, value: str | None) -> str | None:
        return None if value is None else check_revision(value)

    @model_validator(mode="after")
    def _coherent(self) -> Args:
        if self.start is not None and not self.create:
            raise ValueError("`start` n'a de sens qu'avec `create: true`")
        if self.create and self.branch.startswith("@"):
            raise ValueError("une branche créée se nomme, elle ne se désigne pas par alias")
        return self


def apply(args: Args, ctx: SetupContext) -> str:
    name = ctx.branch_name(args.branch)
    argv = ["switch", "-q"]
    if args.create:
        argv += ["-c", name]
        if args.start is not None:
            argv.append(ctx.revision(args.start))
    else:
        argv.append(name)
    ctx.git.internal(*argv, cwd=ctx.layout.repo)
    return element_id("ref", f"refs/heads/{name}")
