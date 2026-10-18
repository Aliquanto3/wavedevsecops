"""Commit de l'agent B dans le dépôt local, identité « Agent B » et date fixes."""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal

from pydantic import AwareDatetime, Field, field_validator

from wavedevsecops import wsfs
from wavedevsecops.contracts import element_id
from wavedevsecops.scenarios.ops._base import OpArgs
from wavedevsecops.scenarios.ops.colleague_commit import FileDecl

if TYPE_CHECKING:
    from wavedevsecops.scenarios.context import SetupContext


class Args(OpArgs):
    op: Literal["agent_commit"]
    files: list[FileDecl] = Field(min_length=1)
    """Fichiers écrits puis indexés (eux seuls : le reste de l'arbre n'est pas touché)."""
    message: str = Field(min_length=1)
    date: AwareDatetime | None = None
    """Date fixe ; sinon l'horloge du setup (une minute par commit)."""

    @field_validator("files")
    @classmethod
    def _unique(cls, value: list[FileDecl]) -> list[FileDecl]:
        paths = [f.path for f in value]
        if len(set(paths)) != len(paths):
            raise ValueError("chemin en double dans files")
        return value


def apply(args: Args, ctx: SetupContext) -> str:
    repo = ctx.layout.repo
    for file in args.files:
        wsfs.write_text(repo, file.path, file.content)
    ctx.git.internal("add", "--", *(f.path for f in args.files), cwd=repo)
    env = ctx.identity_env("agent", ctx.next_date(args.date))
    # pathspec : seuls ces chemins entrent dans le commit, même si l'index en contient d'autres.
    message = wsfs.to_lf(args.message)
    paths = [f.path for f in args.files]
    ctx.git.internal(
        "commit", "-q", "--no-verify", "-m", message, "--", *paths, cwd=repo, extra_env=env
    )
    return element_id("commit", ctx.git.internal("rev-parse", "HEAD", cwd=repo).strip())
