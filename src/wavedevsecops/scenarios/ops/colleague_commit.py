"""Le collègue simulé pousse un commit sur `origin`, avec identité et date fixes."""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar, Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, field_validator

from wavedevsecops import wsfs
from wavedevsecops.contracts import element_id
from wavedevsecops.scenarios.ops._base import OpArgs, check_branch
from wavedevsecops.scenarios.ops._origin import commit_on_origin

if TYPE_CHECKING:
    from wavedevsecops.scenarios.context import SetupContext


class FileDecl(BaseModel):
    """Un fichier écrit par le commit du collègue."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    path: str
    """Chemin posix relatif au dépôt."""
    content: str

    @field_validator("path")
    @classmethod
    def _relative(cls, value: str) -> str:
        try:
            wsfs.check_relative(value)
        except wsfs.SandboxPathError as exc:
            raise ValueError(exc.cause_text) from None
        return value


class Args(OpArgs):
    op: Literal["colleague_commit"]
    branch: str = "main"
    """Branche de `origin` qui reçoit le commit : nom ou `@alias`."""
    files: list[FileDecl] = Field(min_length=1)
    message: str = Field(min_length=1)
    date: AwareDatetime | None = None
    """Date fixe ; sinon l'horloge du setup (une minute par commit)."""
    start: str | None = None
    """Branche de `origin` d'où part `branch` si elle n'existe pas encore ; sinon commit racine."""

    reference_fields: ClassVar[tuple[str, ...]] = ("branch", "start")

    @field_validator("branch", "start")
    @classmethod
    def _branch(cls, value: str | None) -> str | None:
        return None if value is None else check_branch(value)

    @field_validator("files")
    @classmethod
    def _unique(cls, value: list[FileDecl]) -> list[FileDecl]:
        paths = [f.path for f in value]
        if len(set(paths)) != len(paths):
            raise ValueError("chemin en double dans files")
        return value


def apply(args: Args, ctx: SetupContext) -> str:
    sha = commit_on_origin(
        ctx,
        "colleague",
        args.branch,
        {f.path: f.content for f in args.files},
        args.message,
        args.date,
        args.start,
    )
    return element_id("commit", sha)
