"""Ouvre une PR dans le GitHub simulé, entre deux branches déjà poussées sur `origin`."""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from wavedevsecops import github_sim
from wavedevsecops.contracts.github import JOB_ID_PATTERN, CheckState, Finding, ReviewState
from wavedevsecops.scenarios.context import PERSONAS
from wavedevsecops.scenarios.ops._base import OpArgs, check_branch
from wavedevsecops.scenarios.ops._origin import origin_branch

if TYPE_CHECKING:
    from wavedevsecops.scenarios.context import SetupContext


class CheckDecl(BaseModel):
    """Check déclaré par le scénario, lié aux SHA de la PR à son ouverture."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    job_id: str = Field(pattern=JOB_ID_PATTERN)
    state: CheckState = "queued"
    required: bool = False
    output: str = ""
    findings: list[Finding] = Field(default_factory=list)


class ReviewDecl(BaseModel):
    """Revue déclarée par le scénario, liée au `head_sha` de la PR à son ouverture."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    author: Literal["learner", "colleague", "agent"] = "colleague"
    state: ReviewState
    body_text: str = ""


class Args(OpArgs):
    op: Literal["open_pr"]
    head: str
    """Branche de tête sur `origin` : nom ou `@alias`."""
    base: str = "main"
    """Branche de base sur `origin` : nom ou `@alias`."""
    title_text: str = ""
    checks: list[CheckDecl] = Field(default_factory=list)
    reviews: list[ReviewDecl] = Field(default_factory=list)

    reference_fields: ClassVar[tuple[str, ...]] = ("head", "base")

    @field_validator("head", "base")
    @classmethod
    def _branch(cls, value: str) -> str:
        return check_branch(value)

    @field_validator("checks")
    @classmethod
    def _unique_jobs(cls, value: list[CheckDecl]) -> list[CheckDecl]:
        jobs = [c.job_id for c in value]
        if len(set(jobs)) != len(jobs):
            raise ValueError("job_id en double dans checks")
        return value


def apply(args: Args, ctx: SetupContext) -> str:
    pr = github_sim.open_pr(
        ctx.git,
        ctx.layout,
        origin_branch(ctx, args.head),
        origin_branch(ctx, args.base),
        title_text=args.title_text,
        checks=[
            github_sim.DeclaredCheck(c.job_id, c.state, c.required, c.output, tuple(c.findings))
            for c in args.checks
        ],
        reviews=[
            github_sim.DeclaredReview(PERSONAS[r.author].name, r.state, r.body_text)
            for r in args.reviews
        ],
    )
    return pr.element
