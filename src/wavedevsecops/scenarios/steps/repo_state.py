"""Étape validée par des conditions sur l'état réel du dépôt : refs, commits, index, arbre, stash.

La validation porte sur le `RepoState` relu après la commande, jamais sur le texte tapé : toute
commande qui mène à l'état attendu valide l'étape (AD-7). `expect` liste les conditions, toutes
nécessaires ; `foreseen` décrit des états prévus mais pas encore suffisants, chacun avec sa
raison. Un état qui bouge sans être ni attendu ni prévu donne `unexpected`.

Conditions ajoutées par la story 6.3, toutes optionnelles (absentes, rien ne change) :
- `head.contains`, `branches[].contains` : tel commit (`@alias`, ref, SHA) est accessible depuis
  HEAD ou la branche ; un nouveau commit au même message ne le remplace pas ;
- `commits[].merges` : `false` exige un historique linéaire (aucun commit de fusion parmi les
  commits comptés), `true` au moins un commit de fusion ;
- `tree.markers_absent`, `tree.markers_present` : marqueurs de conflit (lignes `<<<<<<<`,
  `=======`, `>>>>>>>`) absents ou présents dans ces fichiers de l'arbre de travail ;
- `tree.contains` : tel fichier contient tel texte (fins de ligne normalisées en LF).
Les conditions de contenu lisent le fichier dans le dépôt de l'espace (`ctx.layout.repo`) :
sans espace, ou si le fichier est absent ou illisible, elles échouent (échec fermé).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from wavedevsecops.contracts import (
    Commit,
    InProgress,
    RepoState,
    element_id,
    parse_element_id,
)
from wavedevsecops.scenarios.steps._base import Observed, StepArgs, StepContext, Verdict

SHORT = 7
HEAD_ID = element_id("ref", "HEAD")
MAX_READ = 1 << 20
"""Taille lue au plus pour une condition de contenu (octets)."""
MARKER = re.compile(r"^(?:(?:<{7}|>{7}|\|{7})(?: .*)?|={7})$", re.MULTILINE)
"""Ligne de marqueur de conflit : `<<<<<<<`, `|||||||`, `>>>>>>>` (suivis ou non d'une
étiquette) ou `=======` seul sur sa ligne."""
GENERIC_UNEXPECTED_TEXT = (
    "Le dépôt a changé, mais pas dans le sens que cette étape attend, et ce n'est pas un état "
    "qu'elle prévoyait. Rien n'est bloqué : vous pouvez continuer, relire l'état du dépôt ou "
    "reprendre la consigne."
)


class _Cond(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class HeadCond(_Cond):
    """HEAD : branche courante, détachée, ou sur un commit donné."""

    branch: str | None = None
    """Nom court de la branche locale (ou `@alias`) que HEAD doit porter."""
    detached: bool | None = None
    at: str | None = None
    """Commit visé par HEAD : `@alias`, nom de ref ou `HEAD`."""
    contains: str | None = None
    """Commit (`@alias`, ref, SHA) qui doit être accessible depuis HEAD."""


class BranchCond(_Cond):
    name: str
    """Nom court de la branche locale, ou `@alias`."""
    exists: bool = True
    at: str | None = None
    """Commit visé : `@alias`, nom de ref (`main`, `origin/main`) ou `HEAD`."""
    contains: str | None = None
    """Commit (`@alias`, ref, SHA) qui doit être accessible depuis la branche."""


class TagCond(_Cond):
    name: str
    exists: bool = True
    annotated: bool | None = None


class CommitsCond(_Cond):
    """Commits accessibles depuis `on` mais pas depuis `ahead_of`."""

    on: str = "HEAD"
    ahead_of: str | None = None
    min: int = Field(default=1, ge=0)
    subject_contains: str | None = None
    """Un de ces commits a un sujet qui contient ce texte (sans tenir compte de la casse)."""
    merges: bool | None = None
    """`False` : aucun de ces commits n'est une fusion (historique linéaire) ; `True` : au
    moins un l'est."""


