"""Vues calculées depuis le `RepoState` : graphe annoté, index, invite, annonce (AD-2).

Les textes suivent les gabarits de l'UX (EXPERIENCE.md, accessibilité) :

- nœud : « Commit a1b2c3d, Add config, par l'agent, parent 9f8e7d6, pointé par la branche
  locale feature et HEAD, nouveau » ;
- refs : « branche locale feature », « référence distante origin/main », « tag v0.1.0 » ;
- commit perdu : « perdu · visible par reflog » (dans le nom : « perdu, visible par reflog »).
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence

from wavedevsecops.contracts import (
    Commit,
    GraphEdge,
    GraphNode,
    GraphView,
    PromptView,
    Ref,
    RefLabel,
    RepoState,
    StagingItem,
    StagingView,
    Views,
    element_id,
)
from wavedevsecops.projections.graph import Cell, Layout, Route, place

SHORT = 7
HEAD_ID = element_id("ref", "HEAD")
DETACHED_TEXT = "HEAD détachée"

EXPLAIN_COMMIT = "graph.commit"
EXPLAIN_COMMIT_LOST = "graph.commit_lost"
EXPLAIN_BRANCH = "graph.branch"
EXPLAIN_REMOTE = "graph.remote_ref"
EXPLAIN_TAG = "graph.tag"
EXPLAIN_HEAD = "graph.head"
EXPLAIN_HEAD_DETACHED = "graph.head_detached"
EXPLAIN_REFS = (
    EXPLAIN_COMMIT,
    EXPLAIN_COMMIT_LOST,
    EXPLAIN_BRANCH,
    EXPLAIN_REMOTE,
    EXPLAIN_TAG,
    EXPLAIN_HEAD,
    EXPLAIN_HEAD_DETACHED,
)
"""Clés du catalogue d'explications citées par le graphe."""

_ACTOR_TEXT = {"learner": "par vous", "colleague": "par le collègue", "agent": "par l'agent"}


def short(sha: str) -> str:
    return sha[:SHORT]


def join_fr(items: Sequence[str]) -> str:
    """« a », « a et b », « a, b et c »."""
    if len(items) <= 1:
        return "".join(items)
    return ", ".join(items[:-1]) + " et " + items[-1]


def ref_element(ref: Ref) -> str:
    """`element_id` d'une ref : `tag:<nom>` pour un tag, `ref:<nom complet>` sinon."""
    if ref.kind == "tag":
        return element_id("tag", ref.short_name)
    return element_id("ref", ref.name)


def _labelled(state: RepoState) -> list[Ref]:
    """Refs affichées sur le graphe : branches, refs distantes (hors symboliques) et tags."""
    return [
        r for r in state.refs if r.commit and r.kind in {"branch", "remote", "tag"} and not r.symref
    ]


def _changed_refs(state: RepoState, previous: RepoState | None) -> set[str]:
    if previous is None:
        return set()
    before = {r.name: r.commit for r in previous.refs}
    return {r.name for r in state.refs if before.get(r.name) != r.commit}


def _head_changed(state: RepoState, previous: RepoState | None) -> bool:
    if previous is None:
        return False
    return (state.head.ref, state.head.commit) != (previous.head.ref, previous.head.commit)


def _labels(
    sha: str, state: RepoState, refs: Iterable[Ref], changed: set[str], head_changed: bool
) -> list[RefLabel]:
    """Étiquettes d'un commit : branche courante, HEAD, autres branches, distantes, tags."""
    head = state.head
    here = sorted(
        (r for r in refs if r.commit == sha),
        key=lambda r: (
            {"branch": 0, "remote": 2, "tag": 3}[r.kind] - (r.name == head.ref),
            r.name,
        ),
    )
    labels: list[RefLabel] = []
    node_id = element_id("commit", sha)
    for ref in here:
        if ref.kind == "branch":
            text, a11y, explain = ref.short_name, f"branche locale {ref.short_name}", EXPLAIN_BRANCH
        elif ref.kind == "remote":
            text, a11y = ref.short_name, f"référence distante {ref.short_name}"
            explain = EXPLAIN_REMOTE
        else:
            text, a11y, explain = ref.short_name, f"tag {ref.short_name}", EXPLAIN_TAG
        labels.append(
            RefLabel(
                element_id=ref_element(ref),
                kind="branch" if ref.kind == "branch" else ref.kind,  # type: ignore[arg-type]
                name_text=text,
                a11y_name_text=a11y,
                explain_ref=explain,
                current=ref.name == head.ref,
                new=ref.name in changed,
                links=[node_id],
            )
        )
        if ref.name == head.ref:
            labels.append(_head_label(False, node_id, head_changed))
    if head.detached and head.commit == sha:
        labels.insert(0, _head_label(True, node_id, head_changed))
    return labels


