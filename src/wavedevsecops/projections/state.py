"""Lecture du `RepoState` par le contexte interne de git (AD-2, AD-3).

Commandes plumbing ou porcelain stables, en `LC_ALL=C`, jamais affichées : `for-each-ref`,
`rev-list`, `status --porcelain=v2 -z`, `ls-files -s -z`, `ls-files -z`, `stash list` et
`log -g` (reflog). Les tags annotés sont déréférencés par `for-each-ref` (`%(*objectname)`),
ce qui évite un `cat-file` par tag ; un tag de tag, qu'un git ancien ne déréférence que d'un
niveau, l'est par `rev-parse`. Les sorties sont découpées sur `\n` ou NUL seulement :
`splitlines()` couperait aussi sur U+0085, U+2028 ou U+2029, permis dans un nom de ref.

Commits retenus : ceux qu'une ref (hors `refs/stash`) ou HEAD rend accessibles, comme
`git log --all` sans le stash, puis ceux qu'un reflog cite encore sans qu'aucune ref n'y
mène (perdus). Les commits internes du stash n'y figurent pas : le stash est listé à part.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from pathlib import Path

from wavedevsecops.contracts import (
    Actor,
    Commit,
    Head,
    IndexEntry,
    InProgress,
    Ref,
    RefKind,
    RepoState,
    StashEntry,
    StatusEntry,
)
from wavedevsecops.gitio import Git

_FIELDS = ("%H", "%P", "%T", "%an", "%ae", "%aI", "%cn", "%ce", "%cI", "%ct", "%s", "%B")
COMMIT_FORMAT = "%x1e" + "%x1f".join(_FIELDS) + "%x00"
"""Un enregistrement par commit, entre `\\x1e` et `\\x00` (un message ne contient pas NUL)."""
_RECORD = re.compile("\x1e(.*?)\x00", re.DOTALL)
_REF_FORMAT = "%00".join(
    (
        "%(refname)",
        "%(objectname)",
        "%(objecttype)",
        "%(*objectname)",
        "%(*objecttype)",
        "%(symref)",
        "%(upstream)",
    )
)
_REFLOG_KINDS: frozenset[RefKind] = frozenset({"branch", "remote"})


def _ref_kind(name: str) -> tuple[RefKind, str]:
    for prefix, kind in (
        ("refs/heads/", "branch"),
        ("refs/remotes/", "remote"),
        ("refs/tags/", "tag"),
    ):
        if name.startswith(prefix):
            return kind, name[len(prefix) :]  # type: ignore[return-value]
    if name == "refs/stash":
        return "stash", "stash"
    return "other", name.removeprefix("refs/")


def read_refs(git: Git, repo: Path) -> list[Ref]:
    """Refs du dépôt, triées par nom complet ; un tag annoté est déréférencé."""
    out = git.internal("for-each-ref", f"--format={_REF_FORMAT}", cwd=repo)
    found: list[Ref] = []
    for line in out.split("\n"):
        if not line:
            continue
        name, target, otype, peeled, ptype, symref, upstream = line.split("\0")
        kind, short = _ref_kind(name)
        if ptype == "tag":
            result = git.run("rev-parse", "--verify", "-q", f"{target}^{{commit}}", cwd=repo)
            commit = result.stdout.strip() if result.ok else ""
        elif peeled:
            commit = peeled if ptype == "commit" else ""
        else:
            commit = target if otype == "commit" else ""
        found.append(
            Ref(
                name=name,
                kind=kind,
                short_name=short,
                target=target,
                commit=commit,
                annotated=otype == "tag",
                symref=symref,
                upstream=upstream,
            )
        )
    return sorted(found, key=lambda r: r.name)


def _split_z(output: str) -> list[str]:
    return output.split("\0")


def read_status(git: Git, repo: Path) -> tuple[dict[str, str], list[StatusEntry]]:
    """`git status --porcelain=v2 -z --branch` : en-têtes `branch.*` et entrées, triées."""
    out = git.internal(
        "status",
        "--porcelain=v2",
        "-z",
        "--branch",
        "--untracked-files=all",
        "--ignored=no",
        cwd=repo,
    )
    headers: dict[str, str] = {}
    entries: list[StatusEntry] = []
    tokens = iter(_split_z(out))
    for token in tokens:
        if not token:
            continue
        if token.startswith("# "):
            key, _, value = token[2:].partition(" ")
            headers[key] = value
        elif token.startswith("1 "):
            fields = token.split(" ", 8)
            xy = fields[1]
            entries.append(
                StatusEntry(
                    path=fields[8], kind="changed", index_status=xy[0], worktree_status=xy[1]
                )
            )
        elif token.startswith("2 "):
            fields = token.split(" ", 9)
            xy = fields[1]
            entries.append(
                StatusEntry(
                    path=fields[9],
                    kind="renamed",
                    index_status=xy[0],
                    worktree_status=xy[1],
                    orig_path=next(tokens, ""),
                )
            )
        elif token.startswith("u "):
            fields = token.split(" ", 10)
            xy = fields[1]
            entries.append(
                StatusEntry(
                    path=fields[10], kind="unmerged", index_status=xy[0], worktree_status=xy[1]
                )
            )
        elif token.startswith("? "):
            entries.append(
                StatusEntry(path=token[2:], kind="untracked", index_status="?", worktree_status="?")
            )
    return headers, sorted(entries, key=lambda e: e.path)


def read_index(git: Git, repo: Path) -> list[IndexEntry]:
    """Entrées de l'index (`ls-files -s -z`), triées par chemin puis étage."""
    out = git.internal("ls-files", "-s", "-z", cwd=repo)
    entries = []
    for item in _split_z(out):
        if not item:
            continue
        meta, _, path = item.partition("\t")
        mode, oid, stage = meta.split(" ")
        entries.append(IndexEntry(path=path, mode=mode, oid=oid, stage=int(stage)))
    return sorted(entries, key=lambda e: (e.path, e.stage))