class IndexCond(_Cond):
    """Index et arbre de travail, comme `git status`."""

    staged: list[str] = []
    unstaged: list[str] = []
    untracked: list[str] = []
    tracked: list[str] = []
    clean: bool | None = None


def _safe_path(path: str) -> str:
    pure = PurePosixPath(path)
    if not path or "\\" in path or ":" in path or pure.is_absolute() or ".." in pure.parts:
        raise ValueError(f"chemin relatif au dépôt attendu : {path!r}")
    return path


class FileText(_Cond):
    """Un fichier de l'arbre de travail et un texte qu'il doit contenir."""

    path: str
    text: str = Field(min_length=1)

    @field_validator("path")
    @classmethod
    def _path(cls, value: str) -> str:
        return _safe_path(value)


class TreeCond(_Cond):
    """Fichiers présents dans l'arbre de travail, et leur contenu."""

    present: list[str] = []
    absent: list[str] = []
    markers_absent: list[str] = []
    """Fichiers présents sans aucun marqueur de conflit."""
    markers_present: list[str] = []
    """Fichiers qui contiennent encore au moins un marqueur de conflit."""
    contains: list[FileText] = []
    """Fichiers qui contiennent un texte (comparaison exacte, fins de ligne normalisées)."""

    @field_validator("markers_absent", "markers_present")
    @classmethod
    def _paths(cls, value: list[str]) -> list[str]:
        return [_safe_path(v) for v in value]


class StashCond(_Cond):
    count: int | None = Field(default=None, ge=0)
    min: int | None = Field(default=None, ge=0)
    message_contains: str | None = None


class Conditions(_Cond):
    """Conditions sur l'état du dépôt, toutes nécessaires."""

    head: HeadCond | None = None
    branches: list[BranchCond] = []
    tags: list[TagCond] = []
    commits: list[CommitsCond] = []
    index: IndexCond | None = None
    tree: TreeCond | None = None
    stash: StashCond | None = None
    in_progress: InProgress | None = None

    @model_validator(mode="after")
    def _not_empty(self) -> Conditions:
        if not any(getattr(self, name) not in (None, []) for name in type(self).model_fields):
            raise ValueError("au moins une condition est attendue")
        return self


class Foreseen(_Cond):
    """État prévu mais pas encore suffisant : la raison est montrée à l'apprenant."""

    when: Conditions
    reason_text: str = Field(min_length=1)


MISSING_FORESEEN_TEXT = (
    "aucun état prévu : un pas intermédiaire licite (par exemple `git add` avant `git commit`) "
    "ouvrira l'encart « État inattendu » ; décrivez-le dans `foreseen`"
)


class Args(StepArgs):
    type: Literal["repo_state"]
    expect: Conditions
    foreseen: list[Foreseen] = []

    def authoring_warnings(self) -> list[tuple[tuple[str | int, ...], str]]:
        """Règle actuelle : tout état qui change sans être attendu ni prévu est « inattendu ».
        Une étape qui attend un commit ou un stash passe presque toujours par un état
        intermédiaire (fichiers indexés, modifiés) : sans `foreseen`, l'auteur est averti."""
        multi = self.expect.commits or self.expect.stash is not None
        return [(("foreseen",), MISSING_FORESEEN_TEXT)] if multi and not self.foreseen else []


@dataclass
class Finding:
    ok: bool
    expected: str
    observed: list[Observed] = field(default_factory=list)