def _head_label(detached: bool, node_id: str, new: bool) -> RefLabel:
    return RefLabel(
        element_id=HEAD_ID,
        kind="head",
        name_text=DETACHED_TEXT if detached else "HEAD",
        a11y_name_text=DETACHED_TEXT if detached else "HEAD",
        explain_ref=EXPLAIN_HEAD_DETACHED if detached else EXPLAIN_HEAD,
        new=new,
        links=[node_id],
    )


def _pointer_text(label: RefLabel) -> str:
    if label.kind == "branch":
        return f"la {label.a11y_name_text}"
    if label.kind == "tag":
        return f"le {label.a11y_name_text}"
    if label.kind == "remote":
        return f"la {label.a11y_name_text}"
    return label.a11y_name_text


def commit_a11y_name(
    commit: Commit, labels: Sequence[RefLabel], *, new: bool, restored: bool = False
) -> str:
    """Nom accessible d'un nœud, selon le gabarit de l'UX."""
    parts = [f"Commit {short(commit.sha)}"]
    if commit.subject:
        parts.append(commit.subject)
    parts.append(_ACTOR_TEXT[commit.actor])
    if not commit.parents:
        parts.append("sans parent")
    elif len(commit.parents) == 1:
        parts.append(f"parent {short(commit.parents[0])}")
    else:
        parts.append("parents " + join_fr([short(p) for p in commit.parents]))
    if labels:
        parts.append("pointé par " + join_fr([_pointer_text(label) for label in labels]))
    if commit.lost:
        parts.append("perdu, visible par reflog")
    if new:
        parts.append("nouveau")
    if restored:
        parts.append("rétabli")
    return ", ".join(parts)


def layout_of(graph: GraphView) -> Layout:
    """Placement porté par un graphe déjà publié (mémoire du placement, AD-2)."""
    shas = {node.element_id: node.sha for node in graph.nodes}
    cells = {node.sha: Cell(node.column, node.row) for node in graph.nodes}
    routes = [
        Route(shas[edge.child], shas[edge.parent], edge.column, edge.kind == "first_parent")
        for edge in graph.edges
        if edge.child in shas and edge.parent in shas
    ]
    return Layout(cells, routes, [])


def build_graph(
    state: RepoState,
    previous: RepoState | None = None,
    restored: Iterable[str] = (),
    previous_graph: GraphView | None = None,
) -> GraphView:
    """Graphe placé et annoté ; `previous` (état d'avant l'opération) fixe les marques `new`.

    `previous_graph` : graphe publié avant l'opération ; ses commits gardent leur case.
    """
    layout = place(state.commits, layout_of(previous_graph) if previous_graph else None)
    commits = {c.sha: c for c in state.commits}
    known = {c.sha for c in previous.commits} if previous is not None else None
    changed = _changed_refs(state, previous)
    head_changed = _head_changed(state, previous)
    refs = _labelled(state)
    restored_set = set(restored)
    nodes: list[GraphNode] = []
    for sha in layout.order:
        commit = commits[sha]
        cell = layout.cells[sha]
        new = known is not None and sha not in known
        labels = _labels(sha, state, refs, changed, head_changed)
        nodes.append(
            GraphNode(
                element_id=element_id("commit", sha),
                sha=sha,
                short_sha=short(sha),
                subject=commit.subject,
                actor=commit.actor,
                column=cell.column,
                row=cell.row,
                parents=[element_id("commit", p) for p in commit.parents],
                refs=labels,
                head=state.head.commit == sha,
                detached_head=state.head.detached and state.head.commit == sha,
                lost=commit.lost,
                new=new,
                restored=sha in restored_set,
                a11y_name_text=commit_a11y_name(
                    commit, labels, new=new, restored=sha in restored_set
                ),
                explain_ref=EXPLAIN_COMMIT_LOST if commit.lost else EXPLAIN_COMMIT,
                links=[label.element_id for label in labels],
            )
        )
    nodes.sort(key=lambda n: (-n.row, n.column))
    edges = [
        GraphEdge(
            child=element_id("commit", route.child),
            parent=element_id("commit", route.parent),
            column=route.column,
            kind="first_parent" if route.first_parent else "merge",
            lost=commits[route.child].lost,
        )
        for route in layout.routes
    ]
    return GraphView(
        nodes=nodes,
        edges=edges,
        columns=layout.columns,
        rows=layout.rows,
        head_text=_head_text(state),
    )


