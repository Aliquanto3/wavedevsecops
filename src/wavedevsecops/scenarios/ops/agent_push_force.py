"""L'agent B réécrit une branche d'`origin` par un push forcé, identité et date fixes."""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar, Literal

from pydantic import AwareDatetime, Field, field_validator

from wavedevsecops.contracts import element_id
from wavedevsecops.scenarios.ops._base import OpArgs, check_branch, check_revision
from wavedevsecops.scenarios.ops._origin import commit_on_origin, origin_branch
from wavedevsecops.scenarios.ops.colleague_commit import FileDecl

if TYPE_CHECKING:
    from wavedevsecops.scenarios.context import SetupContext


class Args(OpArgs):
    op: Literal["agent_push_force"]
    branch: str = "main"
    """Branche de `origin` réécrite : nom ou `@alias`."""
    parent: str
    """Nouveau parent du commit : SHA, branche d'`origin` ou `@alias` d'un commit. Les commits
    de `branch` situés après lui disparaissent de la branche."""
    files: list[FileDecl] = Field(default_factory=list)
    """Fichiers écrits par rapport à l'arbre du parent ; vide : l'arbre du parent est gardé."""
    message: str = Field(min_length=1)
    date: AwareDatetime | None = None

    reference_fields: ClassVar[tuple[str, ...]] = ("branch", "parent")

    @field_validator("branch")
    @classmethod
    def _branch(cls, value: str) -> str:
        return check_branch(value)

    @field_validator("parent")
    @classmethod
    def _parent(cls, value: str) -> str:
        return check_revision(value)

    @field_validator("files")
    @classmethod
    def _unique(cls, value: list[FileDecl]) -> list[FileDecl]:
        paths = [f.path for f in value]
        if len(set(paths)) != len(paths):
            raise ValueError("chemin en double dans files")
        return value


def apply(args: Args, ctx: SetupContext) -> str:
    commit_on_origin(
        ctx,
        "agent",
        args.branch,
        {f.path: f.content for f in args.files},
        args.message,
        args.date,
        parent=args.parent,
        force=True,
    )
    # Le dépôt local n'est pas touché : la branche de suivi `origin/<branch>` ne bouge qu'au
    # prochain `git fetch` de l'apprenant, comme après un vrai push d'un autre poste.
    return element_id("ref", f"refs/remotes/origin/{origin_branch(ctx, args.branch)}")
