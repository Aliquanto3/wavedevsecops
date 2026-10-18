"""`RepoState` : l'état git d'un bac à sable, relu par `projections` après chaque opération.

Schéma versionné, en ajout seulement (AD-17) : un champ nouveau a une valeur par défaut. Les
SHA sont complets (40 caractères hexadécimaux), les chemins en notation posix relatifs à la
racine du dépôt, les dates en ISO 8601 avec fuseau.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict

REPO_STATE_VERSION = 1

Actor = Literal["learner", "colleague", "agent"]
"""Rôle de l'auteur d'un commit : l'apprenant, le collègue simulé ou l'agent B."""

RefKind = Literal["branch", "remote", "tag", "stash", "other"]
"""`refs/heads/`, `refs/remotes/`, `refs/tags/`, `refs/stash`, le reste."""

StatusKind = Literal["changed", "renamed", "unmerged", "untracked"]
"""Types d'entrée de `git status --porcelain=v2` (`1`, `2`, `u`, `?`)."""

InProgress = Literal["", "merge", "rebase", "cherry_pick", "revert"]
"""Opération git en cours (conflit à résoudre) ; vide sinon."""


class _Model(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class Commit(_Model):
    """Un commit du graphe : accessible depuis une ref, ou perdu mais encore dans le reflog."""

    sha: str
    parents: list[str] = []
    tree: str
    author_name: str
    author_email: str
    author_date: str
    committer_name: str
    committer_email: str
    committer_date: str
    committer_ts: int
    """Date du committer en secondes Unix : ordre de placement du graphe."""
    subject: str
    message: str
    """Message complet, sans fin de ligne finale."""
    actor: Actor = "learner"
    lost: bool = False
    """Vrai si aucune ref (ni HEAD) n'y mène, mais qu'un reflog le cite encore."""


class Ref(_Model):
    """Une ref du dépôt (`for-each-ref`), hors HEAD."""

    name: str
    """Nom complet (`refs/heads/main`)."""
    kind: RefKind
    short_name: str
    """Nom court (`main`, `origin/main`, `v1.0`)."""
    target: str
    """Objet visé : le commit, ou l'objet tag d'un tag annoté."""
    commit: str = ""
    """Commit visé après déréférencement (vide si la ref ne vise pas un commit)."""
    annotated: bool = False
    """Tag annoté (objet tag)."""
    symref: str = ""
    """Cible d'une ref symbolique (`refs/remotes/origin/HEAD`) ; vide sinon."""
    upstream: str = ""
    """Branche distante suivie (nom complet), pour une branche locale."""


class Head(_Model):
    """HEAD : branche courante (attachée) ou commit (détachée)."""

    detached: bool
    ref: str = ""
    """Branche courante (nom complet) si HEAD est attachée ; vide si détachée."""
    commit: str = ""
    """Commit de HEAD ; vide si la branche courante n'a encore aucun commit."""
    upstream: str = ""
    ahead: int | None = None
    behind: int | None = None


class IndexEntry(_Model):
    """Entrée de l'index (`ls-files -s -z`)."""

    path: str
    mode: str
    oid: str
    stage: int = 0
    """0 hors conflit ; 1, 2, 3 pendant un conflit (base, nôtre, leur)."""


class StatusEntry(_Model):
    """Entrée de `git status --porcelain=v2 -z` (fichiers ignorés exclus)."""

    path: str
    kind: StatusKind
    index_status: str = "."
    """Lettre de l'index (X) ; `.` si inchangé, `?` pour un fichier non suivi."""
    worktree_status: str = "."
    """Lettre de l'arbre de travail (Y) ; `.` si inchangé, `?` pour un fichier non suivi."""
    orig_path: str = ""
    """Ancien chemin d'un renommage ou d'une copie."""


class StashEntry(_Model):
    index: int
    """Position : `stash@{index}`."""
    sha: str
    message: str


class RepoState(_Model):
    """État complet du dépôt de l'apprenant après une opération (AD-2)."""

    schema_version: int = REPO_STATE_VERSION
    head: Head
    commits: list[Commit] = []
    """Commits accessibles (comme `git log --all`, hors stash) puis perdus, triés par SHA."""
    refs: list[Ref] = []
    """Refs triées par nom complet."""
    index: list[IndexEntry] = []
    status: list[StatusEntry] = []
    worktree: list[str] = []
    """Fichiers présents de l'arbre de travail, suivis ou non ignorés (posix, triés)."""
    stash: list[StashEntry] = []
    in_progress: InProgress = ""
