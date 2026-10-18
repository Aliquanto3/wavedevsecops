"""Aides des ops qui agissent sur `origin` : branche désignée, commit écrit dans `origin.git`."""

from __future__ import annotations

import tempfile
from collections.abc import Mapping
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

from wavedevsecops import wsfs
from wavedevsecops.scenarios.context import SetupError
from wavedevsecops.wsfs import to_lf

if TYPE_CHECKING:
    from wavedevsecops.scenarios.context import SetupContext

_PREFIXES = ("refs/remotes/origin/", "refs/heads/")
NULL_OID = "0" * 40
"""Ancienne valeur attendue d'une ref qui ne doit pas exister encore (`update-ref`)."""


def origin_branch(ctx: SetupContext, value: str) -> str:
    """Nom court sur `origin` : `@alias` d'une branche locale ou de suivi d'origin, ou nom."""
    if not value.startswith("@"):
        return value
    revision = ctx.revision(value)
    for prefix in _PREFIXES:
        if revision.startswith(prefix):
            return revision.removeprefix(prefix)
    raise SetupError(f"L'alias « {value} » ne désigne pas une branche.")


def commit_on_origin(
    ctx: SetupContext,
    persona: str,
    branch: str,
    files: Mapping[str, str],
    message: str,
    date: datetime | None = None,
    start: str | None = None,
) -> str:
    """Commit de `persona` écrit directement dans `origin.git`, sans toucher au dépôt local.

    Plomberie git sans worktree (index temporaire) : le nouvel arbre est celui de `branch`
    (ou de `start` si `branch` n'existe pas encore sur `origin`) plus `files` (chemin posix ->
    contenu UTF-8, LF). `branch` est avancée avec `update-ref` ; si elle n'existe pas et que
    `start` est vide, le commit est une racine ; si elle existe, `start` est ignoré (toujours
    fast-forward : un push forcé demanderait un parent explicite). Identité et date sont celles
    du setup (AD-3) :
    le SHA est le même sur les trois systèmes. Rend le SHA du commit."""
    git, bare = ctx.git, ctx.layout.origin
    name = origin_branch(ctx, branch)
    ref = f"refs/heads/{name}"
    current = git.run("rev-parse", "--verify", "-q", ref, cwd=bare)
    old = current.stdout.strip() if current.ok else None
    parent = old
    if old is None and start is not None:
        base = git.run("rev-parse", "--verify", "-q", origin_branch(ctx, start), cwd=bare)
        if not base.ok:
            raise SetupError(f"La branche de départ « {start} » n'existe pas sur origin.")
        parent = base.stdout.strip()
    with tempfile.TemporaryDirectory(prefix="wds-colleague-") as tmp:
        index = {"GIT_INDEX_FILE": str(Path(tmp) / "index")}
        if parent is not None:
            git.internal("read-tree", parent, cwd=bare, extra_env=index)
        for number, (path, content) in enumerate(sorted(files.items())):
            blob = wsfs.write_text(Path(tmp), f"blob{number}", content)
            oid = git.internal("hash-object", "-w", str(blob), cwd=bare).strip()
            entry = f"100644,{oid},{path}"
            git.internal("update-index", "--add", "--cacheinfo", entry, cwd=bare, extra_env=index)
        tree = git.internal("write-tree", cwd=bare, extra_env=index).strip()
    argv = ["commit-tree", tree, "-m", to_lf(message)]
    if parent is not None:
        argv += ["-p", parent]
    env = ctx.identity_env(persona, ctx.next_date(date))
    sha = git.internal(*argv, cwd=bare, extra_env=env).strip()
    git.internal("update-ref", ref, sha, old or NULL_OID, cwd=bare)
    return sha
