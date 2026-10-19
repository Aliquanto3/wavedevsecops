"""Correspondances entre vues, noms courts et clés d'explication (story 2.10, AD-2).

`annotate` complète les `Views` d'un espace avec :

- `links` : pour un `element_id`, ceux qui lui sont liés, selon la table « Correspondances entre
  vues » de l'UX. Ce sont des arêtes déclarées, lues dans les deux sens par le front, qui n'en
  déduit aucune. Les cibles absentes de la vue affichée (un `path:head:…` sans diff ouvert) sont
  permises. Les lignes du diff, projetées à la demande, portent leurs propres `links`
  (`projections.diff`) ;
- `names` : le nom court de chaque élément projeté, pour « 3 éléments liés : ref origin/main,
  PR n°2, fichier config.py » ;
- `explain` : la clé d'explication (`content/explanations.yaml`) de chaque élément projeté.

Rien ici ne lit le disque : tout vient des vues déjà calculées.
"""

from __future__ import annotations

from wavedevsecops.contracts import Views, element_id, parse_element_id
from wavedevsecops.projections.views import (
    EXPLAIN_CHECK,
    EXPLAIN_COMMIT,
    EXPLAIN_PATH,
    EXPLAIN_PR,
    EXPLAIN_REMOTE,
    EXPLAIN_REVIEW,
    EXPLAIN_SBOM,
    pipeline_explain_ref,
)

PATH_ZONES = ("head", "index", "worktree")
"""Les trois zones d'un `path:…` : le commit (HEAD), l'index et l'arbre de travail."""


def path_ids(path: str) -> list[str]:
    """Le même fichier dans ses trois zones (une seule correspondance : le chemin)."""
    return [element_id("path", zone, path) for zone in PATH_ZONES]


def diff_links(commit: str, path: str) -> list[str]:
    """Liens d'une ligne ou d'un en-tête de diff : son commit (s'il y en a un) et son fichier."""
    return [*([element_id("commit", commit)] if commit else []), *path_ids(path)]


class _Edges:
    def __init__(self) -> None:
        self.edges: dict[str, list[str]] = {}

    def add(self, source: str, *targets: str) -> None:
        bucket = self.edges.setdefault(source, [])
        for target in targets:
            if target != source and target not in bucket:
                bucket.append(target)


def _label_name(kind: str, name_text: str) -> str:
    return {
        "branch": f"branche {name_text}",
        "remote": f"ref {name_text}",
        "tag": f"tag {name_text}",
    }.get(kind, "HEAD")


def annotate(views: Views) -> Views:
    """`views` complétées de `links`, `names` et `explain` (calculés depuis ses autres vues)."""
    edges = _Edges()
    names: dict[str, str] = {}
    explain: dict[str, str] = {}

    for node in views.graph.nodes:
        names[node.element_id] = f"commit {node.short_sha}"
        explain[node.element_id] = node.explain_ref
        edges.add(node.element_id, *node.links)
        for label in node.refs:
            names[label.element_id] = _label_name(label.kind, label.name_text)
            explain[label.element_id] = label.explain_ref
            edges.add(label.element_id, *label.links)

    paths: set[str] = set()
    for group in (views.staging.staged, views.staging.unstaged, views.staging.untracked):
        for item in group:
            names[item.element_id] = f"fichier {item.path}"
            explain[item.element_id] = EXPLAIN_PATH
            paths.add(item.path)
    for item in views.staging.stash:
        names[item.element_id] = f"stash {item.path.partition(' :')[0]}"
        explain[item.element_id] = EXPLAIN_COMMIT
    paths.update(views.repo.worktree)
    paths.update(entry.path for entry in views.repo.index)
    for path in sorted(paths):
        head, index, worktree = path_ids(path)
        edges.add(index, worktree, head)
        edges.add(worktree, head)

    remote = views.remote
    heads = {branch.element_id: branch.sha for branch in remote.branches}
    for branch in remote.branches:
        names[branch.element_id] = f"ref {branch.name_text}"
        explain.setdefault(branch.element_id, EXPLAIN_REMOTE)
        edges.add(branch.element_id, *branch.links)
    for pr in remote.pulls:
        label = f"PR n°{pr.number}"
        names[pr.element_id] = label
        explain[pr.element_id] = EXPLAIN_PR
        edges.add(pr.element_id, *pr.links)
        head = element_id("ref", f"refs/remotes/origin/{pr.head}")
        if head in heads:
            edges.add(pr.element_id, element_id("commit", heads[head]))
        for check in pr.checks:
            names[check.element_id] = f"check {check.job_id} ({label})"
            ref = pipeline_explain_ref(check.job_id, EXPLAIN_CHECK)
            explain[check.element_id] = ref
            if check.output_element_id and ref != EXPLAIN_CHECK:
                names[check.output_element_id] = f"sortie {check.job_id} ({label})"
                explain[check.output_element_id] = ref
            edges.add(check.element_id, *check.links)
            _, segments = parse_element_id(check.element_id)
            edges.add(check.element_id, element_id("commit", segments[2]))
            for row in check.sbom:
                names[row.element_id] = f"composant {row.name} {row.version} ({label})"
                explain[row.element_id] = EXPLAIN_SBOM
                edges.add(row.element_id, *row.links)
                edges.add(check.element_id, row.element_id)
        for entry in pr.review.entries:
            _, segments = parse_element_id(entry.element_id)
            names[entry.element_id] = f"revue n°{segments[1]} ({label})"
            explain[entry.element_id] = EXPLAIN_REVIEW
            edges.add(entry.element_id, *entry.links)

    return views.model_copy(update={"links": edges.edges, "names": names, "explain": explain})


__all__ = ["PATH_ZONES", "annotate", "diff_links", "path_ids"]