class _State:
    """Recherches dans le `RepoState` pour évaluer les conditions."""

    def __init__(self, state: RepoState, aliases: dict[str, str], repo: Path | None = None) -> None:
        self.state = state
        self.aliases = aliases
        self.repo = repo
        self.commits: dict[str, Commit] = {c.sha: c for c in state.commits}
        self._texts: dict[str, str | None] = {}

    def text(self, path: str) -> str | None:
        """Contenu du fichier (fins de ligne LF) ; `None` s'il est absent ou illisible."""
        if path not in self._texts:
            self._texts[path] = self._read(path)
        return self._texts[path]

    def _read(self, path: str) -> str | None:
        if self.repo is None:
            return None
        try:
            root = Path(self.repo).resolve()
            target = (root / path).resolve()
            if not target.is_relative_to(root) or not target.is_file():
                return None
            with target.open("rb") as handle:
                data = handle.read(MAX_READ)
        except OSError:
            return None
        text = data.decode("utf-8", errors="replace")
        return text.replace("\r\n", "\n").replace("\r", "\n")

    def alias(self, value: str) -> tuple[str, str]:
        """`(type, valeur)` de l'élément désigné par `@alias` ; `("", "")` s'il est inconnu."""
        target = self.aliases.get(value[1:])
        if not target:
            return "", ""
        try:
            kind, segments = parse_element_id(target)
        except ValueError:
            return "", ""
        return kind, segments[0] if segments else ""

    def branch_name(self, value: str) -> str:
        if not value.startswith("@"):
            return value
        _, name = self.alias(value)
        return name.removeprefix("refs/heads/")

    def tag_name(self, value: str) -> str:
        if not value.startswith("@"):
            return value
        _, name = self.alias(value)
        return name.removeprefix("refs/tags/")

    def commit(self, spec: str) -> str | None:
        """SHA du commit désigné par `HEAD`, `@alias`, une ref ou un SHA."""
        if spec == "HEAD":
            return self.state.head.commit or None
        if spec.startswith("@"):
            kind, value = self.alias(spec)
            if not value:
                return None
            if kind == "commit":
                return value
            spec = value
        if len(spec) == 40 and spec in self.commits:
            return spec
        for wanted in ("branch", "tag", "remote"):
            for ref in self.state.refs:
                if ref.kind == wanted and spec in (ref.short_name, ref.name):
                    return ref.commit or None
        for ref in self.state.refs:
            if spec == ref.name:
                return ref.commit or None
        return None

    def reachable(self, sha: str | None) -> set[str]:
        seen: set[str] = set()
        todo = [sha] if sha else []
        while todo:
            current = todo.pop()
            if current in seen or current not in self.commits:
                continue
            seen.add(current)
            todo.extend(self.commits[current].parents)
        return seen

    def branch(self, name: str):
        return next(
            (r for r in self.state.refs if r.kind == "branch" and r.short_name == name), None
        )

    def tag(self, name: str):
        return next((r for r in self.state.refs if r.kind == "tag" and r.short_name == name), None)

    def head_text(self) -> Observed:
        head = self.state.head
        if head.detached:
            where = f" sur `{head.commit[:SHORT]}`" if head.commit else ""
            return Observed(text=f"HEAD est détachée{where}.", element_id=HEAD_ID)
        name = head.ref.removeprefix("refs/heads/")
        return Observed(text=f"HEAD est sur la branche `{name}`.", element_id=HEAD_ID)

    def path_id(self, path: str, zone: str = "worktree") -> str:
        return element_id("path", zone, path) if path in self.state.worktree else ""


def _commit_observed(sha: str | None, text: str) -> Observed:
    return Observed(text=text, element_id=element_id("commit", sha) if sha else "")


def _contains(spec: str, tip: str | None, where: str, st: _State) -> Finding:
    """`spec` est accessible depuis `tip` (le même commit, pas un commit au même message)."""
    target = st.commit(spec)
    ok = target is not None and target in st.reachable(tip)
    shown = target[:SHORT] if target else spec.removeprefix("@")
    observed = [_commit_observed(target, f"Le commit `{shown}` n'est pas dans {where}.")]
    return Finding(ok, f"le commit `{shown}` dans {where}", [] if ok else observed)


