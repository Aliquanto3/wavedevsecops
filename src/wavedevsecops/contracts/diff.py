"""Diff projeté par le serveur pour la vue Code (AD-2, UX-DR17).

Le front met en forme (marqueurs « + » et « − », couleurs) sans rien calculer : numéros de
ligne, `element_id`, noms accessibles et phrases viennent d'ici.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict

DiffLineKind = Literal["added", "removed", "context"]
DiffFileStatus = Literal["modified", "new", "deleted", "renamed", "binary"]


class _Model(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class DiffLine(_Model):
    """Une ligne de diff (`diff-view`) : focalisable, liable, désignable."""

    element_id: str
    """`diffline:<sha40|worktree>:<chemin>:<old|new>:<ligne>` (côté `old` pour une suppression)."""
    kind: DiffLineKind
    old_no: int | None = None
    new_no: int | None = None
    text: str
    a11y_name_text: str
    """« Ligne ajoutée 12 : texte » : le marqueur « + » / « − » n'est pas la seule information."""
    conflict: bool = False
    """Marqueur de conflit (`<<<<<<<`, `=======`, `>>>>>>>`), à rendre visible."""
    links: list[str] = []
    """`element_id` liés (story 2.10) : le commit du diff et le fichier, dans ses trois zones."""


class DiffHunk(_Model):
    header_text: str
    """`@@ -1,3 +1,4 @@` et le contexte de fonction éventuel."""
    lines: list[DiffLine] = []


class DiffFile(_Model):
    """`diff-file-header` et ses blocs."""

    element_id: str
    """`path:<head|worktree>:<chemin>` : le fichier du diff, désignable comme fichier."""
    path: str
    old_path: str = ""
    """Ancien chemin, pour un renommage."""
    status: DiffFileStatus
    added: int = 0
    removed: int = 0
    summary_text: str
    """« modifié · +3 −1 », « nouveau fichier · +3 −0 »…"""
    a11y_name_text: str
    explain_ref: str = ""
    """Clé de `content/explanations.yaml` (story 2.10)."""
    links: list[str] = []
    """`element_id` liés : le commit du diff et le fichier dans les autres zones."""
    hunks: list[DiffHunk] = []


class DiffView(_Model):
    """Diff d'un commit ou de l'arbre de travail."""

    target: str
    """`worktree` ou le SHA complet du commit."""
    target_text: str
    """« Arbre de travail (depuis HEAD) » ou « Commit a1b2c3d »."""
    files: list[DiffFile] = []
    empty_text: str = ""
    """Phrase affichée quand il n'y a aucun changement."""
    truncated: bool = False
    truncated_text: str = ""
