"""Passages liables d'une sortie, résolus contre le `RepoState` (AD-2).

Un mot de la sortie devient liable s'il nomme un élément qui existe dans le bac à sable :

- un nom de ref (`main`, `origin/main`, `v1.0`, `refs/heads/main`, `HEAD`), résolu dans
  l'ordre de git (`refs/<nom>`, tag, branche, ref distante) ;
- un chemin de l'arbre de travail ou de l'index, y compris `a/<chemin>` et `b/<chemin>`
  d'un diff et `fichier:ligne` (seul le chemin est lié) ;
- un préfixe hexadécimal d'au moins 7 caractères qui désigne un seul commit du graphe.

Positions en unités UTF-16 (celles de `String.prototype.slice` côté front).
"""

from __future__ import annotations

import bisect
import re
from typing import Any

from wavedevsecops.contracts import RepoState, element_id
from wavedevsecops.projections.views import HEAD_ID, ref_element

_TOKEN = re.compile(r"[^\s\"'`()\[\]{}<>,;|=]+")
_TRAILING = ".:!?…"
_HEX = re.compile(r"^[0-9a-f]{7,40}$")
_FILE_LINE = re.compile(r"^(?P<path>.+?):\d+(?::\d+)?:?$")
_MIN_SHA = 7


def _utf16(text: str, index: int) -> int:
    prefix = text[:index]
    return index if prefix.isascii() else len(prefix.encode("utf-16-le")) // 2


class Linker:
    """Trouve les passages liables d'un texte pour un `RepoState` donné."""

    def __init__(self, state: RepoState) -> None:
        self._shas = sorted(c.sha for c in state.commits)
        names: dict[str, str] = {"HEAD": HEAD_ID}
        # Ordre inverse de la priorité de git : la dernière écriture l'emporte.
        for kind in ("remote", "branch", "tag"):
            for ref in state.refs:
                if ref.kind == kind and ref.commit:
                    names[ref.short_name] = ref_element(ref)
        for ref in state.refs:
            if ref.kind != "stash" and (ref.commit or ref.symref):
                names[ref.name] = ref_element(ref)
                names[ref.name.removeprefix("refs/")] = ref_element(ref)
        self._names = names
        worktree = set(state.worktree)
        index = {e.path for e in state.index}
        self._paths = {
            **{p: element_id("path", "index", p) for p in sorted(index - worktree)},
            **{p: element_id("path", "worktree", p) for p in sorted(worktree)},
        }

    def _commit(self, token: str) -> str:
        if not _HEX.match(token):
            return ""
        at = bisect.bisect_left(self._shas, token)
        found = self._shas[at : at + 2]
        if (
            found
            and found[0].startswith(token)
            and not (len(found) > 1 and found[1].startswith(token))
        ):
            return element_id("commit", found[0])
        return ""

    def _resolve(self, token: str) -> tuple[str, int]:
        """`(element_id, longueur liée)` d'un mot, ou `("", 0)`."""
        if token in self._names:
            return self._names[token], len(token)
        if token in self._paths:
            return self._paths[token], len(token)
        if token[:2] in {"a/", "b/"} and token[2:] in self._paths:
            # Lien sur le chemin seul : le préfixe de diff reste hors du passage.
            return self._paths[token[2:]], -len(token[2:])
        match = _FILE_LINE.match(token)
        if match and match["path"] in self._paths:
            return self._paths[match["path"]], len(match["path"])
        if len(token) >= _MIN_SHA:
            found = self._commit(token)
            if found:
                return found, len(token)
        return "", 0

    def __call__(self, text: str) -> list[dict[str, Any]]:
        spans: list[dict[str, Any]] = []
        for match in _TOKEN.finditer(text):
            token = match.group(0).rstrip(_TRAILING)
            if not token:
                continue
            target, length = self._resolve(token)
            if not target:
                continue
            start = match.start()
            if length < 0:  # a/<chemin> ou b/<chemin>
                start, length = start + 2, -length
            end = start + length
            spans.append(
                {
                    "start": _utf16(text, start),
                    "end": _utf16(text, end),
                    "text": text[start:end],
                    "element_id": target,
                }
            )
        return spans
