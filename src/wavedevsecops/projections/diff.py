"""Diff d'un commit ou de l'arbre de travail, projeté pour la vue Code (AD-2, UX-DR17).

Le serveur lit le diff par git (contexte interne, sortie stable `LC_ALL=C`) et le découpe en
fichiers, blocs et lignes qui portent chacun leur `element_id`, leur numéro et leur nom
accessible. Le front ne fait que mettre en forme.
"""

from __future__ import annotations

import re
from pathlib import Path

from wavedevsecops.contracts import AppError, element_id
from wavedevsecops.contracts.diff import DiffFile, DiffHunk, DiffLine, DiffView
from wavedevsecops.gitio import Git

WORKTREE = "worktree"
EMPTY_TREE = "4b825dc642cb6eb9a060e54bf8d69288fbee4904"
"""Arbre vide de git : base du diff d'un premier commit ou d'un dépôt sans commit."""
MAX_LINES = 3000
"""Lignes de diff au plus projetées : au-delà, la projection est coupée et le dit."""
MAX_TEXT = 2000
MAX_UNTRACKED = 200
"""Fichiers non suivis au plus ajoutés au diff de l'arbre de travail (un appel git chacun)."""
_TARGET = re.compile(r"^[0-9a-f]{7,40}$")
_HUNK = re.compile(r"^@@ -(\d+)(?:,\d+)? \+(\d+)(?:,\d+)? @@")
_CONFLICT = re.compile(r"^(<<<<<<<|>>>>>>>)( |$)|^=======$")
_QUIET = {"GIT_OPTIONAL_LOCKS": "0"}
"""Une lecture ne rafraîchit pas l'index : elle ne prend pas son verrou pendant une commande."""


class DiffTargetError(AppError):
    """Cible de diff inconnue (SHA absent du dépôt, forme invalide)."""

    def __init__(self, target: str) -> None:
        super().__init__(
            f"Le commit « {target[:40]} » est introuvable dans ce dépôt.",
            "Sélectionnez un commit du graphe ou l'arbre de travail.",
        )


def _plural(count: int, singular: str, plural: str) -> str:
    return f"{count} {singular if count in (0, 1) else plural}"


def _provisional_path(rest: str) -> str:
    """Chemin d'un en-tête `a/<p> b/<p>` (hors renommage) ; garde le segment après ` b/`."""
    if len(rest) >= 5 and (len(rest) - 5) % 2 == 0:
        size = (len(rest) - 5) // 2
        if rest[2 : 2 + size] == rest[5 + size :]:
            return rest[2 : 2 + size]
    return rest.rsplit(" b/", 1)[-1]


def _unquote(path: str) -> str:
    return path[1:-1] if len(path) >= 2 and path[0] == path[-1] == '"' else path


class _File:
    def __init__(self, path: str) -> None:
        self.path = path
        self.old_path = ""
        self.status = "modified"
        self.hunks: list[tuple[str, list[DiffLine]]] = []
        self.added = 0
        self.removed = 0


def _summary(file: _File) -> str:
    if file.status == "binary":
        return "fichier binaire"
    label = {
        "new": "nouveau fichier",
        "deleted": "fichier supprimé",
        "renamed": f"renommé depuis {file.old_path}",
        "modified": "modifié",
    }[file.status]
    return f"{label} · +{file.added} −{file.removed}"


def _a11y_file(file: _File) -> str:
    if file.status == "binary":
        return f"Fichier {file.path}, binaire"
    status = {
        "new": "nouveau fichier",
        "deleted": "supprimé",
        "renamed": f"renommé depuis {file.old_path}",
        "modified": "modifié",
    }[file.status]
    return (
        f"Fichier {file.path}, {status}, "
        f"{_plural(file.added, 'ligne ajoutée', 'lignes ajoutées')}, "
        f"{_plural(file.removed, 'ligne supprimée', 'lignes supprimées')}"
    )


def _line(zone: str, file: _File, kind: str, old_no: int | None, new_no: int | None, raw: str):
    text = raw[:MAX_TEXT]
    side, number = ("old", old_no) if kind == "removed" else ("new", new_no)
    word = {"added": "ajoutée", "removed": "supprimée", "context": "de contexte"}[kind]
    shown = text if text.strip() else "(ligne vide)"
    return DiffLine(
        element_id=element_id("diffline", zone, file.path, side, str(number)),
        kind=kind,
        old_no=old_no,
        new_no=new_no,
        text=text,
        a11y_name_text=f"Ligne {word} {number} : {shown}",
        conflict=bool(_CONFLICT.match(text)),
    )