def _head(cond: HeadCond, st: _State) -> list[Finding]:
    head = st.state.head
    found = []
    if cond.branch is not None:
        name = st.branch_name(cond.branch)
        ok = not head.detached and head.ref == f"refs/heads/{name}"
        found.append(Finding(ok, f"HEAD sur la branche `{name}`", [] if ok else [st.head_text()]))
    if cond.detached is not None:
        ok = head.detached == cond.detached
        wanted = "HEAD détachée" if cond.detached else "HEAD sur une branche"
        found.append(Finding(ok, wanted, [] if ok else [st.head_text()]))
    if cond.at is not None:
        target = st.commit(cond.at)
        ok = target is not None and head.commit == target
        shown = target[:SHORT] if target else cond.at
        found.append(
            Finding(
                ok,
                f"HEAD sur le commit `{shown}`",
                [] if ok else [_commit_observed(head.commit or None, st.head_text().text)],
            )
        )
    if cond.contains is not None:
        found.append(_contains(cond.contains, head.commit or None, "l'historique de HEAD", st))
    return found


def _branch(cond: BranchCond, st: _State) -> list[Finding]:
    name = st.branch_name(cond.name)
    ref = st.branch(name)
    if not cond.exists:
        observed = [Observed(text=f"La branche `{name}` existe.", element_id=_ref_id(ref))]
        return [Finding(ref is None, f"pas de branche `{name}`", [] if ref is None else observed)]
    if ref is None:
        missing = Observed(text=f"La branche `{name}` n'existe pas.")
        return [Finding(False, f"la branche `{name}`", [missing])]
    found = [Finding(True, f"la branche `{name}`")]
    if cond.at is not None:
        target = st.commit(cond.at)
        ok = target is not None and ref.commit == target
        shown = target[:SHORT] if target else cond.at
        observed = [
            _commit_observed(ref.commit or None, f"`{name}` pointe sur `{ref.commit[:SHORT]}`.")
        ]
        found.append(Finding(ok, f"`{name}` sur le commit `{shown}`", [] if ok else observed))
    if cond.contains is not None:
        found.append(_contains(cond.contains, ref.commit or None, f"`{name}`", st))
    return found


def _ref_id(ref) -> str:
    if ref is None:
        return ""
    return element_id("tag", ref.short_name) if ref.kind == "tag" else element_id("ref", ref.name)


def _tag(cond: TagCond, st: _State) -> list[Finding]:
    name = st.tag_name(cond.name)
    ref = st.tag(name)
    if not cond.exists:
        observed = [Observed(text=f"Le tag `{name}` existe.", element_id=_ref_id(ref))]
        return [Finding(ref is None, f"pas de tag `{name}`", [] if ref is None else observed)]
    if ref is None:
        return [
            Finding(False, f"le tag `{name}`", [Observed(text=f"Le tag `{name}` n'existe pas.")])
        ]
    if cond.annotated is not None and ref.annotated != cond.annotated:
        kind = "annoté" if cond.annotated else "léger"
        have = "annoté" if ref.annotated else "léger"
        observed = Observed(text=f"Le tag `{name}` est {have}.", element_id=_ref_id(ref))
        return [Finding(False, f"le tag {kind} `{name}`", [observed])]
    return [Finding(True, f"le tag `{name}`")]


