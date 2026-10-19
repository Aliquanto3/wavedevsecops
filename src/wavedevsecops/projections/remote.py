"""Vue « Distant + PR » : refs de `origin`, PR, checks, journal de revue (AD-2, FR-4, FR-6, FR-8).

Tout est calculé ici, à partir de `github.json` et des refs de `origin.git` : le front dessine.
La lecture est tolérante : un `github.json` ou un `origin.git` illisible donne une vue qui le
dit (`error_text`), jamais une projection en échec.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from typing import Any

from pydantic import ValidationError

from wavedevsecops import github_sim
from wavedevsecops.contracts import AppError, element_id
from wavedevsecops.contracts.github import BranchProtection, Check, GithubState, PullRequest, Review
from wavedevsecops.contracts.remote import (
    CheckDetail,
    CheckRow,
    CheckSpan,
    MergeReason,
    MergeState,
    PrCard,
    RemoteBranch,
    RemoteView,
    ReviewEntry,
    ReviewLog,
    SbomRow,
    SbomVulnRow,
)
from wavedevsecops.gitio import Git, GitError
from wavedevsecops.projections.spans import Linker
from wavedevsecops.wsfs import Layout

DEFAULT_BASE = "main"
SHORT = 7

CHECK_STATE_TEXT = {
    "queued": "En attente",
    "running": "En cours",
    "success": "Réussi",
    "failure": "Échec",
    "error": "Erreur de l'outil",
}
CHECK_ORDER = {"failure": 0, "error": 0, "running": 1, "queued": 1, "success": 2}
"""Ordre d'affichage : échecs et erreurs, puis en attente et en cours, puis réussis."""
PR_STATE_TEXT = {"open": "Ouverte", "merged": "Mergée", "closed": "Fermée"}
REVIEW_ACTION_TEXT = {
    "approved": "a approuvé",
    "changes_requested": "a demandé des modifications",
    "commented": "a commenté",
}
STALE_REVIEW_TEXT = "sur un commit remplacé"
BLOCKED_TEXT = "Cette PR ne peut pas être mergée."
NOT_OPEN_TEXT = "Cette PR n'est plus ouverte."
TOOL_ERROR_RULE = "tool_error"
"""Même valeur que `ci.TOOL_ERROR_RULE` (la projection n'importe pas `ci`)."""
MAX_DETAILS = 50
"""Lignes de détail d'un check dans la vue ; la sortie complète reste dans `tool-output`."""


def _short(sha: str) -> str:
    return sha[:SHORT]


def _count(n: int, one: str, many: str) -> str:
    return f"{n} {one if n == 1 else many}"


def branch_element(name: str) -> str:
    return element_id("ref", f"refs/remotes/origin/{name}")


