"""Placement déterministe du graphe des commits (AD-2).

Rang : nombre de générations depuis la racine (`1 + max(rang des parents)`, 0 pour une
racine). Il ne dépend que des ancêtres d'un commit, que son SHA fixe : il ne change jamais.

Colonne : les commits sont placés un par un, dans un ordre topologique où, parmi les
commits prêts, passe d'abord le plus ancien (date du committer, puis rang, puis SHA). Chaque
commit prend la colonne de son premier parent si elle est libre jusqu'à son rang, sinon la
plus petite colonne libre. Le choix ne regarde que les commits déjà placés, jamais les refs :
une branche créée, supprimée ou déplacée, un HEAD détaché, un tag ou une ref distante ne
bougent aucun commit ; un commit perdu reste à sa place.

Mémoire : la date d'un commit peut mentir (commit du collègue daté du setup, horloge
reculée). Pour qu'un commit ajouté ne déplace jamais les autres, `place` reçoit le placement
précédent (`previous`) : les commits déjà placés gardent leur case et leurs arêtes, seuls les
nouveaux sont placés, autour d'eux. Le placement est repris de zéro seulement quand le passé
change sous un commit déjà placé (rang différent, parent nouveau : dépôt approfondi) ; sans
placement précédent (réouverture de l'espace), on retombe sur l'ordre par date.

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


def _kept(
    previous: Layout | None,
    by_sha: dict[str, Commit],
    parents: dict[str, list[str]],
    rows: dict[str, int],
) -> tuple[dict[str, Cell], list[Route]]:
    """Cases et arêtes du placement précédent encore valides ; rien si le passé a changé."""
    if previous is None:
        return {}, []
    cells = {sha: cell for sha, cell in previous.cells.items() if sha in by_sha}
    for sha, cell in cells.items():
        if rows[sha] != cell.row or any(p not in cells for p in parents[sha]):
            return {}, []
    routes = [r for r in previous.routes if r.child in cells and r.parent in cells]
    wanted = {(sha, p) for sha in cells for p in parents[sha]}
    if {(r.child, r.parent) for r in routes} != wanted:
        return {}, []
    return cells, routes


def place(commits: Iterable[Commit], previous: Layout | None = None) -> Layout:
    """Place chaque commit ; un parent absent de `commits` (dépôt superficiel) est ignoré.

    `previous` : placement précédent ; ses commits encore présents gardent leur case.
    """
    by_sha = {c.sha: c for c in commits}
    parents = {sha: [p for p in c.parents if p in by_sha] for sha, c in by_sha.items()}
    children: dict[str, list[str]] = {sha: [] for sha in by_sha}
    for sha, ps in parents.items():
        for parent in set(ps):
            children[parent].append(sha)
    rows: dict[str, int] = {}
    for sha in _topological(parents, children):
        rows[sha] = 1 + max((rows[p] for p in parents[sha]), default=-1)

    cells, routes = _kept(previous, by_sha, parents, rows)
    grid = _Grid()
    for cell in cells.values():
        grid.take(cell.column, cell.row, cell.row)
    for route in routes:
        grid.take(route.column, cells[route.parent].row + 1, cells[route.child].row - 1)
    order = sorted(cells, key=lambda s: (cells[s].row, cells[s].column))
    waiting = {sha: len({p for p in ps if p not in cells}) for sha, ps in parents.items()}
    ready: list[tuple[int, int, str]] = []

    def push(sha: str) -> None:
        heapq.heappush(ready, (by_sha[sha].committer_ts, rows[sha], sha))

    for sha in sorted(by_sha):
        if sha not in cells and waiting[sha] == 0:
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


def _topological(parents: dict[str, list[str]], children: dict[str, list[str]]) -> list[str]:
    """Les commits, chaque parent avant ses enfants."""
    waiting = {sha: len(set(ps)) for sha, ps in parents.items()}
    stack = sorted(sha for sha, count in waiting.items() if count == 0)
    out: list[str] = []
    while stack:
        sha = stack.pop()
        out.append(sha)
        for child in children[sha]:
            waiting[child] -= 1
            if waiting[child] == 0:
                stack.append(child)
    return out
