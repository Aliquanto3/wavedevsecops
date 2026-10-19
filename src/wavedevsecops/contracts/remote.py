"""Projection de la vue « Distant + PR » (AD-2, AD-17) : refs de `origin`, PR, checks, revues.

Le serveur calcule tout : textes d'état, durées, raisons de blocage liées à leur élément,
compteurs d'approbations, disponibilité de « Merger » et d'« Ouvrir une PR ». Le front met en
forme. `element_id` émis (et lisibles par 2.10) : `ref:refs/remotes/origin/<branche>`,
`pr:<n>`, `check:<n>:<job_id>:<head_sha40>`, `review:<n>:<review_id>`. Ajouts seulement (AD-17).
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict

ReviewActor = Literal["colleague", "agent"]
# Mêmes valeurs que `contracts.github` (importé après ce module : pas d'import circulaire).
CheckState = Literal["queued", "running", "success", "failure", "error"]
PrState = Literal["open", "merged", "closed"]
ReviewState = Literal["approved", "changes_requested", "commented"]
BlockKind = Literal["check", "approvals", "conflict", "head_missing"]


class _Model(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class RemoteBranch(_Model):
    """Une branche de `origin` (`graph-remote-ref` du volet Distant)."""

    element_id: str
    """Le même que celui de l'étiquette du graphe : `ref:refs/remotes/origin/<branche>`."""
    name_text: str
    """`origin/feature`."""
    sha: str
    short_sha: str
    a11y_name_text: str
    protection_text: str = ""
    """« protégée · 2 approbations requises » ; vide si la branche n'est pas protégée."""
    pr_number: int | None = None
    """Numéro de la PR ouverte dont c'est la branche de tête."""
    can_open_pr: bool = False
    """Vrai : branche poussée, sans PR ouverte et avec du travail à merger (« Ouvrir une PR »)."""
    links: list[str] = []
    designable: bool = True
    """Désignable à l'étape courante (story 5.2, `engine.designation.mark_views`)."""


class CheckSpan(_Model):
    """Passage liable de la sortie d'un check (positions UTF-16, comme `terminal_output`)."""

    start: int
    end: int
    text: str
    element_id: str


class CheckDetail(_Model):
    """Ligne de détail d'un check (story 7.4) : règle, message, fichier:ligne lié à Code."""

    rule_id: str = ""
    message_text: str = ""
    location_text: str = ""
    """« src/app.py:12 » ; vide si le constat ne nomme pas de fichier."""
    link: str = ""
    """`element_id` du fichier dans le bac à sable ; vide s'il n'y existe pas."""


class CheckRow(_Model):
    """`pr-check` : un check de la PR."""

    element_id: str
    job_id: str
    state: CheckState
    state_text: str
    """« En attente », « En cours », « Réussi », « Échec », « Erreur de l'outil »."""
    duration_text: str = ""
    """« 2,4 s » ; vide si la durée n'est pas connue."""
    required: bool = False
    stale: bool = False
    """Calculé pour un ancien `head_sha`/`base_sha` de la PR."""
    a11y_name_text: str
    links: list[str] = []
    designable: bool = True
    """Désignable à l'étape courante (story 5.2, `engine.designation.mark_views`)."""
    output_text: str = ""
    """Sortie humaine de l'outil, verbatim (bloc `tool-output` de « Voir la sortie », 7.4)."""
    output_spans: list[CheckSpan] = []
    details: list[CheckDetail] = []
    """Constats de l'exécution machine (hors erreur de l'outil), dans l'ordre de l'outil."""
    tool_error_text: str = ""
    """« gitleaks s'est arrêté sans résultat (code 1). Ce n'est pas un défaut de votre code. »"""
    can_rerun: bool = False
    """« Relancer le check » (`check_rerun`) : erreur de l'outil sur les SHA courants."""
    output_element_id: str = ""
    """`output:check:<n>:<job_id>:<sha>` : le bloc `tool-output` déplié, désignable."""


class ReviewEntry(_Model):
    """Une entrée du `review-log`."""

    element_id: str
    author: str
    actor: ReviewActor = "colleague"
    state: ReviewState
    action_text: str
    """« a approuvé », « a demandé des modifications », « a commenté »."""
    body_text: str = ""
    time_text: str = ""
    """« 14:32 UTC » ; vide si la revue a été déclarée à l'ouverture, sans horodatage."""
    stale: bool = False
    """Revue faite sur un commit remplacé."""
    stale_text: str = ""
    a11y_name_text: str
    links: list[str] = []
    designable: bool = True
    """Désignable à l'étape courante (story 5.2, `engine.designation.mark_views`)."""


class ReviewLog(_Model):
    entries: list[ReviewEntry] = []
    approvals: int = 0
    required: int = 0
    counter_text: str = ""
    """« Approbations : 1 sur 2 »."""
    required_text: str = ""
    """« 2 approbations requises » ou « Aucune approbation requise »."""


class MergeReason(_Model):
    """Une raison de blocage (`merge-blocked`), liée à l'élément en cause."""

    kind: BlockKind
    text: str
    element_id: str


class MergeState(_Model):
    enabled: bool
    """Vrai seulement pour une PR ouverte et mergeable : « Merger » est actif."""
    disabled_text: str = ""
    """Raison courte quand le bouton est inactif."""
    reasons: list[MergeReason] = []
    done_text: str = ""
    """PR déjà mergée : « Mergée dans main (a1b2c3d) »."""


class PrCard(_Model):
    """`pr-card`."""

    element_id: str
    number: int
    title_text: str
    head: str
    base: str
    branches_text: str
    """« feature → main », affiché en code."""
    state: PrState
    state_text: str
    current: bool = False
    """La PR courante : celle de la branche locale courante, sinon la plus récente ouverte."""
    checks: list[CheckRow] = []
    """Dans l'ordre d'affichage : échecs et erreurs, puis en attente et en cours, puis réussis."""
    review: ReviewLog
    merge: MergeState
    a11y_name_text: str
    links: list[str] = []
    designable: bool = True
    """Désignable à l'étape courante (story 5.2, `engine.designation.mark_views`)."""


class RemoteView(_Model):
    """`views.remote` : refs de `origin` et PR du GitHub simulé."""

    branches: list[RemoteBranch] = []
    pulls: list[PrCard] = []
    """La PR courante d'abord, puis les autres ouvertes (récentes d'abord), puis les mergées."""
    error_text: str = ""
    """Le GitHub simulé ou `origin` n'a pas pu être lu ; la vue le dit au lieu de rester vide."""
