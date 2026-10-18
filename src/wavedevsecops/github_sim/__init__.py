"""GitHub simulé d'un espace : seul écrivain de `github.json` (AD-5, AD-8, AD-20).

`github.json` n'est écrit qu'ici, par écriture atomique (`wsfs.write_json`), depuis une
opération de la file de l'espace (le setup passe lui-même par la file, AD-1). Chaque écriture
part d'une lecture, applique la modification, puis recalcule toutes les PR ouvertes contre
les refs courantes de `origin.git` (`refresh`) : quand `head_sha` ou `base_sha` d'une PR
change, ses checks repassent à `queued` dans la même écriture, et `mergeable` et les raisons
de blocage sont recalculés.

Une PR est mergeable si chaque check obligatoire est `success` pour ses `head_sha` et
`base_sha` courants, si les approbations requises sont atteintes et s'il n'y a pas de conflit
(`git merge-tree --write-tree`, sans worktree).
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from pydantic import ValidationError

from wavedevsecops import gitio, wsfs
from wavedevsecops.contracts import AppError, element_id
from wavedevsecops.contracts.github import (
    GITHUB_SCHEMA_VERSION,
    BlockReason,
    BranchProtection,
    Check,
    CheckState,
    Finding,
    Firing,
    GithubState,
    PullRequest,
    Reaction,
    ReactionReview,
    ReactionTrigger,
    Review,
    ReviewState,
)
from wavedevsecops.gitio import Git, GitError
from wavedevsecops.wsfs import Layout

MIGRATIONS: dict[int, Callable[[dict[str, Any]], dict[str, Any]]] = {}
"""`MIGRATIONS[n]` fait passer un `github.json` de la version `n` à `n + 1` (en ajout seulement)."""

FINGERPRINT_EXCLUDED_CHECK_FIELDS = frozenset({"output", "duration_ms", "updated_at"})
"""Champs d'un check exclus de l'empreinte (AD-6) : sortie, durée, horodatage."""
FINGERPRINT_EXCLUDED_REVIEW_FIELDS = frozenset({"created_at"})
"""Champs d'une revue exclus de l'empreinte : l'heure (celle d'une réaction est réelle)."""


def now_iso() -> str:
    """Heure courante en ISO 8601 à la milliseconde (UTC) ; les tests la remplacent."""
    return datetime.now(UTC).isoformat(timespec="milliseconds")


STATE_TEXT: dict[str, str] = {
    "queued": "est en attente",
    "running": "est en cours",
    "failure": "a échoué",
    "error": "s'est terminé en erreur",
}


class GithubSimError(AppError):
    """Le GitHub simulé refuse ou ne peut pas lire son état."""


@dataclass(frozen=True)
class DeclaredCheck:
    """Check déclaré à l'ouverture d'une PR (scénario de test, station) : lié aux SHA courants."""

    job_id: str
    state: CheckState = "queued"
    required: bool = False
    output: str = ""
    findings: tuple[Finding, ...] = ()


@dataclass(frozen=True)
class DeclaredReview:
    """Revue déclarée par le scénario : liée au `head_sha` courant de la PR."""

    author: str
    state: ReviewState
    body_text: str = ""


@dataclass
class RefreshResult:
    """Résultat d'un recalcul : l'état écrit et les PR touchées."""

    state: GithubState
    sha_changed: list[int] = field(default_factory=list)
    """PR dont `head_sha` ou `base_sha` a changé (checks remis à `queued` : un run est à
    demander au pipeline simulé)."""
    updated: list[int] = field(default_factory=list)
    """PR dont le contenu a changé (`pr_updated` à émettre)."""


# --- Lecture, migrations, écriture -------------------------------------------------------


def _read_raw(layout: Layout) -> dict[str, Any] | None:
    path = layout.github_json
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_bytes().decode("utf-8"))
    except OSError, UnicodeDecodeError, json.JSONDecodeError:
        raise GithubSimError(
            "L'état du GitHub simulé de cet espace (github.json) est illisible.",
            "Recommencez le scénario pour reconstruire l'espace.",
        ) from None
    version = data.get("schema_version") if isinstance(data, dict) else None
    if not isinstance(version, int) or version < 1:
        raise GithubSimError(
            "L'état du GitHub simulé de cet espace (github.json) n'a pas de version valide.",
            "Recommencez le scénario pour reconstruire l'espace.",
        )
    if version > GITHUB_SCHEMA_VERSION:
        raise GithubSimError(
            "L'état du GitHub simulé de cet espace vient d'une version plus récente de "
            "WaveDevSecOps.",
            "Mettez WaveDevSecOps à jour pour rouvrir cet espace.",
        )
    while version < GITHUB_SCHEMA_VERSION:
        data = MIGRATIONS[version](data)
        version += 1
        data["schema_version"] = version
    return data


def load(layout: Layout) -> GithubState:
    """État du GitHub simulé (fichier absent : état vide), mis à la version courante en mémoire."""
    data = _read_raw(layout)
    if data is None:
        return GithubState()
    try:
        return GithubState.model_validate(data)
    except ValidationError:
        raise GithubSimError(
            "L'état du GitHub simulé de cet espace (github.json) est invalide.",
            "Recommencez le scénario pour reconstruire l'espace.",
        ) from None


def _save(layout: Layout, state: GithubState) -> None:
    wsfs.write_json(layout.github_json, state.model_dump(mode="json"))


def init(layout: Layout) -> GithubState:
    """Crée un `github.json` vide (`schema_version`, aucune PR) s'il n'existe pas."""
    if layout.github_json.is_file():
        return load(layout)
    state = GithubState()
    _save(layout, state)
    return state


def canonical_digest(layout: Layout) -> str | None:
    """sha256 de la sérialisation canonique de `github.json` pour l'empreinte (AD-6) :
    JSON trié, sans `checks[].output`, durées ni horodatages. Fichier absent : `None`."""
    if _read_raw(layout) is None:
        return None
    data = load(layout).model_dump(mode="json")
    for pull in data["pulls"]:
        for check in pull["checks"]:
            for name in FINGERPRINT_EXCLUDED_CHECK_FIELDS:
                check.pop(name, None)
        for review in pull["reviews"]:
            for name in FINGERPRINT_EXCLUDED_REVIEW_FIELDS:
                review.pop(name, None)
    if not data["reactions"]:
        del data["reactions"]  # sans réaction, l'empreinte reste celle d'avant la 3.4
    text = json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


# --- Lectures de origin.git ----------------------------------------------------------------


def origin_branches(git: Git, layout: Layout) -> dict[str, str]:
    """Branches de `origin.git` : nom court -> SHA."""
    prefix = "refs/heads/"
    return {
        name.removeprefix(prefix): target
        for name, target in gitio.refs(git, layout.origin)
        if name.startswith(prefix)
    }


def has_conflict(git: Git, layout: Layout, base_sha: str, head_sha: str) -> bool:
    """Vrai si merger `head_sha` dans `base_sha` donne un conflit (`merge-tree --write-tree`,
    sans worktree ni écriture de ref). Des historiques sans ancêtre commun comptent comme
    un conflit."""
    args = ("merge-tree", "--write-tree", "--no-messages", base_sha, head_sha)
    result = git.run(*args, cwd=layout.origin)
    if result.returncode == 0:
        return False
    if result.returncode == 1 or "unrelated histories" in result.stderr:
        return True
    raise GitError(args, result)


# --- Calcul de mergeable --------------------------------------------------------------------


ConflictProbe = Callable[[str, str], bool | None]
"""`(base_sha, head_sha) -> conflit ?` ; `None` : fusion impossible à calculer."""


def _requeue(check: Check, head_sha: str, base_sha: str) -> Check:
    return check.model_copy(
        update={
            "head_sha": head_sha,
            "base_sha": base_sha,
            "state": "queued",
            "output": "",
            "findings": [],
            "duration_ms": None,
            "updated_at": None,
        }
    )


def _check_reason(pr: PullRequest, check: Check) -> BlockReason | None:
    if check.state == "success" and (check.head_sha, check.base_sha) == (
        pr.head_sha,
        pr.base_sha,
    ):
        return None
    if check.state == "success":
        text = (
            f"Le check obligatoire « {check.job_id} » a réussi sur un ancien commit : "
            "il doit repasser sur le commit courant de la PR."
        )
    else:
        text = f"Le check obligatoire « {check.job_id} » {STATE_TEXT[check.state]}."
    return BlockReason(kind="check", text=text, element_id=check.element(pr.number))


def evaluate(
    pr: PullRequest,
    protection: BranchProtection | None,
    branches: dict[str, str],
    conflict: ConflictProbe,
) -> tuple[PullRequest, bool]:
    """Recalcule une PR ouverte contre les branches de `origin`.

    Rend la PR mise à jour et un drapeau vrai si `head_sha` ou `base_sha` a changé (ses
    checks sont alors remis à `queued`)."""
    if pr.state != "open":
        return pr, False
    required_checks = list(protection.required_checks) if protection else []
    checks = [
        c.model_copy(update={"required": c.required or c.job_id in required_checks})
        for c in pr.checks
    ]
    head_sha = branches.get(pr.head)
    base_sha = branches.get(pr.base)
    update: dict[str, Any] = {
        "protection": protection,
        "required_approvals": protection.required_approvals if protection else 0,
    }
    if head_sha is None or base_sha is None:
        missing = pr.head if head_sha is None else pr.base
        reason = BlockReason(
            kind="head_missing",
            text=(
                f"La branche « {missing} » n'existe pas sur origin : le GitHub simulé ne peut "
                "pas calculer cette PR."
            ),
            element_id=element_id("ref", f"refs/remotes/origin/{missing}"),
        )
        update |= {"checks": checks, "mergeable": False, "blocking_reasons": [reason]}
        return pr.model_copy(update=update), False
    sha_changed = (head_sha, base_sha) != (pr.head_sha, pr.base_sha)
    if sha_changed:
        checks = [_requeue(c, head_sha, base_sha) for c in checks]
    known = {c.job_id for c in checks}
    checks += [
        Check(job_id=job, head_sha=head_sha, base_sha=base_sha, required=True)
        for job in required_checks
        if job not in known
    ]
    current = pr.model_copy(update=update | {"head_sha": head_sha, "base_sha": base_sha})
    reasons = [r for c in checks if c.required and (r := _check_reason(current, c))]
    stale_dismissed = protection is not None and protection.dismiss_stale_reviews
    approvals = current.count_approvals(head_sha=head_sha if stale_dismissed else None)
    if approvals < current.required_approvals:
        reasons.append(
            BlockReason(
                kind="approvals",
                text=(
                    f"Approbations : {approvals} sur {current.required_approvals} requise(s) "
                    f"par la protection de « {pr.base} »."
                ),
                element_id=current.element,
            )
        )
    conflicting = conflict(base_sha, head_sha)
    if conflicting is None:
        reasons.append(
            BlockReason(
                kind="conflict",
                text=(
                    f"Le GitHub simulé n'a pas pu calculer la fusion de « {pr.head} » dans "
                    f"« {pr.base} » : la PR reste bloquée."
                ),
                element_id=current.element,
            )
        )
    elif conflicting:
        reasons.append(
            BlockReason(
                kind="conflict",
                text=(
                    f"La branche « {pr.head} » est en conflit avec « {pr.base} » : "
                    "résolvez le conflit, puis poussez à nouveau."
                ),
                element_id=current.element,
            )
        )
    current = current.model_copy(
        update={
            "checks": checks,
            "approvals": approvals,
            "mergeable": not reasons,
            "blocking_reasons": reasons,
        }
    )
    return current, sha_changed


def _recompute(git: Git, layout: Layout, state: GithubState) -> RefreshResult:
    branches = origin_branches(git, layout)
    cache: dict[tuple[str, str], bool | None] = {}

    def conflict(base_sha: str, head_sha: str) -> bool | None:
        key = (base_sha, head_sha)
        if key not in cache:
            try:
                cache[key] = has_conflict(git, layout, base_sha, head_sha)
            except GitError:
                cache[key] = None
        return cache[key]

    result = RefreshResult(state)
    pulls = []
    for pr in state.pulls:
        new, sha_changed = evaluate(pr, state.protection(pr.base), branches, conflict)
        if sha_changed:
            result.sha_changed.append(pr.number)
        if new != pr:
            result.updated.append(pr.number)
        pulls.append(new)
    result.state = state.model_copy(update={"pulls": pulls})
    return result


# --- Réactions du collègue simulé ---------------------------------------------------------------


def _checks_green(pr: PullRequest) -> bool:
    """Vrai si la PR a au moins un check obligatoire et que tous sont `success` (SHA courants :
    un changement de SHA les a remis à `queued`)."""
    required = [c for c in pr.checks if c.required]
    return bool(required) and all(c.state == "success" for c in required)


def _react(state: GithubState, opened: int | None) -> tuple[GithubState, list[int]]:
    """Joue les réactions dues : revues ajoutées dans l'ordre, une seule fois par déclencheur.

    `opened` : numéro de la PR qui vient d'être ouverte (déclencheur `pr_opened`). Rend l'état
    et les numéros de PR modifiées ; ne recalcule pas les approbations (l'appelant le fait)."""
    pulls = {p.number: p for p in state.pulls}
    reactions = []
    touched: set[int] = set()
    for reaction in state.reactions:
        fired = list(reaction.fired)
        for number, pr in pulls.items():
            if pr.state != "open" or reaction.head not in (None, pr.head):
                continue
            on_open = reaction.trigger == "pr_opened"
            if not (number == opened if on_open else _checks_green(pr)):
                continue
            if any(f.number == number and (on_open or f.head_sha == pr.head_sha) for f in fired):
                continue
            first = max((r.review_id for r in pr.reviews), default=0) + 1
            added = [
                Review(
                    review_id=first + offset,
                    author=reaction.author,
                    state=r.state,
                    body_text=r.body_text,
                    commit_sha=pr.head_sha,
                    created_at=now_iso(),
                )
                for offset, r in enumerate(reaction.reviews)
            ]
            pulls[number] = pr.model_copy(update={"reviews": [*pr.reviews, *added]})
            fired.append(Firing(number=number, head_sha=pr.head_sha))
            touched.add(number)
        reactions.append(reaction.model_copy(update={"fired": fired}))
    new = state.model_copy(
        update={"reactions": reactions, "pulls": [pulls[p.number] for p in state.pulls]}
    )
    return new, sorted(touched)


def _commit(
    git: Git,
    layout: Layout,
    state: GithubState,
    *,
    force: bool = False,
    opened: int | None = None,
) -> RefreshResult:
    """Recalcule, joue les réactions dues (ouverture, checks verts), puis écrit, en une seule
    écriture atomique."""
    result = _recompute(git, layout, state)
    reacted, touched = _react(result.state, opened)
    if touched:
        again = _recompute(git, layout, reacted)
        updated = sorted(set(result.updated) | set(touched) | set(again.updated))
        result = RefreshResult(again.state, result.sha_changed, updated)
        force = True
    if force or result.updated or not layout.github_json.is_file():
        _save(layout, result.state)
    return result


def refresh(git: Git, layout: Layout) -> RefreshResult:
    """Après un changement des refs de `origin` : recalcule toutes les PR ouvertes.

    N'écrit que si une PR a changé ; idempotent. Sans `github.json` (espace préparé avant le
    GitHub simulé), il n'y a aucune PR : rien n'est écrit."""
    if _read_raw(layout) is None:
        return RefreshResult(GithubState())
    return _commit(git, layout, load(layout))


# --- Modifications ----------------------------------------------------------------------------


def set_protection(git: Git, layout: Layout, protection: BranchProtection) -> RefreshResult:
    """Pose (ou remplace) la protection d'une branche, puis recalcule les PR."""
    state = load(layout)
    others = [p for p in state.protections if p.branch != protection.branch]
    protections = sorted([*others, protection], key=lambda p: p.branch)
    return _commit(git, layout, state.model_copy(update={"protections": protections}), force=True)


def add_reaction(
    layout: Layout,
    trigger: ReactionTrigger,
    author: str,
    reviews: Iterable[ReactionReview],
    *,
    head: str | None = None,
) -> Reaction:
    """Déclare une réaction du collègue simulé (numérotée dans l'ordre de déclaration).

    Elle joue aux événements de PR qui suivent : `pr_opened` à l'ouverture d'une PR (dont la
    tête est `head`, ou toute PR), `checks_green` quand les checks obligatoires passent tous à
    `success` (voir `_react`). Rien n'est joué à la déclaration."""
    state = load(layout)
    reaction = Reaction(
        reaction_id=len(state.reactions) + 1,
        trigger=trigger,
        author=author,
        head=head,
        reviews=list(reviews),
    )
    _save(layout, state.model_copy(update={"reactions": [*state.reactions, reaction]}))
    return reaction


def set_check_state(
    git: Git,
    layout: Layout,
    number: int,
    job_id: str,
    state: CheckState,
    *,
    output: str = "",
    findings: Iterable[Finding] = (),
) -> PullRequest:
    """Fixe l'état d'un check d'une PR ouverte (le pipeline simulé, plus tard, ou un test).

    Recalcule les PR et joue les réactions `checks_green` dues, dans la même écriture."""
    current = load(layout)
    pr = current.pull(number)
    check = None if pr is None else next((c for c in pr.checks if c.job_id == job_id), None)
    if pr is None or pr.state != "open" or check is None:
        raise GithubSimError(
            f"La PR n°{number} n'a pas de check « {job_id} » à mettre à jour.",
            "Choisissez une PR ouverte et un check qu'elle déclare.",
        )
    updated = check.model_copy(
        update={
            "state": state,
            "output": output,
            "findings": list(findings),
            "updated_at": now_iso(),
        }
    )
    checks = [updated if c.job_id == job_id else c for c in pr.checks]
    pulls = [
        p.model_copy(update={"checks": checks}) if p.number == number else p for p in current.pulls
    ]
    written = _commit(git, layout, current.model_copy(update={"pulls": pulls}), force=True)
    result = written.state.pull(number)
    assert result is not None
    return result


def open_pr(
    git: Git,
    layout: Layout,
    head: str,
    base: str = "main",
    *,
    title_text: str = "",
    checks: Iterable[DeclaredCheck] = (),
    reviews: Iterable[DeclaredReview] = (),
) -> PullRequest:
    """Ouvre une PR de `head` vers `base`, toutes deux sur `origin` ; rend la PR écrite."""
    branches = origin_branches(git, layout)
    for branch in (head, base):
        if branch not in branches:
            raise GithubSimError(
                f"La branche « {branch} » n'existe pas sur origin : le GitHub simulé ne peut "
                "pas ouvrir la PR.",
                "Poussez d'abord la branche vers origin, puis ouvrez la PR.",
            )
    if head == base:
        raise GithubSimError(
            f"La PR irait de « {head} » vers elle-même.",
            "Choisissez une branche de tête différente de la base.",
        )
    checks = list(checks)
    job_ids = [c.job_id for c in checks]
    if len(set(job_ids)) != len(job_ids):
        raise GithubSimError(
            "La PR déclare deux fois le même check.",
            "Déclarez chaque job_id une seule fois.",
        )
    state = load(layout)
    if any(p.state == "open" and (p.head, p.base) == (head, base) for p in state.pulls):
        raise GithubSimError(
            f"Une PR de « {head} » vers « {base} » est déjà ouverte.",
            "Ouvrez cette PR existante plutôt qu'une nouvelle.",
        )
    head_sha, base_sha = branches[head], branches[base]
    number = state.next_number
    declared_checks = [
        Check(
            job_id=c.job_id,
            head_sha=head_sha,
            base_sha=base_sha,
            state=c.state,
            required=c.required,
            output=c.output,
            findings=list(c.findings),
        )
        for c in checks
    ]
    declared_reviews = [
        Review(
            review_id=index,
            author=r.author,
            state=r.state,
            body_text=r.body_text,
            commit_sha=head_sha,
        )
        for index, r in enumerate(reviews, start=1)
    ]
    pr = PullRequest(
        number=number,
        title_text=title_text,
        head=head,
        base=base,
        head_sha=head_sha,
        base_sha=base_sha,
        checks=declared_checks,
        reviews=declared_reviews,
    )
    new_state = state.model_copy(update={"next_number": number + 1, "pulls": [*state.pulls, pr]})
    written = _commit(git, layout, new_state, force=True, opened=number).state.pull(number)
    assert written is not None
    return written


# --- Merge ----------------------------------------------------------------------------------


MERGE_IDENTITY = {
    "GIT_AUTHOR_NAME": "GitHub simulé",
    "GIT_AUTHOR_EMAIL": "github-sim@wavedevsecops.invalid",
    "GIT_COMMITTER_NAME": "GitHub simulé",
    "GIT_COMMITTER_EMAIL": "github-sim@wavedevsecops.invalid",
}
"""Identité fixe des merges écrits par le GitHub simulé (AD-8)."""


class MergeRaced(GithubSimError):
    """`base` a bougé sur `origin` entre le calcul et l'écriture : rien n'a été écrit."""


def merge_message(pr: PullRequest) -> str:
    return f"Merge pull request #{pr.number} from {pr.head}"


def _update_ref(git: Git, layout: Layout, ref: str, new: str, old: str) -> gitio.procs.ProcResult:
    """`update-ref` avec l'ancienne valeur attendue ; échoue si la ref a changé entre-temps."""
    return git.run("update-ref", ref, new, old, cwd=layout.origin)


def _already_merged(git: Git, layout: Layout, pr: PullRequest) -> str | None:
    """SHA du merge de `pr` si la pointe de `base` l'est déjà (écriture de github.json perdue
    après `update-ref`) ; `None` sinon."""
    args = ("log", "-1", "--format=%P%n%s", pr.base_sha)
    out = git.run(*args, cwd=layout.origin)
    if not out.ok:
        return None
    parents, _, subject = out.stdout.strip().partition("\n")
    parents_list = parents.split()
    if len(parents_list) == 2 and parents_list[1] == pr.head_sha and subject == merge_message(pr):
        return pr.base_sha
    return None


def _is_ancestor(git: Git, layout: Layout, ancestor: str, descendant: str) -> bool:
    args = ("merge-base", "--is-ancestor", ancestor, descendant)
    return git.run(*args, cwd=layout.origin).returncode == 0


def is_contained(git: Git, layout: Layout, sha: str, in_sha: str) -> bool:
    """Vrai si `sha` est déjà accessible depuis `in_sha` dans `origin.git` (rien à merger)."""
    return _is_ancestor(git, layout, sha, in_sha)


def _record_merged(
    git: Git, layout: Layout, state: GithubState, pr: PullRequest, merge_sha: str
) -> PullRequest:
    """Écrit la PR `merged` et recalcule les autres, sans relire github.json."""
    merged = pr.model_copy(
        update={
            "state": "merged",
            "merge_sha": merge_sha,
            "mergeable": False,
            "blocking_reasons": [],
        }
    )
    pulls = [merged if p.number == pr.number else p for p in state.pulls]
    try:
        written = _commit(git, layout, state.model_copy(update={"pulls": pulls}), force=True)
    except OSError:
        raise GithubSimError(
            f"Le merge de la PR n°{pr.number} est écrit dans origin, mais l'état des PR "
            "(github.json) n'a pas pu être enregistré.",
            "Relancez le merge de cette PR : il sera constaté sans nouveau commit.",
        ) from None
    result = written.state.pull(pr.number)
    assert result is not None
    return result


def merge_pr(git: Git, layout: Layout, number: int) -> PullRequest:
    """Merge la PR `number` dans `origin.git`, sans worktree ni `receive-pack` (AD-8).

    `merge-tree --write-tree` calcule l'arbre, `commit-tree` écrit le commit de merge (message
    et identité fixes), `update-ref` avance la base en vérifiant sa valeur d'avant. Refusé si la
    PR n'est pas mergeable après recalcul, ou si `head` est déjà contenue dans `base` (sauf
    merge déjà écrit par le GitHub simulé : il est alors seulement constaté) ; si la base a
    bougé, `MergeRaced` après un recalcul.
    """
    state = load(layout)
    pr = state.pull(number)
    if pr is None:
        raise GithubSimError(
            f"La PR n°{number} n'existe pas.", "Ouvrez d'abord une PR depuis une branche poussée."
        )
    if pr.state != "open":
        raise GithubSimError(
            f"La PR n°{number} n'est plus ouverte.", "Seule une PR ouverte peut être mergée."
        )
    state = _commit(git, layout, state).state
    pr = state.pull(number)
    assert pr is not None
    if not any(r.kind == "head_missing" for r in pr.blocking_reasons):
        done = _already_merged(git, layout, pr)
        if done is not None:
            return _record_merged(git, layout, state, pr, done)
        if _is_ancestor(git, layout, pr.head_sha, pr.base_sha):
            raise GithubSimError(
                f"La branche « {pr.head} » est déjà contenue dans « {pr.base} » : "
                "il n'y a rien à merger.",
                "Poussez de nouveaux commits sur la branche, puis réessayez.",
            )
    if not pr.mergeable:
        reasons = " ".join(r.text for r in pr.blocking_reasons)
        raise GithubSimError(
            f"La PR n°{number} ne peut pas être mergée : {reasons}",
            "Levez ces blocages, puis réessayez.",
        )
    tree_args = ("merge-tree", "--write-tree", pr.base_sha, pr.head_sha)
    tree = git.run(*tree_args, cwd=layout.origin)
    if not tree.ok:
        raise GitError(tree_args, tree)
    commit_args = (
        "commit-tree",
        tree.stdout.splitlines()[0].strip(),
        "-p",
        pr.base_sha,
        "-p",
        pr.head_sha,
        "-m",
        merge_message(pr),
    )
    commit = git.run(*commit_args, cwd=layout.origin, extra_env=MERGE_IDENTITY)
    if not commit.ok:
        raise GitError(commit_args, commit)
    merge_sha = commit.stdout.strip()
    ref = f"refs/heads/{pr.base}"
    moved = _update_ref(git, layout, ref, merge_sha, pr.base_sha)
    if not moved.ok:
        if origin_branches(git, layout).get(pr.base) == pr.base_sha:
            # La ref n'a pas bougé : l'échec vient de git, pas d'une course.
            raise GitError(("update-ref", ref, merge_sha, pr.base_sha), moved)
        _commit(git, layout, state)
        raise MergeRaced(
            f"La branche « {pr.base} » a bougé sur origin pendant le merge de la PR n°{number} : "
            "rien n'a été écrit.",
            "La PR a été recalculée ; relisez ses blocages, puis réessayez.",
        )
    return _record_merged(git, layout, state, pr, merge_sha)


__all__ = [
    "DeclaredCheck",
    "add_reaction",
    "now_iso",
    "set_check_state",
    "DeclaredReview",
    "GithubSimError",
    "MergeRaced",
    "RefreshResult",
    "merge_message",
    "merge_pr",
    "canonical_digest",
    "evaluate",
    "has_conflict",
    "init",
    "is_contained",
    "load",
    "open_pr",
    "origin_branches",
    "refresh",
    "set_protection",
]
