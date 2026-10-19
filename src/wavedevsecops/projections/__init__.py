"""Projections (AD-2) : `RepoState` relu par git, puis vues calculées par le serveur.

Après chaque opération, la file (AD-1) appelle le projecteur de l'espace : il relit l'état
réel (`state`), place le graphe (`graph`), calcule les vues annotées (`views`) et fournit le
résolveur des passages liables des sorties (`spans`). Le front ne déduit rien.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from pydantic import ValidationError

from wavedevsecops.contracts import (
    REPO_STATE_VERSION,
    VIEWS_VERSION,
    Actor,
    GraphView,
    RepoState,
    Views,
)
from wavedevsecops.gitio import Git
from wavedevsecops.projections.graph import Layout, place
from wavedevsecops.projections.links import annotate
from wavedevsecops.projections.remote import announce_remote, build_remote, previous_remote
from wavedevsecops.projections.spans import Linker
from wavedevsecops.projections.state import read_repo_state
from wavedevsecops.projections.views import (
    EXPLAIN_REFS,
    EXPLAIN_SBOM,
    announce,
    build_graph,
    build_prompt,
    build_staging,
    build_views,
    commit_a11y_name,
)
from wavedevsecops.scenarios.context import PERSONAS
from wavedevsecops.wsfs import Layout as WorkspaceLayout

ACTORS: dict[str, Actor] = {
    identity.email.lower(): persona  # type: ignore[misc]
    for persona, identity in PERSONAS.items()
    if persona in ("colleague", "agent")  # le relecteur (`reviewer`) ne commite jamais
}
"""Adresse e-mail des personnages simulés → rôle ; toute autre adresse est l'apprenant."""


@dataclass(frozen=True)
class Projected:
    views: Views
    linker: Linker


def previous_state(views: Mapping[str, Any] | None) -> RepoState | None:
    """`RepoState` de la projection précédente, s'il est lisible et de même version."""
    repo = (views or {}).get("repo")
    if not isinstance(repo, Mapping) or repo.get("schema_version") != REPO_STATE_VERSION:
        return None
    try:
        return RepoState.model_validate(repo)
    except ValidationError:
        return None


def previous_graph(views: Mapping[str, Any] | None) -> GraphView | None:
    """Graphe de la projection précédente, s'il est lisible et de même version."""
    graph = (views or {}).get("graph")
    if not isinstance(graph, Mapping) or (views or {}).get("schema_version") != VIEWS_VERSION:
        return None
    try:
        return GraphView.model_validate(graph)
    except ValidationError:
        return None


def project(
    git: Git,
    layout: WorkspaceLayout,
    previous_views: Mapping[str, Any] | None = None,
    *,
    restored: frozenset[str] = frozenset(),
    after_restore: bool = False,
    pipeline_jobs: frozenset[str] = frozenset(),
) -> Projected:
    """Relit le dépôt de l'espace et calcule ses vues ; `previous_views` fixe les marques.

    `after_restore` (AD-6) : les commits revenus par la restauration (absents de l'état
    précédent) portent la marque `restored` au lieu de `new`.
    """
    state = read_repo_state(git, layout.repo, ACTORS)
    previous = previous_state(previous_views)
    if after_restore:
        known = {c.sha for c in previous.commits} if previous is not None else set()
        restored = restored | frozenset(c.sha for c in state.commits if c.sha not in known)
        previous = None
    views = build_views(state, previous, restored, previous_graph(previous_views))
    branch = state.head.ref.removeprefix("refs/heads/")
    linker = Linker(state)
    remote = build_remote(git, layout, branch, linker, pipeline_jobs)
    before = previous_remote(previous_views)
    news = announce_remote(before, remote) if before is not None else ""
    views = views.model_copy(
        update={
            "remote": remote,
            "announce_text": f"{views.announce_text} {news}".strip(),
        }
    )
    views = annotate(views)
    return Projected(views, linker)


__all__ = [
    "ACTORS",
    "EXPLAIN_REFS",
    "EXPLAIN_SBOM",
    "Layout",
    "Linker",
    "Projected",
    "announce",
    "build_graph",
    "build_prompt",
    "build_staging",
    "build_views",
    "commit_a11y_name",
    "place",
    "previous_graph",
    "previous_state",
    "project",
    "read_repo_state",
]
