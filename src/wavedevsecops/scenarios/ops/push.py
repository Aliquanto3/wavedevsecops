"""Pousse une branche vers `origin` (le dépôt nu `origin.git/` de l'espace)."""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar, Literal

from pydantic import field_validator

from wavedevsecops.contracts import element_id
from wavedevsecops.scenarios.ops._base import OpArgs, check_branch

if TYPE_CHECKING:
    from wavedevsecops.scenarios.context import SetupContext


class Args(OpArgs):
    op: Literal["push"]
    remote: Literal["origin"] = "origin"
    branch: str | None = None
    """Branche poussée : nom ou `@alias` ; par défaut la branche courante."""
    set_upstream: bool = True
    force: bool = False

    reference_fields: ClassVar[tuple[str, ...]] = ("branch",)

    @field_validator("branch")
    @classmethod
    def _branch(cls, value: str | None) -> str | None:
        return None if value is None else check_branch(value)


def apply(args: Args, ctx: SetupContext) -> str:
    repo = ctx.layout.repo
    if args.branch is None:
        name = ctx.git.internal("symbolic-ref", "--short", "HEAD", cwd=repo).strip()
    else:
        name = ctx.branch_name(args.branch)
    argv = ["push", "-q", "--no-verify"]
    if args.set_upstream:
        argv.append("--set-upstream")
    if args.force:
        argv.append("--force")
    ctx.git.internal(*argv, args.remote, f"refs/heads/{name}:refs/heads/{name}", cwd=repo)
    return element_id("ref", f"refs/remotes/{args.remote}/{name}")
