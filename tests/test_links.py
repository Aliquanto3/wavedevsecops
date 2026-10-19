"""Liens entre vues, noms courts et explications (story 2.10, AD-2, AD-7).

Le serveur déclare `links`, `names` et `explain` dans `state_projected.views` ; les lignes du
diff portent leurs propres `links` ; `content/explanations.yaml` est servi par
`GET /api/explanations`. Vrais dépôts git, vraie PR du GitHub simulé.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml
from test_catalogue import call, cookie, instance  # noqa: F401  (fixtures)
from test_remote_dom import BLOCKED, _views

from wavedevsecops.config import Settings
from wavedevsecops.contracts import Views, element_id, parse_element_id
from wavedevsecops.projections import EXPLAIN_REFS
from wavedevsecops.projections.diff import parse_diff
from wavedevsecops.projections.links import PATH_ZONES, path_ids
from wavedevsecops.web.explanations import load_explanations

CONTENT = Path(__file__).resolve().parent.parent / "content"
SHA = "a" * 40
UNIFIED = """\
diff --git a/src/app.py b/src/app.py
index 1111111..2222222 100644
--- a/src/app.py
+++ b/src/app.py
@@ -1,2 +1,2 @@
 import os
-print("a")
+print("b")
"""


@pytest.fixture(scope="module")
def views(tmp_path_factory: pytest.TempPathFactory, git_path: Path) -> Views:
    root = tmp_path_factory.mktemp("liens")
    return Views.model_validate(_views(root, git_path, "pr", BLOCKED))


def _linked(views: Views, one: str, other: str) -> bool:
    """Lien déclaré dans un sens ou dans l'autre (le front lit les arêtes dans les deux sens)."""
    return other in views.links.get(one, []) or one in views.links.get(other, [])


def test_pr_branche_commit_et_checks_sont_lies(views: Views) -> None:
    (pr,) = views.remote.pulls
    branch = next(b for b in views.remote.branches if b.pr_number == pr.number)
    commit = element_id("commit", branch.sha)
    assert _linked(views, pr.element_id, branch.element_id)  # PR ↔ branche de tête
    assert _linked(views, pr.element_id, commit)  # PR ↔ commit de tête
    assert _linked(views, branch.element_id, commit)  # ref distante ↔ commit
    for check in pr.checks:
        assert _linked(views, check.element_id, pr.element_id)  # check ↔ PR
        assert _linked(views, check.element_id, commit)  # check ↔ commit testé
    assert pr.review.entries
    for entry in pr.review.entries:
        assert _linked(views, entry.element_id, pr.element_id)


def test_la_ref_distante_du_graphe_et_celle_du_distant_ont_le_meme_element_id(
    views: Views,
) -> None:
    graph_refs = {label.element_id for node in views.graph.nodes for label in node.refs}
    remote = {b.element_id for b in views.remote.branches}
    assert remote & graph_refs  # même identifiant : les deux vues s'allument ensemble


def test_un_fichier_est_lie_dans_ses_trois_zones(views: Views) -> None:
    paths = set(views.repo.worktree)
    assert paths
    for path in sorted(paths):
        head, index, worktree = path_ids(path)
        assert _linked(views, worktree, head) and _linked(views, index, worktree)
        assert _linked(views, index, head)


def test_chaque_element_projete_est_nomme_et_explique(views: Views) -> None:
    (pr,) = views.remote.pulls
    assert views.names[pr.element_id] == f"PR n°{pr.number}"
    branch = views.remote.branches[0]
    assert views.names[branch.element_id] == f"ref {branch.name_text}"
    for node in views.graph.nodes:
        assert views.names[node.element_id] == f"commit {node.short_sha}"
    for check in pr.checks:
        assert views.names[check.element_id] == f"check {check.job_id} (PR n°{pr.number})"
    for element, key in views.explain.items():
        assert key in EXPLAIN_REFS, f"{element} : clé inconnue « {key} »"
        assert element in views.names, f"{element} sans nom court"
    # Tout élément projeté qui se sélectionne (commit, ref, PR, check, revue) a une explication.
    for element in views.names:
        kind, _ = parse_element_id(element)
        if kind in {"commit", "ref", "pr", "check", "review", "path"}:
            assert views.explain.get(element), f"{element} sans explication"


