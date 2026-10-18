"""Crée un commit avec une identité et une date fixes (tout l'arbre est indexé par défaut)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal

from pydantic import AwareDatetime, Field

from wavedevsecops.contracts import element_id
from wavedevsecops.scenarios.ops._base import OpArgs
from wavedevsecops.wsfs import to_lf

if TYPE_CHECKING:
    from wavedevsecops.scenarios.context import SetupContext


class Args(OpArgs):
    op: Literal["commit"]
    message: str = Field(min_length=1)
    author: Literal["learner", "colleague", "agent"] = "learner"
    date: AwareDatetime | None = None
    """Date fixe ; sinon l'horloge du setup (une minute par commit)."""
    add_all: bool = True
    """Indexe tout l'arbre (`git add -A`) avant le commit."""
    allow_empty: bool = False


def apply(args: Args, ctx: SetupContext) -> str:
    repo = ctx.layout.repo
    if args.add_all:
        ctx.git.internal("add", "-A", cwd=repo)
    argv = ["commit", "-q", "--no-verify", "-m", to_lf(args.message)]
    if args.allow_empty:
        argv.append("--allow-empty")
    env = ctx.identity_env(args.author, ctx.next_date(args.date))
    ctx.git.internal(*argv, cwd=repo, extra_env=env)
    sha = ctx.git.internal("rev-parse", "HEAD", cwd=repo).strip()
    return element_id("commit", sha)