def _commits(cond: CommitsCond, st: _State) -> list[Finding]:
    tip = st.commit(cond.on)
    where = f" depuis `{cond.ahead_of.removeprefix('@')}`" if cond.ahead_of else ""
    # Échec fermé : une référence introuvable ne compte jamais comme une base vide.
    missing = [
        spec for spec in (cond.on, cond.ahead_of) if spec is not None and st.commit(spec) is None
    ]
    if missing:
        noun = "commit" if cond.min == 1 else "commits"
        return [
            Finding(
                False,
                f"au moins {cond.min} {noun} sur `{cond.on.removeprefix('@')}`{where}",
                [
                    Observed(text=f"`{spec.removeprefix('@')}` est introuvable dans le dépôt.")
                    for spec in missing
                ],
            )
        ]
    base = st.reachable(st.commit(cond.ahead_of)) if cond.ahead_of else set()
    new = [st.commits[sha] for sha in st.reachable(tip) - base]
    found = []
    ok = len(new) >= cond.min
    noun = "commit" if cond.min == 1 else "commits"
    found.append(
        Finding(
            ok,
            f"au moins {cond.min} {noun} sur `{cond.on.removeprefix('@')}`{where}",
            [] if ok else [_commit_observed(tip, f"{len(new)} commit(s) trouvé(s){where}.")],
        )
    )
    if cond.subject_contains is not None:
        needle = cond.subject_contains.lower()
        ok = any(needle in c.subject.lower() for c in new)
        found.append(
            Finding(
                ok,
                f"un commit dont le message contient « {cond.subject_contains} »",
                [] if ok else [_commit_observed(tip, "Aucun commit ne porte ce message.")],
            )
        )
    if cond.merges is not None:
        merge = next((c for c in new if len(c.parents) > 1), None)
        ok = (merge is not None) == cond.merges
        wanted = "un commit de fusion" if cond.merges else "un historique linéaire, sans fusion"
        if merge is not None:
            seen = _commit_observed(merge.sha, f"`{merge.sha[:SHORT]}` est un commit de fusion.")
        else:
            seen = _commit_observed(tip, f"Aucun commit de fusion{where}.")
        found.append(Finding(ok, wanted, [] if ok else [seen]))
    return found


def _status_paths(st: _State, test) -> set[str]:
    return {e.path for e in st.state.status if test(e)}


def _index(cond: IndexCond, st: _State) -> list[Finding]:
    status = st.state.status
    staged = _status_paths(
        st, lambda e: e.kind in {"changed", "renamed"} and e.index_status not in {".", "?"}
    )
    unstaged = _status_paths(
        st, lambda e: e.kind in {"changed", "renamed"} and e.worktree_status not in {".", "?"}
    )
    untracked = _status_paths(st, lambda e: e.kind == "untracked")
    tracked = {e.path for e in st.state.index if e.stage == 0}
    found = []
    groups = (
        ("indexé", cond.staged, staged),
        ("modifié et non indexé", cond.unstaged, unstaged),
        ("non suivi", cond.untracked, untracked),
        ("suivi par git", cond.tracked, tracked),
    )
    for label, wanted, have in groups:
        for path in wanted:
            ok = path in have
            observed = Observed(text=f"`{path}` n'est pas {label}.", element_id=st.path_id(path))
            found.append(Finding(ok, f"`{path}` {label}", [] if ok else [observed]))
    if cond.clean is not None:
        ok = (not status) == cond.clean
        wanted = "aucun changement en attente" if cond.clean else "des changements en attente"
        have = f"{len(status)} fichier(s) en attente." if status else "Aucun changement en attente."
        found.append(Finding(ok, wanted, [] if ok else [Observed(text=have)]))
    return found


def _tree(cond: TreeCond, st: _State) -> list[Finding]:
    present = set(st.state.worktree)
    found = []
    for path in cond.present:
        ok = path in present
        observed = Observed(text=f"`{path}` est absent de l'arbre de travail.")
        found.append(Finding(ok, f"`{path}` présent", [] if ok else [observed]))
    for path in cond.absent:
        ok = path not in present
        observed = Observed(text=f"`{path}` est présent.", element_id=st.path_id(path))
        found.append(Finding(ok, f"`{path}` absent", [] if ok else [observed]))
    for path in cond.markers_absent:
        text = st.text(path)
        ok = text is not None and not MARKER.search(text)
        seen = "est illisible" if text is None else "contient encore des marqueurs de conflit"
        observed = Observed(text=f"`{path}` {seen}.", element_id=st.path_id(path))
        found.append(Finding(ok, f"`{path}` sans marqueur de conflit", [] if ok else [observed]))
    for path in cond.markers_present:
        text = st.text(path)
        ok = text is not None and bool(MARKER.search(text))
        observed = Observed(text=f"`{path}` n'a pas de marqueur.", element_id=st.path_id(path))
        found.append(Finding(ok, f"`{path}` avec marqueurs de conflit", [] if ok else [observed]))
    for item in cond.contains:
        text = st.text(item.path)
        needle = item.text.replace("\r\n", "\n")
        ok = text is not None and needle in text
        observed = Observed(
            text=f"`{item.path}` ne contient pas le texte attendu.",
            element_id=st.path_id(item.path),
        )
        wanted = f"`{item.path}` contient « {item.text.strip()} »"
        found.append(Finding(ok, wanted, [] if ok else [observed]))
    return found