def read_worktree(git: Git, repo: Path, status: Iterable[StatusEntry]) -> list[str]:
    """Fichiers présents dans l'arbre de travail, suivis ou non ignorés (posix, triés)."""
    out = git.internal("ls-files", "-z", "--cached", "--others", "--exclude-standard", cwd=repo)
    deleted = {e.path for e in status if e.worktree_status == "D"}
    return sorted({p for p in _split_z(out) if p and p not in deleted})


def read_stash(git: Git, repo: Path) -> list[StashEntry]:
    """Entrées du stash, de `stash@{0}` à la plus ancienne."""
    out = git.internal("stash", "list", "--format=%H%x1f%gs%x00", cwd=repo)
    entries = []
    records = (record.lstrip("\n") for record in out.split("\0"))
    for position, record in enumerate(record for record in records if record):
        sha, _, message = record.partition("\x1f")
        entries.append(StashEntry(index=position, sha=sha, message=message))
    return entries


def read_reflog(git: Git, repo: Path, names: Iterable[str]) -> list[str]:
    """Commits cités par les reflogs de `names` (une ref sans reflog est ignorée).

    Un seul `log -g` pour toutes les refs ; s'il échoue (un git qui refuserait une ref sans
    reflog), une commande par ref.
    """
    names = list(names)
    result = git.run("log", "-g", "--format=%H", *names, "--", cwd=repo)
    outputs = [result.stdout] if result.ok else []
    if not result.ok:
        for name in names:
            single = git.run("log", "-g", "--format=%H", name, "--", cwd=repo)
            if single.ok:
                outputs.append(single.stdout)
    return list(dict.fromkeys(line for out in outputs for line in out.split("\n") if line))


