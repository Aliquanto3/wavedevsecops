"""Protège une branche de `origin` : approbations et checks requis, push direct refusé."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, ClassVar, Literal

from pydantic import Field, field_validator

from wavedevsecops import github_sim
from wavedevsecops.contracts import element_id
from wavedevsecops.contracts.github import JOB_ID_PATTERN, BranchProtection
from wavedevsecops.scenarios.ops._base import OpArgs, check_branch
from wavedevsecops.scenarios.ops._origin import origin_branch

if TYPE_CHECKING:
    from wavedevsecops.scenarios.context import SetupContext


class Args(OpArgs):
    op: Literal["set_protection"]
    branch: str = "main"
    """Branche protégée sur `origin` : nom ou `@alias`."""
    required_approvals: int = Field(default=0, ge=0)
    required_checks: list[str] = Field(default_factory=list)
    """`job_id` des checks obligatoires pour merger vers cette branche."""
    block_direct_push: bool = True
    """Refus d'un push direct par le hook `pre-receive` (story 3.5)."""

    reference_fields: ClassVar[tuple[str, ...]] = ("branch",)

    @field_validator("branch")
    @classmethod
    def _branch(cls, value: str) -> str:
        return check_branch(value)

    @field_validator("required_checks")
    @classmethod
    def _jobs(cls, value: list[str]) -> list[str]:
        for job in value:
            if not re.match(JOB_ID_PATTERN, job):
                raise ValueError(f"job_id invalide : « {job} »")
        if len(set(value)) != len(value):
            raise ValueError("job_id en double dans required_checks")
        return value


def apply(args: Args, ctx: SetupContext) -> str:
    branch = origin_branch(ctx, args.branch)
    github_sim.set_protection(
        ctx.git,
        ctx.layout,
        BranchProtection(
            branch=branch,
            required_approvals=args.required_approvals,
            required_checks=list(args.required_checks),
            block_direct_push=args.block_direct_push,
        ),
    )
    return element_id("ref", f"refs/remotes/origin/{branch}")