def _stash(cond: StashCond, st: _State) -> list[Finding]:
    entries = st.state.stash
    have = Observed(text=f"{len(entries)} entrée(s) dans le stash.")
    found = []
    if cond.count is not None:
        found.append(
            Finding(len(entries) == cond.count, f"{cond.count} entrée(s) dans le stash", [have])
        )
    if cond.min is not None:
        found.append(
            Finding(
                len(entries) >= cond.min, f"au moins {cond.min} entrée(s) dans le stash", [have]
            )
        )
    if cond.message_contains is not None:
        needle = cond.message_contains.lower()
        ok = any(needle in e.message.lower() for e in entries)
        found.append(
            Finding(ok, f"un stash dont le message contient « {cond.message_contains} »", [have])
        )
    return found


def evaluate(cond: Conditions, st: _State) -> list[Finding]:
    """Une `Finding` par condition élémentaire de `cond`."""
    found: list[Finding] = []
    if cond.head is not None:
        found += _head(cond.head, st)
    for branch in cond.branches:
        found += _branch(branch, st)
    for tag in cond.tags:
        found += _tag(tag, st)
    for commits in cond.commits:
        found += _commits(commits, st)
    if cond.index is not None:
        found += _index(cond.index, st)
    if cond.tree is not None:
        found += _tree(cond.tree, st)
    if cond.stash is not None:
        found += _stash(cond.stash, st)
    if cond.in_progress is not None:
        ok = st.state.in_progress == cond.in_progress
        wanted = (
            f"opération en cours : {cond.in_progress}"
            if cond.in_progress
            else "aucune opération en cours"
        )
        have = st.state.in_progress or "aucune"
        found.append(
            Finding(ok, wanted, [] if ok else [Observed(text=f"Opération en cours : {have}.")])
        )
    return found


def _join(texts: list[str]) -> str:
    unique = list(dict.fromkeys(texts))
    return "Attendu : " + " ; ".join(unique) + "." if unique else ""


def check(state: RepoState | None, ctx: StepContext) -> Verdict:
    """Jugement de l'état : réussi, prévu mais insuffisant, inattendu, ou rien à dire."""
    if state is None:
        return Verdict(status="pending")  # dépôt illisible : la projection l'a déjà signalé
    step: Args = ctx.step
    layout = getattr(ctx, "layout", None)
    st = _State(state, ctx.aliases, getattr(layout, "repo", None))
    findings = evaluate(step.expect, st)
    failed = [f for f in findings if not f.ok]
    if not failed:
        return Verdict(status="passed")
    if ctx.previous is not None and ctx.previous == state:
        return Verdict(status="pending")  # lecture seule ou sans effet : rien à signaler
    expected = _join([f.expected for f in findings])
    observed = [o for f in failed for o in f.observed]
    for foreseen in step.foreseen:
        if all(f.ok for f in evaluate(foreseen.when, st)):
            return Verdict(
                status="failed",
                reason_text=foreseen.reason_text,
                expected_text=expected,
                observed=observed,
            )
    return Verdict(
        status="unexpected",
        reason_text=step.unexpected_text or GENERIC_UNEXPECTED_TEXT,
        expected_text=expected,
        observed=observed,
    )
