"""Déclare la réaction du collègue simulé à une PR (ouverture, checks au vert)."""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar, Literal

from pydantic import Field, field_validator

from wavedevsecops import github_sim
from wavedevsecops.contracts import element_id
from wavedevsecops.contracts.github import HeadFile, ReactionReview, ReactionTrigger
from wavedevsecops.scenarios.context import PERSONAS
from wavedevsecops.scenarios.ops._base import OpArgs, check_branch
from wavedevsecops.scenarios.ops._origin import origin_branch

if TYPE_CHECKING:
    from wavedevsecops.scenarios.context import SetupContext


class Args(OpArgs):
    op: Literal["colleague_reaction"]
    trigger: ReactionTrigger
    """`pr_opened` : à l'ouverture de la PR ; `checks_green` : quand tous ses checks obligatoires
    sont `success`, sans action de l'apprenant."""
    reviews: list[ReactionReview] = Field(min_length=1)
    """Revues publiées dans cet ordre (« commentaire, puis approbation »)."""
    author: Literal["colleague", "agent", "reviewer"] = "colleague"
    """`reviewer` : un second relecteur humain, distinct du collègue (deux approbations)."""
    head: str | None = None
    """Ne réagit qu'aux PR de cette branche de tête : nom ou `@alias` ; sinon à toute PR."""

    when_files: list[HeadFile] = Field(default_factory=list)
    """Le relecteur lit ces fichiers au commit de tête : condition non remplie, il publie
    `otherwise` (par exemple une demande de changements) au lieu de `reviews`."""
    otherwise: list[ReactionReview] = Field(default_factory=list)

    reference_fields: ClassVar[tuple[str, ...]] = ("head",)

    @field_validator("head")
    @classmethod
    def _head(cls, value: str | None) -> str | None:
        return None if value is None else check_branch(value)


def apply(args: Args, ctx: SetupContext) -> str:
    head = None if args.head is None else origin_branch(ctx, args.head)
    github_sim.add_reaction(
        ctx.layout,
        args.trigger,
        PERSONAS[args.author].name,
        args.reviews,
        head=head,
        when_files=args.when_files,
        otherwise=args.otherwise,
    )
    return element_id("ref", f"refs/remotes/origin/{head or 'main'}")
