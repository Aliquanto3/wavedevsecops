"""Schéma de `github.json` : le GitHub simulé d'un espace (AD-8, AD-20), `schema_version` 1.

Le modèle de PR est complet dès v0.1 : checks liés à `head_sha`/`base_sha`, revues et
approbations, approbations requises, règles de protection de la base, `mergeable` et raisons
de blocage. Seul `github_sim` écrit ce fichier ; `hooks` et `projections` le lisent.
Les ajouts suivent la règle d'AD-17 : en ajout seulement, avec migration numérotée.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from wavedevsecops.contracts import element_id

GITHUB_SCHEMA_VERSION = 1

SHA_PATTERN = r"^[0-9a-f]{40}$"
JOB_ID_PATTERN = r"^[a-z][a-z0-9]*(?:_[a-z0-9]+)*$"

CheckState = Literal["queued", "running", "success", "failure", "error"]
PrState = Literal["open", "merged", "closed"]
ReviewState = Literal["approved", "changes_requested", "commented"]
BlockKind = Literal["check", "approvals", "conflict", "head_missing"]
ReactionTrigger = Literal["pr_opened", "checks_green"]
"""Événements de PR qui déclenchent une réaction du collègue simulé (AD-8) : l'ouverture
de la PR, et le passage au vert de tous ses checks obligatoires."""


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Finding(_Model):
    """Constat structuré d'un check, tiré de la sortie machine de l'outil (AD-10)."""

    rule_id: str = ""
    severity: str = ""
    message_text: str = ""
    path: str | None = None
    """Chemin posix relatif à la racine du dépôt."""
    line: int | None = Field(default=None, ge=1)


class Check(_Model):
    """Check d'une PR, lié à la paire `(head_sha, base_sha)` pour laquelle il a été calculé."""

    job_id: str = Field(pattern=JOB_ID_PATTERN)
    head_sha: str = Field(pattern=SHA_PATTERN)
    base_sha: str = Field(pattern=SHA_PATTERN)
    state: CheckState = "queued"
    required: bool = False
    output: str = ""
    """Sortie humaine de l'outil, verbatim (hors empreinte)."""
    findings: list[Finding] = Field(default_factory=list)
    duration_ms: int | None = Field(default=None, ge=0)
    """Durée du job (hors empreinte)."""
    updated_at: str | None = None
    """Horodatage ISO 8601 du dernier changement d'état (hors empreinte)."""

    def element(self, number: int) -> str:
        return element_id("check", str(number), self.job_id, self.head_sha)


class Review(_Model):
    """Revue d'une PR (le collègue simulé, AD-8), numérotée à partir de 1 dans sa PR."""

    review_id: int = Field(ge=1)
    author: str = Field(min_length=1)
    """Nom affiché de l'auteur de la revue."""
    state: ReviewState
    body_text: str = ""
    commit_sha: str = Field(pattern=SHA_PATTERN)
    """`head_sha` de la PR au moment de la revue."""
    created_at: str | None = None
    """Horodatage ISO 8601 de la revue ; `None` si le scénario l'a déclarée à l'ouverture
    (hors empreinte)."""

    def element(self, number: int) -> str:
        return element_id("review", str(number), str(self.review_id))


class BranchProtection(_Model):
    """Règles de protection d'une branche de `origin` (lues aussi par le hook `pre-receive`)."""

    branch: str = Field(min_length=1)
    required_approvals: int = Field(default=0, ge=0)
    required_checks: list[str] = Field(default_factory=list)
    """`job_id` des checks obligatoires pour merger vers cette branche."""
    block_direct_push: bool = True
    """Vrai : un push direct sur la branche est refusé (`pre-receive`, story 3.5)."""
    dismiss_stale_reviews: bool = False
    """Vrai : seules les revues du `head_sha` courant comptent (faux par défaut, comme GitHub)."""


class ReactionReview(_Model):
    """Une revue que la réaction publie, dans l'ordre où elle est déclarée."""

    state: ReviewState
    body_text: str = ""


class Firing(_Model):
    """Une PR (et son `head_sha` au moment du déclenchement) pour laquelle la réaction a joué."""

    number: int = Field(ge=1)
    head_sha: str = Field(pattern=SHA_PATTERN)


class Reaction(_Model):
    """Réaction déclarée par le scénario : à un événement de PR, le collègue publie ses revues.

    `pr_opened` joue une fois par PR ; `checks_green` joue une fois par `head_sha` (un nouveau
    push la réarme)."""

    reaction_id: int = Field(ge=1)
    trigger: ReactionTrigger
    author: str = Field(min_length=1)
    """Nom affiché de l'auteur des revues."""
    head: str | None = None
    """Branche de tête des PR concernées ; `None` : toutes."""
    reviews: list[ReactionReview] = Field(min_length=1)
    fired: list[Firing] = Field(default_factory=list)


class BlockReason(_Model):
    """Raison pour laquelle une PR n'est pas mergeable, calculée par `github_sim`."""

    kind: BlockKind
    text: str
    element_id: str


class PullRequest(_Model):
    """PR du GitHub simulé, numérotée à partir de 1 par espace."""

    number: int = Field(ge=1)
    title_text: str = ""
    head: str = Field(min_length=1)
    """Branche de tête (nom court, sur `origin`)."""
    base: str = Field(min_length=1)
    """Branche de base (nom court, sur `origin`)."""
    state: PrState = "open"
    head_sha: str = Field(pattern=SHA_PATTERN)
    base_sha: str = Field(pattern=SHA_PATTERN)
    checks: list[Check] = Field(default_factory=list)
    reviews: list[Review] = Field(default_factory=list)
    approvals: int = Field(default=0, ge=0)
    """Approbations comptées au dernier calcul (`count_approvals`)."""
    required_approvals: int = Field(default=0, ge=0)
    """Approbations requises : celles de la protection de la base."""
    protection: BranchProtection | None = None
    """Règles de protection de la base au dernier calcul ; `None` : base non protégée."""
    mergeable: bool = False
    blocking_reasons: list[BlockReason] = Field(default_factory=list)
    merge_sha: str | None = Field(default=None, pattern=SHA_PATTERN)

    @property
    def element(self) -> str:
        return element_id("pr", str(self.number))

    def count_approvals(self, *, head_sha: str | None = None) -> int:
        """Auteurs distincts dont la dernière revue décisive est une approbation.

        `head_sha` donné : seules les revues faites sur ce commit comptent."""
        last: dict[str, str] = {}
        for review in sorted(self.reviews, key=lambda r: r.review_id):
            if head_sha is not None and review.commit_sha != head_sha:
                continue
            if review.state != "commented":
                last[review.author] = review.state
        return sum(1 for state in last.values() if state == "approved")


class GithubState(_Model):
    """Contenu de `github.json`."""

    schema_version: Literal[1] = GITHUB_SCHEMA_VERSION
    next_number: int = Field(default=1, ge=1)
    """Numéro de la prochaine PR : jamais réutilisé dans l'espace."""
    protections: list[BranchProtection] = Field(default_factory=list)
    pulls: list[PullRequest] = Field(default_factory=list)
    reactions: list[Reaction] = Field(default_factory=list)
    """Réactions du collègue simulé, dans l'ordre de déclaration (ordre de jeu)."""

    def protection(self, branch: str) -> BranchProtection | None:
        return next((p for p in self.protections if p.branch == branch), None)

    def pull(self, number: int) -> PullRequest | None:
        return next((p for p in self.pulls if p.number == number), None)