def read_commits(git: Git, repo: Path, *, empty: bool = False) -> dict[str, dict[str, str]]:
    """Commits accessibles depuis les refs, HEAD et les reflogs (`rev-list --all --reflog`).

    `empty` : le dépôt n'a ni ref ni commit sur HEAD ; un échec de `rev-list` y veut dire
    « aucun commit » (toute autre erreur remonte en `GitError`).
    """
    argv = ("rev-list", "--all", "--reflog", "--no-commit-header", f"--format={COMMIT_FORMAT}")
    if empty:
        result = git.run(*argv, cwd=repo)
        output = result.stdout if result.ok else ""
    else:
        output = git.internal(*argv, cwd=repo)
    commits: dict[str, dict[str, str]] = {}
    keys = ("sha", "parents", "tree", "an", "ae", "ad", "cn", "ce", "cd", "ct", "subject", "body")
    for match in _RECORD.finditer(output):
        values = dict(zip(keys, match.group(1).split("\x1f", len(keys) - 1), strict=True))
        commits[values["sha"]] = values
    return commits


def _walk(starts: Iterable[str], parents: Mapping[str, list[str]], skip: set[str]) -> set[str]:
    seen: set[str] = set()
    stack = [s for s in starts if s in parents and s not in skip]
    while stack:
        sha = stack.pop()
        if sha in seen:
            continue
        seen.add(sha)
        stack += [p for p in parents[sha] if p in parents and p not in skip and p not in seen]
    return seen


def in_progress(repo: Path) -> InProgress:
    """Opération en cours, d'après les marqueurs de `.git/` (lecture seule)."""
    git_dir = repo / ".git"
    if (git_dir / "rebase-merge").exists() or (git_dir / "rebase-apply").exists():
        return "rebase"
    for marker, name in (
        ("MERGE_HEAD", "merge"),
        ("CHERRY_PICK_HEAD", "cherry_pick"),
        ("REVERT_HEAD", "revert"),
    ):
        if (git_dir / marker).exists():
            return name  # type: ignore[return-value]
    return ""


def read_repo_state(git: Git, repo: Path, actors: Mapping[str, Actor] | None = None) -> RepoState:
    """Construit le `RepoState` du dépôt `repo`.

    `actors` associe une adresse e-mail d'auteur à un rôle ; toute autre adresse est celle
    de l'apprenant.
    """
    actors = actors or {}
    refs = read_refs(git, repo)
    headers, status = read_status(git, repo)
    oid = headers.get("branch.oid", "(initial)")
    head_name = headers.get("branch.head", "")
    detached = head_name == "(detached)"
    head_ref = "" if detached else f"refs/heads/{head_name}"
    upstream = next((r.upstream for r in refs if r.name == head_ref), "")
    ahead = behind = None
    if "branch.ab" in headers:
        plus, minus = headers["branch.ab"].split(" ")
        ahead, behind = int(plus.lstrip("+")), int(minus.lstrip("-"))
    head = Head(
        detached=detached,
        ref=head_ref,
        commit="" if oid == "(initial)" else oid,
        upstream=upstream,
        ahead=ahead,
        behind=behind,
    )

    raw = read_commits(git, repo, empty=not refs and not head.commit)
    parents = {sha: values["parents"].split() for sha, values in raw.items()}
    tips = [r.commit for r in refs if r.commit and r.kind != "stash"]
    if head.commit:
        tips.append(head.commit)
    reachable = _walk(tips, parents, set())
    logged = read_reflog(
        git, repo, ["HEAD", *(r.name for r in refs if r.kind in _REFLOG_KINDS and not r.symref)]
    )
    lost = _walk(logged, parents, reachable)

    commits = []
    for sha in sorted(reachable | lost):
        values = raw[sha]
        commits.append(
            Commit(
                sha=sha,
                parents=parents[sha],
                tree=values["tree"],
                author_name=values["an"],
                author_email=values["ae"],
                author_date=values["ad"],
                committer_name=values["cn"],
                committer_email=values["ce"],
                committer_date=values["cd"],
                committer_ts=int(values["ct"]),
                subject=values["subject"],
                message=values["body"].rstrip("\n"),
                actor=actors.get(values["ae"].lower(), "learner"),
                lost=sha in lost,
            )
        )
    return RepoState(
        head=head,
        commits=commits,
        refs=refs,
        index=read_index(git, repo),
        status=status,
        worktree=read_worktree(git, repo, status),
        stash=read_stash(git, repo),
        in_progress=in_progress(repo),
    )