def _duration_text(duration_ms: int | None) -> str:
    if duration_ms is None:
        return ""
    if duration_ms < 60_000:
        return f"{duration_ms / 1000:.1f} s".replace(".", ",")
    minutes, seconds = divmod(duration_ms // 1000, 60)
    return f"{minutes} min {seconds:02d} s"


def _time_text(moment: str | None) -> str:
    if not moment:
        return ""
    try:
        return datetime.fromisoformat(moment).strftime("%H:%M") + " UTC"
    except ValueError:
        return ""


def _protection_text(protection: BranchProtection | None) -> str:
    if protection is None:
        return ""
    parts = ["protégée"]
    if protection.required_approvals:
        parts.append(
            _count(protection.required_approvals, "approbation requise", "approbations requises")
        )
    if protection.required_checks:
        parts.append("checks : " + ", ".join(protection.required_checks))
    return " · ".join(parts)


def _details(check: Check, linker: Linker | None) -> tuple[list[CheckDetail], str]:
    """Lignes de détail (fichier:ligne lié s'il existe dans le bac à sable) et texte de
    l'erreur de l'outil, tirés des constats du check."""
    details: list[CheckDetail] = []
    tool_error = ""
    for finding in check.findings:
        if finding.rule_id == TOOL_ERROR_RULE:
            tool_error = tool_error or finding.message_text
            continue
        if len(details) >= MAX_DETAILS:
            continue
        location = ""
        link = ""
        if finding.path:
            location = f"{finding.path}:{finding.line}" if finding.line else finding.path
            spans = linker(finding.path) if linker is not None else []
            if spans and spans[0]["text"] == finding.path:
                link = spans[0]["element_id"]
        details.append(
            CheckDetail(
                rule_id=finding.rule_id,
                message_text=finding.message_text,
                location_text=location,
                link=link,
            )
        )
    return details, tool_error


REQUIREMENTS_FILE = "requirements.txt"
"""Même valeur que `ci.findings.REQUIREMENTS_FILE` (la projection n'importe pas `ci`)."""
NO_LICENSE_TEXT = "non indiquée"


def _sbom_rows(pr: PullRequest, check: Check) -> list[SbomRow]:
    """Lignes de `sbom-view` : composant, version, licence, vulnérabilités (✗ côté front)."""
    rows = []
    for item in check.sbom:
        vulns = [SbomVulnRow(vuln_id=v.vuln_id, text=v.vuln_id) for v in item.vulns]
        licenses = ", ".join(item.licenses) or NO_LICENSE_TEXT
        name = f"{item.name} {item.version}".strip()
        ids = ", ".join(v.vuln_id for v in vulns)
        verdict = f"vulnérable : {ids}" if vulns else "sans vulnérabilité"
        label = f"Composant {name}, licence {licenses}, {verdict}"
        links = [
            check.element(pr.number),
            element_id("path", "head", REQUIREMENTS_FILE),
            element_id("path", "head", "pyproject.toml"),
        ]
        rows.append(
            SbomRow(
                element_id=item.element(),
                name=item.name,
                version=item.version,
                license_text=licenses,
                vulnerable=bool(vulns),
                vulns=vulns,
                declared_text=f"{REQUIREMENTS_FILE}:{item.line}" if item.line else "",
                a11y_name_text=label,
                links=links,
            )
        )
    return rows


def _check_row(
    pr: PullRequest,
    check: Check,
    linker: Linker | None = None,
    pipeline_jobs: frozenset[str] = frozenset(),
) -> CheckRow:
    element = check.element(pr.number)
    required = check.required or (
        pr.protection is not None and check.job_id in pr.protection.required_checks
    )
    stale = pr.state == "open" and (check.head_sha, check.base_sha) != (pr.head_sha, pr.base_sha)
    state_text = CHECK_STATE_TEXT[check.state]
    name = f"Check {check.job_id}, {state_text.lower()}"
    if required:
        name += ", obligatoire"
    if stale:
        name += ", calculé sur un ancien commit"
    details, tool_error = _details(check, linker)
    spans = linker(check.output) if linker is not None and check.output else []
    return CheckRow(
        element_id=element,
        job_id=check.job_id,
        state=check.state,
        state_text=state_text,
        duration_text=_duration_text(check.duration_ms),
        required=required,
        stale=stale,
        a11y_name_text=name,
        links=[pr.element],
        output_text=check.output,
        output_spans=[CheckSpan(**span) for span in spans],
        details=details,
        sbom=_sbom_rows(pr, check),
        tool_error_text=tool_error,
        can_rerun=check.state == "error" and pr.state == "open" and not stale,
        in_pipeline=check.job_id in pipeline_jobs,
        output_element_id=element_id(
            "output", f"check-{pr.number}-{check.job_id}-{check.head_sha}"
        ),
    )


def _review_entry(pr: PullRequest, review: Review, stale_dismissed: bool) -> ReviewEntry:
    element = review.element(pr.number)
    action = REVIEW_ACTION_TEXT[review.state]
    stale = review.commit_sha != pr.head_sha
    name = f"Revue de {review.author} : {action}"
    if review.body_text:
        name += f", « {review.body_text} »"
    if stale and stale_dismissed:
        name += ", écartée (commit remplacé)"
    return ReviewEntry(
        element_id=element,
        author=review.author,
        state=review.state,
        action_text=action,
        body_text=review.body_text,
        time_text=_time_text(review.created_at),
        stale=stale,
        stale_text=STALE_REVIEW_TEXT if stale else "",
        a11y_name_text=name,
        links=[pr.element],
    )


REQUEST_WAITING_TEXT = (
    "Le collègue relit une PR dont la CI passe : attendez que les checks soient verts."
)


def _review_log(pr: PullRequest, can_request: bool = False) -> ReviewLog:
    stale_dismissed = pr.protection is not None and pr.protection.dismiss_stale_reviews
    required = pr.required_approvals
    counter = (
        f"Approbations : {pr.approvals} sur {required}"
        if required
        else (f"Approbations : {pr.approvals}")
    )
    required_text = (
        _count(required, "approbation requise", "approbations requises")
        if required
        else "Aucune approbation requise"
    )
    entries = [
        _review_entry(pr, r, stale_dismissed) for r in sorted(pr.reviews, key=lambda r: r.review_id)
    ]
    return ReviewLog(
        entries=entries,
        approvals=pr.approvals,
        required=required,
        counter_text=counter,
        required_text=required_text,
        can_request=can_request,
        request_enabled=can_request and github_sim.checks_green(pr),
        request_disabled_text=(
            REQUEST_WAITING_TEXT if can_request and not github_sim.checks_green(pr) else ""
        ),
    )


def _merge_state(pr: PullRequest) -> MergeState:
    if pr.state == "merged":
        sha = f" ({_short(pr.merge_sha)})" if pr.merge_sha else ""
        return MergeState(enabled=False, done_text=f"Mergée dans {pr.base}{sha}")
    if pr.state != "open":
        return MergeState(enabled=False, disabled_text=NOT_OPEN_TEXT)
    if pr.mergeable:
        return MergeState(enabled=True)
    reasons = [
        MergeReason(kind=r.kind, text=r.text, element_id=r.element_id) for r in pr.blocking_reasons
    ]
    return MergeState(enabled=False, disabled_text=BLOCKED_TEXT, reasons=reasons)


def _card(
    pr: PullRequest,
    current: bool,
    linker: Linker | None = None,
    pipeline_jobs: frozenset[str] = frozenset(),
    can_request: bool = False,
) -> PrCard:
    title = pr.title_text or f"PR n°{pr.number} : {pr.head}"
    checks = sorted(
        (_check_row(pr, c, linker, pipeline_jobs) for c in pr.checks),
        key=lambda row: (CHECK_ORDER[row.state], row.job_id),
    )
    state_text = PR_STATE_TEXT[pr.state]
    return PrCard(
        element_id=pr.element,
        number=pr.number,
        title_text=title,
        head=pr.head,
        base=pr.base,
        branches_text=f"{pr.head} → {pr.base}",
        state=pr.state,
        state_text=state_text,
        current=current,
        checks=checks,
        review=_review_log(pr, can_request),
        merge=_merge_state(pr),
        a11y_name_text=(
            f"PR n°{pr.number}, {title}, de {pr.head} vers {pr.base}, {state_text.lower()}"
        ),
        links=[branch_element(pr.head), branch_element(pr.base)],
    )


def _current_number(pulls: list[PullRequest], local_branch: str) -> int | None:
    """PR courante : l'ouverte de la branche locale courante, sinon la plus récente ouverte."""
    opened = [p for p in pulls if p.state == "open"]
    for pr in sorted(opened, key=lambda p: -p.number):
        if pr.head == local_branch:
            return pr.number
    return max((p.number for p in opened), default=None)


def _branches(
    git: Git, layout: Layout, state: GithubState, heads: dict[str, str]
) -> list[RemoteBranch]:
    opened = {p.head: p for p in state.pulls if p.state == "open"}
    base_sha = heads.get(DEFAULT_BASE)
    out: list[RemoteBranch] = []
    for name, sha in sorted(heads.items()):
        pr = opened.get(name)
        can_open = False
        if pr is None and name != DEFAULT_BASE and base_sha is not None:
            can_open = not github_sim.is_contained(git, layout, sha, base_sha)
        protection = state.protection(name)
        text = f"branche distante origin/{name}, commit {_short(sha)}"
        if pr is not None:
            text += f", PR n°{pr.number} ouverte"
        if protection is not None:
            text += ", protégée"
        out.append(
            RemoteBranch(
                element_id=branch_element(name),
                name_text=f"origin/{name}",
                sha=sha,
                short_sha=_short(sha),
                a11y_name_text=text,
                protection_text=_protection_text(protection),
                pr_number=pr.number if pr else None,
                can_open_pr=can_open,
                links=[element_id("commit", sha), *([pr.element] if pr else [])],
            )
        )
    return out


def build_remote(
    git: Git,
    layout: Layout,
    local_branch: str = "",
    linker: Linker | None = None,
    pipeline_jobs: frozenset[str] = frozenset(),
) -> RemoteView:
    """Vue « Distant + PR » de l'espace ; `local_branch` : nom court de la branche courante ;
    `linker` lie les fichier:ligne des sorties de checks aux fichiers du bac à sable ;
    `pipeline_jobs` : les `job_id` de `content/pipeline.yaml` (« Voir dans le pipeline »)."""
    try:
        state = github_sim.load(layout)
        heads = github_sim.origin_branches(git, layout) if layout.origin.is_dir() else {}
        branches = _branches(git, layout, state, heads)
    except AppError as error:
        return RemoteView(error_text=f"{error.cause_text} {error.action_text}")
    except GitError:
        return RemoteView(
            error_text="Les refs de origin n'ont pas pu être lues. Relancez une commande git."
        )
    current = _current_number(state.pulls, local_branch)
    cards = [
        _card(
            p,
            p.number == current,
            linker,
            pipeline_jobs,
            can_request=github_sim.pending_request(state, p),
        )
        for p in state.pulls
    ]
    order = {"open": 0, "merged": 1, "closed": 2}
    cards.sort(key=lambda c: (not c.current, order[c.state], -c.number))
    return RemoteView(branches=branches, pulls=cards)


def previous_remote(views: Mapping[str, Any] | None) -> RemoteView | None:
    """Vue distante de la projection précédente, si elle est lisible."""
    raw = (views or {}).get("remote")
    if not isinstance(raw, Mapping):
        return None
    try:
        return RemoteView.model_validate(raw)
    except ValidationError:
        return None


def announce_remote(before: RemoteView, after: RemoteView) -> str:
    """Résumé des changements de PR pour la région `role="status"` ; vide si rien ne change."""
    old = {c.number: c for c in before.pulls}
    parts: list[str] = []
    for card in sorted(after.pulls, key=lambda c: c.number):
        prev = old.get(card.number)
        if prev is None:
            parts.append(f"PR n°{card.number} ouverte, {card.branches_text}.")
        elif prev.state != card.state:
            parts.append(f"PR n°{card.number} : {card.state_text.lower()}.")
        elif card.state == "open" and prev.merge.enabled != card.merge.enabled:
            parts.append(
                f"PR n°{card.number} peut être mergée."
                if card.merge.enabled
                else f"PR n°{card.number} est bloquée."
            )
        if prev is not None and prev.review.approvals != card.review.approvals:
            parts.append(f"PR n°{card.number} : {card.review.counter_text}.")
    return " ".join(parts)
