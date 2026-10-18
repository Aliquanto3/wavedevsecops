"""Branche de `origin` désignée par une op : nom court ou `@alias` d'une branche."""

from __future__ import annotations

from typing import TYPE_CHECKING

from wavedevsecops.scenarios.context import SetupError

if TYPE_CHECKING:
    from wavedevsecops.scenarios.context import SetupContext

_PREFIXES = ("refs/remotes/origin/", "refs/heads/")


def origin_branch(ctx: SetupContext, value: str) -> str:
    """Nom court sur `origin` : `@alias` d'une branche locale ou de suivi d'origin, ou nom."""
    if not value.startswith("@"):
        return value
    revision = ctx.revision(value)
    for prefix in _PREFIXES:
        if revision.startswith(prefix):
            return revision.removeprefix(prefix)
    raise SetupError(f"L'alias « {value} » ne désigne pas une branche.")
