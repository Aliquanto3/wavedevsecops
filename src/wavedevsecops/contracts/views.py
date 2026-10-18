"""Projections publiées dans `state_projected{views}` (AD-2, AD-17).

Le serveur calcule tout : placement du graphe, annotations (`new`, `restored`, `lost`,
`designable`), noms accessibles, liens, clés d'explication et texte d'annonce. Le front
met en forme, sans rien déduire. Schéma versionné, en ajout seulement.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict

from wavedevsecops.contracts.repo import Actor, RepoState

VIEWS_VERSION = 1

LabelKind = Literal["branch", "remote", "tag", "head"]


class _Model(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class RefLabel(_Model):
    """Étiquette d'un nœud : `graph-branch`, `graph-remote-ref`, `graph-tag`, `graph-head`."""

    element_id: str
    """`ref:refs/heads/x`, `ref:refs/remotes/origin/x`, `tag:<nom>` ou `ref:HEAD`."""
    kind: LabelKind
    name_text: str
    """Libellé affiché (`main`, `origin/main`, `v1.0`, `HEAD`, `HEAD détachée`)."""
    a11y_name_text: str
    """Rôle et nom (« branche locale feature », « référence distante origin/main »)."""
    explain_ref: str
    current: bool = False
    """Branche courante (HEAD attachée dessus)."""
    new: bool = False
    """Créée ou déplacée par la dernière opération."""
    designable: bool = True
    links: list[str] = []


class GraphNode(_Model):
    """Un commit placé (`graph-commit`, ou `graph-commit-lost`)."""

    element_id: str
    sha: str
    short_sha: str
    subject: str
    actor: Actor
    column: int
    """Colonne (0 à gauche)."""
    row: int
    """Rang, compté depuis les racines (0 en bas) : il ne dépend que des ancêtres."""
    parents: list[str] = []
    """`element_id` des parents, dans l'ordre de git."""
    refs: list[RefLabel] = []
    head: bool = False
    """HEAD est sur ce commit (attachée ou détachée)."""
    detached_head: bool = False
    lost: bool = False
    new: bool = False
    restored: bool = False
    designable: bool = True
    a11y_name_text: str
    explain_ref: str
    links: list[str] = []
    """`element_id` liés (refs qui le visent, parents)."""


class GraphEdge(_Model):
    """Arête `graph-edge`, d'un enfant vers un parent.

    Tracé : nœud parent → (`column`, rang du parent + 1) → (`column`, rang de l'enfant − 1)
    → nœud enfant. Le serveur garantit qu'aucun nœud n'occupe `column` entre ces deux rangs.
    Si les rangs se suivent, l'arête relie directement les deux nœuds.
    """

    child: str
    parent: str
    column: int
    kind: Literal["first_parent", "merge"]
    lost: bool = False


class GraphView(_Model):
    nodes: list[GraphNode] = []
    """Triés par rang décroissant, puis colonne : l'ordre de `commit-list`."""
    edges: list[GraphEdge] = []
    columns: int = 0
    rows: int = 0
    head_text: str = ""
    """« HEAD sur main » ou « HEAD détachée sur a1b2c3d » ; vide si aucun commit."""


class StagingItem(_Model):
    element_id: str
    """`path:index:<chemin>` (Indexé) ou `path:worktree:<chemin>` (les deux autres groupes)."""
    path: str
    letter: str
    """Lettre d'état git (`M`, `A`, `D`, `R`, `C`, `T`, `U`, `?`)."""
    orig_path: str = ""
    designable: bool = True
    a11y_name_text: str = ""
    """Groupe, chemin et état en toutes lettres (« Indexé : a.txt, ajouté »)."""


class StagingView(_Model):
    """`staging-index` : Indexé, Modifié non indexé, Non suivi (UX-DR16)."""

    staged: list[StagingItem] = []
    unstaged: list[StagingItem] = []
    untracked: list[StagingItem] = []


class PromptView(_Model):
    """`terminal-prompt` : la branche courante, ou « HEAD détachée »."""

    text: str
    detached: bool = False
    element_id: str = ""
    """`ref:refs/heads/<branche>`, ou `commit:<sha>` si HEAD est détachée."""


class Views(_Model):
    """Contenu de `state_projected.views`."""

    schema_version: int = VIEWS_VERSION
    repo: RepoState
    graph: GraphView
    staging: StagingView
    prompt: PromptView
    announce_text: str = ""
    """Résumé des changements pour la région `role="status"`."""
