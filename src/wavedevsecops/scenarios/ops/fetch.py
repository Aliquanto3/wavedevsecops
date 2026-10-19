"""Récupère `origin` dans le dépôt de l'apprenant, comme un `git fetch` fait avant le scénario."""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar, Literal

from pydantic import field_validator

from wavedevsecops.contracts import element_id
from wavedevsecops.scenarios.ops._base import OpArgs, check_branch
from wavedevsecops.scenarios.ops._origin import origin_branch

if TYPE_CHECKING:
    from wavedevsecops.scenarios.context import SetupContext


class Args(OpArgs):
    op: Literal["fetch"]
    branch: str = "main"
    """Branche d'`origin` dont le sommet est rendu : nom ou `@alias`."""

    reference_fields: ClassVar[tuple[str, ...]] = ("branch",)

    @field_validator("branch")
    @classmethod
    def _branch(cls, value: str) -> str:
        return check_branch(value)


def apply(args: Args, ctx: SetupContext) -> str:
    """Rend le commit au sommet de `origin/<branch>` après le fetch. Un fetch qui suit un push
    forcé laisse l'ancien sommet dans le reflog de `origin/<branch>` (commit « perdu »)."""
    repo = ctx.layout.repo
    name = origin_branch(ctx, args.branch)
    ctx.git.internal("fetch", "-q", "--no-tags", "origin", cwd=repo)
    sha = ctx.git.internal("rev-parse", f"refs/remotes/origin/{name}^{{commit}}", cwd=repo)
    return element_id("commit", sha.strip())