def _branch(state: RepoState) -> str:
    return state.head.ref.removeprefix("refs/heads/")


def _head_text(state: RepoState) -> str:
    head = state.head
    if head.detached:
        return f"{DETACHED_TEXT} sur {short(head.commit)}"
    if not head.commit:
        return f"HEAD sur {_branch(state)}, sans commit"
    return f"HEAD sur {_branch(state)}"


STAGED_TEXT = "Indexé"
UNSTAGED_TEXT = "Modifié, non indexé"
UNTRACKED_TEXT = "Non suivi"
# Lettres d'état de `git status --short`, dites en toutes lettres dans le nom accessible.
_LETTER_TEXT = {
    "M": "modifié",
    "A": "ajouté",
    "D": "supprimé",
    "R": "renommé",
    "C": "copié",
    "T": "type changé",
    "U": "en conflit",
    "?": "non suivi",
}


def _staging_item(group: str, where: str, path: str, letter: str, orig: str = "") -> StagingItem:
    shown = f"{orig} → {path}" if orig else path
    return StagingItem(
        element_id=element_id("path", where, path),
        path=path,
        letter=letter,
        orig_path=orig,
        a11y_name_text=f"{group} : {shown}, {_LETTER_TEXT.get(letter, letter)}",
    )


def build_staging(state: RepoState) -> StagingView:
    """Les trois groupes de `staging-index`, avec la lettre d'état git (UX-DR16)."""
    staged: list[StagingItem] = []
    unstaged: list[StagingItem] = []
    untracked: list[StagingItem] = []
    for entry in state.status:
        if entry.kind == "untracked":
            untracked.append(_staging_item(UNTRACKED_TEXT, "worktree", entry.path, "?"))
            continue
        if entry.kind == "unmerged":
            unstaged.append(_staging_item(UNSTAGED_TEXT, "worktree", entry.path, "U"))
            continue
        if entry.index_status != ".":
            staged.append(
                _staging_item(STAGED_TEXT, "index", entry.path, entry.index_status, entry.orig_path)
            )
        if entry.worktree_status != ".":
            unstaged.append(
                _staging_item(UNSTAGED_TEXT, "worktree", entry.path, entry.worktree_status)
            )
    return StagingView(staged=staged, unstaged=unstaged, untracked=untracked)


def build_prompt(state: RepoState) -> PromptView:
    """`terminal-prompt` : branche courante, ou « HEAD détachée »."""
    if state.head.detached:
        return PromptView(
            text=DETACHED_TEXT,
            detached=True,
            element_id=element_id("commit", state.head.commit) if state.head.commit else "",
        )
    return PromptView(text=_branch(state), element_id=element_id("ref", state.head.ref))


def _count(n: int, singular: str, plural: str) -> str:
    """Accord français : singulier pour 0 et 1."""
    return f"{n} {singular if n <= 1 else plural}"


