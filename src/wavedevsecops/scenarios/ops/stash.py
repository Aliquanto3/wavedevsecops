"""Met des modifications de côté (`git stash push`), identité et date fixes."""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal

from pydantic import AwareDatetime, Field, field_validator

from wavedevsecops import wsfs
from wavedevsecops.contracts import element_id
from wavedevsecops.scenarios.context import SetupError
from wavedevsecops.scenarios.ops._base import OpArgs
from wavedevsecops.scenarios.ops.colleague_commit import FileDecl

if TYPE_CHECKING:
    from wavedevsecops.scenarios.context import SetupContext


class Args(OpArgs):
    op: Literal["stash"]
    message: str = Field(min_length=1)
    files: list[FileDecl] = Field(default_factory=list)
    """Fichiers écrits avant la mise de côté (sinon : les modifications déjà présentes)."""
    include_untracked: bool = True
    author: Literal["learner", "colleague", "agent"] = "agent"
    date: AwareDatetime | None = None

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
    before = ctx.git.run("rev-parse", "--verify", "-q", "refs/stash", cwd=repo).stdout.strip()
    argv = ["stash", "push", "-q", "-m", wsfs.to_lf(args.message)]
    if args.include_untracked:
        argv.append("--include-untracked")
    env = ctx.identity_env(args.author, ctx.next_date(args.date))
    ctx.git.internal(*argv, cwd=repo, extra_env=env)
    top = ctx.git.run("rev-parse", "--verify", "-q", "refs/stash", cwd=repo).stdout.strip()
    if not top or top == before:
        raise SetupError("Rien à mettre de côté : l'arbre de travail est propre.")
    return element_id("commit", top)