def test_les_liens_ne_citent_que_des_element_id_valides_et_sans_doublon(views: Views) -> None:
    for source, targets in views.links.items():
        parse_element_id(source)
        assert len(targets) == len(set(targets)) and source not in targets
        for target in targets:
            parse_element_id(target)


def test_sans_pr_les_liens_restent_ceux_du_graphe(
    tmp_path: Path, git_path: Path
) -> None:
    free = Views.model_validate(_views(tmp_path, git_path, "libre", ""))
    assert not any(k.startswith("pr:") for k in free.names)
    assert free.links  # au moins les chemins et les refs


# --- diff : liens des lignes et des en-têtes ---------------------------------------------------


def test_le_diff_d_un_commit_lie_ses_lignes_au_commit_et_au_fichier() -> None:
    diff = parse_diff(UNIFIED, SHA)
    (file,) = diff.files
    commit = element_id("commit", SHA)
    own = element_id("path", "head", "src/app.py")
    assert file.element_id == own and file.explain_ref == "code.file"
    assert commit in file.links and own not in file.links
    assert {element_id("path", z, "src/app.py") for z in PATH_ZONES} - {own} <= set(file.links)
    for line in (line for hunk in file.hunks for line in hunk.lines):
        assert line.links[0] == commit
        assert set(path_ids("src/app.py")) <= set(line.links)


def test_le_diff_de_l_arbre_de_travail_ne_cite_aucun_commit() -> None:
    diff = parse_diff(UNIFIED, "worktree")
    (file,) = diff.files
    assert file.element_id == element_id("path", "worktree", "src/app.py")
    assert not any(link.startswith("commit:") for link in file.links)
    for hunk in file.hunks:
        for line in hunk.lines:
            assert not any(link.startswith("commit:") for link in line.links)
            assert set(path_ids("src/app.py")) <= set(line.links)


# --- content/explanations.yaml ------------------------------------------------------------------


def test_le_catalogue_d_explications_couvre_exactement_les_cles_projetees() -> None:
    catalogue = load_explanations(Settings(content_dir=CONTENT))
    assert catalogue is not None
    assert set(catalogue.entries) == set(EXPLAIN_REFS)


def test_chaque_explication_est_courte_en_francais_et_au_vouvoiement() -> None:
    catalogue = load_explanations(Settings(content_dir=CONTENT))
    assert catalogue is not None
    barriers = {
        b["id"]
        for station in yaml.safe_load((CONTENT / "chain.yaml").read_text("utf-8"))["stations"]
        for b in station.get("barriers", [])
    }
    for key, entry in catalogue.entries.items():
        sentences = [s for s in re.split(r"(?<=[.!?])\s+", entry.body_text.strip()) if s]
        assert 2 <= len(sentences) <= 3, f"{key} : {len(sentences)} phrases"
        text = f"{entry.title_text} {entry.body_text}".lower()
        assert not re.search(r"\b(tu|ton|ta|tes|toi|te)\b", text), f"{key} : tutoiement"
        assert "http" not in text, f"{key} : lien externe"
        assert entry.barrier_id == "" or entry.barrier_id in barriers, key


def test_un_catalogue_absent_ou_invalide_donne_un_catalogue_vide(tmp_path: Path) -> None:
    assert load_explanations(Settings(content_dir=tmp_path)) is None
    (tmp_path / "explanations.yaml").write_text("schema_version: 1\nentries: 3\n", "utf-8")
    assert load_explanations(Settings(content_dir=tmp_path)) is None


def test_get_explanations_sert_le_catalogue(instance, cookie) -> None:  # noqa: F811
    status, body = call(instance, "GET", "/api/explanations", cookie)
    assert status == 200 and body["schema_version"] == 1
    assert set(body["entries"]) == set(EXPLAIN_REFS)
    entry = body["entries"]["graph.commit"]
    assert entry["title_text"] and entry["body_text"] and entry["barrier_id"] == ""