def announce(state: RepoState, previous: RepoState | None) -> str:
    """Résumé des changements pour la région `role="status"`."""
    head = state.head
    if previous is None:
        reachable = sum(1 for c in state.commits if not c.lost)
        where = (
            f"{DETACHED_TEXT} sur {short(head.commit)}"
            if head.detached
            else f"branche courante {_branch(state)}"
        )
        return f"Dépôt chargé : {_count(reachable, 'commit', 'commits')}, {where}."
    parts: list[str] = []
    before = {c.sha: c for c in previous.commits}
    new_commits = [c for c in state.commits if c.sha not in before and not c.lost]
    # La branche courante qui avance sur un commit créé (commit, merge, rebase) va de soi.
    created = {c.sha for c in new_commits}
    if new_commits:
        parts.append(_count(len(new_commits), "commit nouveau", "commits nouveaux"))
    newly_lost = [
        c for c in state.commits if c.lost and (c.sha not in before or not before[c.sha].lost)
    ]
    old_refs = {r.name: r for r in previous.refs}
    new_refs = {r.name: r for r in state.refs}

    def by_kind(kind: str) -> tuple[list[str], list[str], list[str]]:
        added = [r.short_name for n, r in new_refs.items() if r.kind == kind and n not in old_refs]
        gone = [r.short_name for n, r in old_refs.items() if r.kind == kind and n not in new_refs]
        moved = [
            r.short_name
            for n, r in new_refs.items()
            if r.kind == kind
            and n in old_refs
            and old_refs[n].commit != r.commit
            and not (n == head.ref == previous.head.ref and r.commit in created)
        ]
        return added, gone, moved

    added, gone, moved = by_kind("branch")
    if added:
        parts.append(_count(len(added), "branche nouvelle", "branches nouvelles"))
    if gone:
        parts.append(_count(len(gone), "branche supprimée", "branches supprimées"))
    if moved:
        word = "branche" if len(moved) == 1 else "branches"
        verb = "déplacée" if len(moved) == 1 else "déplacées"
        parts.append(f"{word} {join_fr(moved)} {verb}")
    added, gone, moved = by_kind("tag")
    if added:
        parts.append(_count(len(added), "tag nouveau", "tags nouveaux"))
    if gone:
        parts.append(_count(len(gone), "tag supprimé", "tags supprimés"))
    remote = [len(x) for x in by_kind("remote")]
    if sum(remote):
        parts.append(
            _count(
                sum(remote), "référence distante mise à jour", "références distantes mises à jour"
            )
        )
    if newly_lost:
        parts.append(
            _count(len(newly_lost), "commit perdu", "commits perdus")
            + (", visible par reflog" if len(newly_lost) == 1 else ", visibles par reflog")
        )
    if (head.ref, head.commit, head.detached) != (
        previous.head.ref,
        previous.head.commit,
        previous.head.detached,
    ) and (head.detached or head.ref != previous.head.ref):
        parts.append(
            f"{DETACHED_TEXT} sur {short(head.commit)}"
            if head.detached
            else f"HEAD sur {_branch(state)}"
        )
    if state.index != previous.index:
        parts.append("index modifié")
    if _worktree_side(state) != _worktree_side(previous):
        parts.append("arbre de travail modifié")
    if state.stash != previous.stash:
        parts.append("stash modifié")
    if state.in_progress != previous.in_progress:
        parts.append(_IN_PROGRESS_TEXT[state.in_progress])
    if not parts:
        return "Vues à jour : le dépôt n'a pas changé."
    return "Vues mises à jour : " + ", ".join(parts) + "."


def _worktree_side(state: RepoState) -> tuple[list[str], list[tuple[str, str, str]]]:
    """Ce que l'arbre de travail montre : ses fichiers et leurs lettres côté arbre."""
    return state.worktree, [
        (e.path, e.kind, e.worktree_status) for e in state.status if e.worktree_status != "."
    ]


_IN_PROGRESS_TEXT = {
    "": "opération en cours terminée",
    "merge": "fusion en cours",
    "rebase": "rebase en cours",
    "cherry_pick": "cherry-pick en cours",
    "revert": "revert en cours",
}


def build_views(
    state: RepoState,
    previous: RepoState | None = None,
    restored: Iterable[str] = (),
    previous_graph: GraphView | None = None,
) -> Views:
    """Toutes les vues de `state_projected` pour l'état `state`."""
    return Views(
        repo=state,
        graph=build_graph(state, previous, restored, previous_graph),
        staging=build_staging(state),
        prompt=build_prompt(state),
        announce_text=announce(state, previous),
    )
