"""Placement déterministe du graphe (AD-2) sur des graphes synthétiques."""

from __future__ import annotations

import hashlib
import random
import time
from collections.abc import Sequence

from wavedevsecops.contracts import Commit
from wavedevsecops.projections import Layout, place


def sha(name: str) -> str:
    return hashlib.sha1(name.encode()).hexdigest()


def commit(name: str, parents: Sequence[str] = (), ts: int = 0) -> Commit:
    return Commit(
        sha=sha(name),
        parents=[sha(p) for p in parents],
        tree="0" * 40,
        author_name="A",
        author_email="a@exemple.test",
        author_date="2026-01-01T00:00:00+00:00",
        committer_name="A",
        committer_email="a@exemple.test",
        committer_date="2026-01-01T00:00:00+00:00",
        committer_ts=ts,
        subject=name,
        message=name,
    )


def check_invariants(layout: Layout, commits: Sequence[Commit]) -> None:
    """Une case par nœud ; la colonne d'une arête ne croise ni nœud ni autre arête."""
    nodes = {(c.column, c.row) for c in layout.cells.values()}
    assert len(nodes) == len(layout.cells) == len(commits)
    used: set[tuple[int, int]] = set()
    for route in layout.routes:
        child, parent = layout.cells[route.child], layout.cells[route.parent]
        assert child.row > parent.row
        if route.first_parent:
            assert route.column == child.column
        segment = {(route.column, row) for row in range(parent.row + 1, child.row)}
        assert not segment & nodes, route
        assert not segment & used, route
        used |= segment
    by_sha = {c.sha: c for c in commits}
    for name, cell in layout.cells.items():
        parents = by_sha[name].parents
        rows = [layout.cells[p].row for p in parents if p in layout.cells]
        expected = 1 + max(rows, default=-1)
        assert cell.row == expected


def grow(rng: random.Random, count: int) -> list[Commit]:
    """Un historique plausible : branches, fusions, plusieurs racines, dates croissantes."""
    commits = [commit("c0", (), 1000)]
    tips = ["c0"]
    for i in range(1, count):
        name = f"c{i}"
        roll = rng.random()
        if roll < 0.02:
            parents: tuple[str, ...] = ()
        elif roll < 0.2 and len(tips) > 1:
            first, second = rng.sample(tips, 2)
            parents = (first, second)
            tips.remove(second)
        elif roll < 0.35:
            parents = (f"c{rng.randrange(i)}",)
        else:
            parents = (rng.choice(tips),)
        if parents and parents[0] in tips:
            tips.remove(parents[0])
        tips.append(name)
        commits.append(commit(name, parents, 1000 + 60 * i))
    return commits


def test_meme_entree_meme_sortie_quel_que_soit_l_ordre() -> None:
    commits = grow(random.Random(7), 120)
    reference = place(commits)
    for seed in range(5):
        shuffled = list(commits)
        random.Random(seed).shuffle(shuffled)
        assert place(shuffled).cells == reference.cells
    check_invariants(reference, commits)


def test_un_commit_ajoute_ne_deplace_aucun_autre() -> None:
    commits = grow(random.Random(11), 150)
    previous = place(commits[:1]).cells
    for size in range(2, len(commits) + 1):
        layout = place(commits[:size])
        check_invariants(layout, commits[:size])
        for name, cell in previous.items():
            assert layout.cells[name] == cell, (size, name)
        previous = layout.cells


def test_ligne_droite_puis_branche_et_fusion() -> None:
    commits = [
        commit("a", (), 1),
        commit("b", ("a",), 2),
        commit("f1", ("b",), 3),
        commit("c", ("b",), 4),
        commit("f2", ("f1",), 5),
        commit("m", ("c", "f2"), 6),
    ]
    cells = place(commits).cells
    assert [
        (cells[sha(n)].column, cells[sha(n)].row) for n in ("a", "b", "f1", "c", "f2", "m")
    ] == [
        (0, 0),
        (0, 1),
        (0, 2),
        (1, 2),
        (0, 3),
        (1, 4),
    ]
    check_invariants(place(commits), commits)


def test_racines_multiples_et_parent_absent() -> None:
    commits = [commit("a", (), 1), commit("z", (), 2), commit("b", ("a", "inconnu"), 3)]
    layout = place(commits)
    check_invariants(layout, commits)
    assert layout.cells[sha("a")].row == layout.cells[sha("z")].row == 0
    assert layout.cells[sha("a")].column != layout.cells[sha("z")].column


def test_graphe_vide() -> None:
    layout = place([])
    assert layout.cells == {} and layout.columns == 0 and layout.rows == 0


def test_performance_quelques_centaines_de_commits() -> None:
    commits = grow(random.Random(3), 800)
    started = time.perf_counter()
    layout = place(commits)
    assert time.perf_counter() - started < 2.0
    check_invariants(layout, commits)
