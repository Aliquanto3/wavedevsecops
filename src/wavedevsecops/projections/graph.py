"""Placement déterministe du graphe des commits (AD-2).

Rang : nombre de générations depuis la racine (`1 + max(rang des parents)`, 0 pour une
racine). Il ne dépend que des ancêtres d'un commit, que son SHA fixe : il ne change jamais.

Colonne : les commits sont placés un par un, dans un ordre topologique où, parmi les
commits prêts, passe d'abord le plus ancien (date du committer, puis rang, puis SHA). Chaque
commit prend la colonne de son premier parent si elle est libre jusqu'à son rang, sinon la
plus petite colonne libre. Le choix ne regarde que les commits déjà placés, jamais les refs :
un commit créé après les autres (commit, merge, rebase, cherry-pick) est placé en dernier et
ne déplace personne. Une branche créée, supprimée ou déplacée, un HEAD détaché, un tag ou une
ref distante ne bougent aucun commit ; un commit perdu reste à sa place.

Garanties testées : une case (colonne, rang) porte au plus un nœud ; entre les deux rangs
d'une arête, sa colonne ne croise ni nœud ni autre arête.
"""

from __future__ import annotations

import heapq
from collections.abc import Iterable
from dataclasses import dataclass

from wavedevsecops.contracts import Commit


@dataclass(frozen=True)
class Cell:
    column: int
    row: int


@dataclass(frozen=True)
class Route:
    """Arête d'un enfant vers un parent ; `column` porte sa partie verticale."""

    child: str
    parent: str
    column: int
    first_parent: bool


@dataclass(frozen=True)
class Layout:
    cells: dict[str, Cell]
    routes: list[Route]
    order: list[str]
    """Ordre de placement des commits."""

    @property
    def columns(self) -> int:
        return 1 + max((c.column for c in self.cells.values()), default=-1)

    @property
    def rows(self) -> int:
        return 1 + max((c.row for c in self.cells.values()), default=-1)


class _Grid:
    """Cases occupées, par colonne : nœuds et parties verticales des arêtes."""

    def __init__(self) -> None:
        self._taken: dict[int, set[int]] = {}

    def free(self, column: int, low: int, high: int) -> bool:
        taken = self._taken.get(column)
        return not taken or all(row not in taken for row in range(low, high + 1))

    def take(self, column: int, low: int, high: int) -> None:
        self._taken.setdefault(column, set()).update(range(low, high + 1))

    def first_free(self, low: int, high: int) -> int:
        column = 0
        while not self.free(column, low, high):
            column += 1
        return column


def place(commits: Iterable[Commit]) -> Layout:
    """Place chaque commit ; un parent absent de `commits` (dépôt superficiel) est ignoré."""
    by_sha = {c.sha: c for c in commits}
    parents = {sha: [p for p in c.parents if p in by_sha] for sha, c in by_sha.items()}
    children: dict[str, list[str]] = {sha: [] for sha in by_sha}
    waiting = {sha: len(set(ps)) for sha, ps in parents.items()}
    for sha, ps in parents.items():
        for parent in set(ps):
            children[parent].append(sha)

    cells: dict[str, Cell] = {}
    routes: list[Route] = []
    order: list[str] = []
    grid = _Grid()
    ready: list[tuple[int, int, str]] = []

    def push(sha: str) -> None:
        row = 1 + max((cells[p].row for p in parents[sha]), default=-1)
        heapq.heappush(ready, (by_sha[sha].committer_ts, row, sha))

    for sha in sorted(by_sha):
        if waiting[sha] == 0:
            push(sha)
    while ready:
        _, row, sha = heapq.heappop(ready)
        own = parents[sha]
        if own:
            first = cells[own[0]]
            if grid.free(first.column, first.row + 1, row):
                column = first.column
            else:
                column = grid.first_free(first.row + 1, row)
            grid.take(column, first.row + 1, row)
            routes.append(Route(sha, own[0], column, True))
        else:
            column = grid.first_free(row, row)
            grid.take(column, row, row)
        cells[sha] = Cell(column, row)
        for parent in own[1:]:
            low = cells[parent].row + 1
            if grid.free(cells[parent].column, low, row - 1):
                lane = cells[parent].column
            else:
                lane = grid.first_free(low, row - 1)
            grid.take(lane, low, row - 1)
            routes.append(Route(sha, parent, lane, False))
        order.append(sha)
        for child in sorted(children[sha]):
            waiting[child] -= 1
            if waiting[child] == 0:
                push(child)
    return Layout(cells, routes, order)
