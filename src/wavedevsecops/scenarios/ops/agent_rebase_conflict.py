"""L'agent B rebase une branche et laisse le rebase en conflit (identité et dates fixes)."""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar, Literal

from pydantic import AwareDatetime, field_validator

from wavedevsecops.contracts import element_id
from wavedevsecops.scenarios.context import SetupError
from wavedevsecops.scenarios.ops._base import OpArgs, check_branch, check_revision

if TYPE_CHECKING:
    from wavedevsecops.scenarios.context import SetupContext


class Args(OpArgs):
    op: Literal["agent_rebase_conflict"]
    onto: str
    """Révision sur laquelle la branche est rejouée : branche, `@alias`, SHA."""
    branch: str | None = None
    """Branche rejouée : nom ou `@alias` ; par défaut la branche courante."""
    date: AwareDatetime | None = None
    """Date des commits rejoués (committer) ; sinon l'horloge du setup."""

    reference_fields: ClassVar[tuple[str, ...]] = ("onto", "branch")

    @field_validator("onto")
    @classmethod
    def _onto(cls, value: str) -> str:
        return check_revision(value)

    @field_validator("branch")
    @classmethod
    def _branch(cls, value: str | None) -> str | None:
        return None if value is None else check_branch(value)


def apply(args: Args, ctx: SetupContext) -> str:
    repo = ctx.layout.repo
    argv = ["rebase", ctx.revision(args.onto)]
    if args.branch is None:
        name = ctx.git.internal("symbolic-ref", "--short", "HEAD", cwd=repo).strip()
    else:
        name = ctx.branch_name(args.branch)
        argv.append(name)
    env = ctx.identity_env("agent", ctx.next_date(args.date))
    result = ctx.git.run(*argv, cwd=repo, extra_env=env)
    if result.ok:
        raise SetupError("Le rebase s'est terminé sans conflit : le scénario ne le provoque pas.")
    state = ctx.git.run("rev-parse", "--git-path", "rebase-merge", cwd=repo)
    if not (repo / state.stdout.strip()).is_dir():
        raise SetupError(f"Le rebase a échoué sans rester en conflit : {result.stderr.strip()}")
    return element_id("ref", f"refs/heads/{name}")