def parse_diff(text: str, target: str) -> DiffView:
    """Découpe un diff unifié de git en `DiffView` (`target` : `worktree` ou SHA complet)."""
    zone = target
    path_zone = "worktree" if target == WORKTREE else "head"
    files: list[_File] = []
    current: _File | None = None
    lines: list[DiffLine] | None = None
    old_no = new_no = 0
    total = 0
    truncated = False
    for raw in text.split("\n"):
        if raw.startswith("diff --git "):
            current = _File(_unquote(_provisional_path(raw[len("diff --git ") :])))
            files.append(current)
            lines = None
            continue
        if current is None:
            continue
        if lines is None or raw.startswith("@@"):
            hunk = _HUNK.match(raw)
            if hunk:
                old_no, new_no = int(hunk.group(1)), int(hunk.group(2))
                lines = []
                current.hunks.append((raw, lines))
                continue
            if lines is None:
                if raw.startswith("new file mode"):
                    current.status = "new"
                elif raw.startswith("deleted file mode"):
                    current.status = "deleted"
                elif raw.startswith("rename from "):
                    current.status = "renamed"
                    current.old_path = _unquote(raw[len("rename from ") :])
                elif raw.startswith("rename to "):
                    current.path = _unquote(raw[len("rename to ") :])
                elif raw.startswith(("Binary files ", "GIT binary patch")):
                    current.status = "binary"
                continue
        if total >= MAX_LINES:
            truncated = True
            break
        marker = raw[:1]
        if marker == "+":
            current.added += 1
            lines.append(_line(zone, current, "added", None, new_no, raw[1:]))
            new_no += 1
        elif marker == "-":
            current.removed += 1
            lines.append(_line(zone, current, "removed", old_no, None, raw[1:]))
            old_no += 1
        elif marker == " ":
            lines.append(_line(zone, current, "context", old_no, new_no, raw[1:]))
            old_no += 1
            new_no += 1
        else:
            continue  # « \ No newline at end of file » ou ligne vide finale
        total += 1
    return DiffView(
        target=target,
        target_text="",
        files=[
            DiffFile(
                element_id=element_id("path", path_zone, f.path),
                path=f.path,
                old_path=f.old_path,
                status=f.status,
                added=f.added,
                removed=f.removed,
                summary_text=_summary(f),
                a11y_name_text=_a11y_file(f),
                hunks=[DiffHunk(header_text=head, lines=body) for head, body in f.hunks],
            )
            for f in files
        ],
        truncated=truncated,
        truncated_text=(
            f"Le diff est coupé après {MAX_LINES} lignes : lisez le reste avec « git diff »."
            if truncated
            else ""
        ),
    )


def _has_head(git: Git, repo: Path) -> bool:
    return git.run("rev-parse", "--verify", "-q", "HEAD", cwd=repo, extra_env=_QUIET).ok


def _untracked_diff(git: Git, repo: Path) -> str:
    """Diff des fichiers non suivis (hors `.gitignore`), présentés comme de nouveaux fichiers.

    `git diff --no-index` contre `/dev/null` : rien n'entre dans l'index (une lecture ne l'écrit
    pas). Au plus `MAX_UNTRACKED` fichiers, et arrêt dès que le diff dépasse `MAX_LINES`.
    """
    listed = git.internal(
        "ls-files", "--others", "--exclude-standard", "-z", cwd=repo, extra_env=_QUIET
    )
    parts: list[str] = []
    size = 0
    for path in [p for p in listed.split("\0") if p][:MAX_UNTRACKED]:
        found = git.run(
            "diff",
            "--no-index",
            "--no-ext-diff",
            "--no-textconv",
            "--no-color",
            "--",
            "/dev/null",
            path,
            cwd=repo,
            extra_env=_QUIET,
        )
        # `--no-index` sort en 1 quand les deux côtés diffèrent : c'est le cas attendu.
        if found.returncode not in (0, 1) or found.timed_out or found.error:
            continue
        parts.append(found.stdout)
        size += found.stdout.count("\n")
        if size > MAX_LINES:
            break
    return "\n".join(parts)


def read_diff(git: Git, repo: Path, target: str) -> DiffView:
    """Diff de l'arbre de travail depuis HEAD (`worktree`) ou d'un commit contre son premier parent.

    L'arbre de travail montre aussi les fichiers non suivis (hors `.gitignore`), comme de
    nouveaux fichiers : un fichier créé dans la vue Code y figure dès son enregistrement.
    """
    flags = ("--no-ext-diff", "--no-textconv", "--no-color", "-M")
    if target == WORKTREE:
        base = "HEAD" if _has_head(git, repo) else EMPTY_TREE
        out = git.internal("diff", *flags, base, cwd=repo, extra_env=_QUIET)
        view = parse_diff(f"{out}\n{_untracked_diff(git, repo)}", WORKTREE)
        text = "Arbre de travail (depuis HEAD)"
        empty = "Aucun changement : l'arbre de travail est identique à HEAD."
        return view.model_copy(
            update={"target_text": text, "empty_text": "" if view.files else empty}
        )
    if not _TARGET.match(target):
        raise DiffTargetError(target)
    found = git.run("rev-list", "--parents", "-n", "1", target, cwd=repo, extra_env=_QUIET)
    parts = found.stdout.split()
    if not found.ok or not parts:
        raise DiffTargetError(target)
    sha = parts[0]
    parent = parts[1] if len(parts) > 1 else EMPTY_TREE
    out = git.internal("diff", *flags, parent, sha, cwd=repo, extra_env=_QUIET)
    view = parse_diff(out, sha)
    return view.model_copy(
        update={
            "target_text": f"Commit {sha[:7]}",
            "empty_text": "" if view.files else "Ce commit ne change aucun fichier.",
        }
    )
