"""Story 3.3 : la vue « Distant + PR » (`views.remote`), calculée par le serveur sur un vrai git."""

from __future__ import annotations

from pathlib import Path

import pytest
from test_github_sim import BASE, _commit_and_push

from wavedevsecops import github_sim
from wavedevsecops.config import Settings
from wavedevsecops.contracts import parse_element_id
from wavedevsecops.contracts.remote import RemoteView
from wavedevsecops.engine import prepare_workspace
from wavedevsecops.gitio import Git
from wavedevsecops.projections import project
from wavedevsecops.projections.remote import (
    _duration_text,
    announce_remote,
    branch_element,
    build_remote,
    previous_remote,
)
from wavedevsecops.scenarios import LoadedScenario, parse_scenario

PR_SETUP = """\
  - op: set_protection
    branch: main
    required_approvals: 2
    required_checks: [tests]
  - op: colleague_reaction
    trigger: pr_opened
    reviews:
      - {state: approved, body_text: "Bien vu."}
  - op: open_pr
    head: feature
    title_text: Change la valeur
    checks:
      - {job_id: lint, state: success}
      - {job_id: bandit, state: failure, required: true}
      - {job_id: build, state: running}
      - {job_id: audit, state: error}
      - {job_id: docs, state: queued}
"""


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(data_dir=tmp_path / "data")


def _prepare(settings: Settings, git_path: Path, extra: str = ""):
    text = BASE.format(feature_path="autre.py") + extra
    loaded = LoadedScenario(parse_scenario(text, "essai.A.yaml"), Path("essai.A.yaml"), "0" * 64)
    prepared = prepare_workspace(loaded, "llm", settings=settings, git_path=git_path)
    return prepared.layout, Git.for_workspace(git_path, prepared.layout.root, settings)


def test_branches_de_origin_et_proposition_d_ouvrir_une_pr(
    settings: Settings, git_path: Path
) -> None:
    layout, git = _prepare(settings, git_path)
    git.internal("branch", "meme-commit", "main", cwd=layout.repo)
    git.internal("push", "-q", "origin", "meme-commit", cwd=layout.repo)
    git.internal("switch", "-q", "-c", "extra", "main", cwd=layout.repo)
    (layout.repo / "extra.txt").write_text("x\n", encoding="utf-8")
    git.internal("add", "extra.txt", cwd=layout.repo)
    _commit_and_push(git, layout, "extra", "extra.txt", "y\n")
    remote = build_remote(git, layout, "extra")
    by_name = {b.name_text: b for b in remote.branches}
    assert sorted(by_name) == [
        "origin/extra",
        "origin/feature",
        "origin/main",
        "origin/meme-commit",
    ]
    # Poussée sans PR, avec du travail : on propose « Ouvrir une PR » ; main et une branche
    # déjà contenue dans main n'ont rien à merger.
    assert [n for n, b in by_name.items() if b.can_open_pr] == ["origin/extra", "origin/feature"]
    assert remote.pulls == []
    main = by_name["origin/main"]
    assert main.element_id == branch_element("main") == "ref:refs/remotes/origin/main"
    assert parse_element_id(main.element_id) == ("ref", ["refs/remotes/origin/main"])
    assert main.a11y_name_text.startswith("branche distante origin/main, commit ")
    assert main.short_sha == main.sha[:7]


def test_carte_de_pr_checks_blocage_et_journal(settings: Settings, git_path: Path) -> None:
    layout, git = _prepare(settings, git_path, PR_SETUP)
    remote = project(git, layout).views.remote
    assert [p.number for p in remote.pulls] == [1]
    card = remote.pulls[0]
    assert (card.element_id, card.title_text, card.branches_text) == (
        "pr:1",
        "Change la valeur",
        "feature → main",
    )
    assert (card.state, card.state_text, card.current) == ("open", "Ouverte", True)
    # Ordre : échecs et erreurs, puis en attente et en cours, puis réussis.
    assert [(c.job_id, c.state_text) for c in card.checks] == [
        ("audit", "Erreur de l'outil"),
        ("bandit", "Échec"),
        ("build", "En cours"),
        ("docs", "En attente"),
        ("tests", "En attente"),
        ("lint", "Réussi"),
    ]
    required = {c.job_id for c in card.checks if c.required}
    assert required == {"bandit", "tests"}  # déclaré, ou exigé par la protection de main
    for check in card.checks:
        kind, segments = parse_element_id(check.element_id)
        assert (kind, segments[:2]) == ("check", ["1", check.job_id])
    bandit = next(c for c in card.checks if c.job_id == "bandit")
    assert bandit.a11y_name_text == "Check bandit, échec, obligatoire"
    # merge-blocked : une raison par ligne, liée à son élément, et Merger inactif.
    assert not card.merge.enabled and card.merge.disabled_text
    kinds = [r.kind for r in card.merge.reasons]
    assert kinds == ["check", "check", "approvals"]
    by_job = {c.job_id: c.element_id for c in card.checks}
    assert {r.element_id for r in card.merge.reasons[:2]} == {by_job["bandit"], by_job["tests"]}
    assert card.merge.reasons[2].element_id == "pr:1"
    # review-log : compteur et entrée du collègue.
    log = card.review
    assert (log.approvals, log.required) == (1, 2)
    assert (log.counter_text, log.required_text) == (
        "Approbations : 1 sur 2",
        "2 approbations requises",
    )
    entry = log.entries[0]
    assert (entry.element_id, entry.author, entry.actor) == (
        "review:1:1",
        "Sacha Martin",
        "colleague",
    )
    assert (entry.action_text, entry.body_text) == ("a approuvé", "Bien vu.")
    assert parse_element_id(entry.element_id)[0] == "review"


def test_pr_sans_protection_est_mergeable_et_la_pr_mergee_n_a_plus_de_bouton(
    settings: Settings, git_path: Path
) -> None:
    layout, git = _prepare(settings, git_path, "  - op: open_pr\n    head: feature\n")
    card = build_remote(git, layout, "main").pulls[0]
    assert card.title_text == "PR n°1 : feature"  # sans titre déclaré
    assert card.merge.enabled and card.merge.reasons == []
    assert card.review.counter_text == "Approbations : 0"
    assert card.review.required_text == "Aucune approbation requise"
    assert card.review.entries == []
    github_sim.merge_pr(git, layout, 1)
    merged = build_remote(git, layout, "main")
    done = merged.pulls[0]
    assert (done.state, done.state_text, done.current) == ("merged", "Mergée", False)
    assert not done.merge.enabled and done.merge.done_text.startswith("Mergée dans main (")
    # La branche mergée n'a plus rien à proposer.
    assert not {b.name_text: b for b in merged.branches}["origin/feature"].can_open_pr


def test_pr_courante_celle_de_la_branche_locale_sinon_la_plus_recente(
    settings: Settings, git_path: Path
) -> None:
    extra = "  - op: open_pr\n    head: feature\n"
    layout, git = _prepare(settings, git_path, extra)
    _commit_and_push(git, layout, "main", "app.py", "valeur = 5\n")
    git.internal("switch", "-q", "-c", "second", "main", cwd=layout.repo)
    _commit_and_push(git, layout, "second", "app.py", "valeur = 6\n")
    github_sim.open_pr(git, layout, "second", "main")
    on_second = build_remote(git, layout, "second")
    assert [(p.number, p.current) for p in on_second.pulls] == [(2, True), (1, False)]
    elsewhere = build_remote(git, layout, "main")
    assert [(p.number, p.current) for p in elsewhere.pulls] == [(2, True), (1, False)]
    on_feature = build_remote(git, layout, "feature")
    assert [(p.number, p.current) for p in on_feature.pulls] == [(1, True), (2, False)]


def test_github_json_illisible_dit_l_erreur_sans_faire_echouer_la_projection(
    settings: Settings, git_path: Path
) -> None:
    layout, git = _prepare(settings, git_path)
    layout.github_json.write_text("{pas du json", encoding="utf-8")
    views = project(git, layout).views
    assert views.remote.error_text and "illisible" in views.remote.error_text
    assert views.remote.branches == [] and views.remote.pulls == []


def test_annonce_des_changements_de_pr(settings: Settings, git_path: Path) -> None:
    layout, git = _prepare(settings, git_path)
    first = project(git, layout).views
    assert first.remote.pulls == []
    github_sim.open_pr(git, layout, "feature", "main")
    second = project(git, layout, first.model_dump(mode="json")).views
    assert "PR n°1 ouverte, feature → main." in second.announce_text
    assert previous_remote(second.model_dump(mode="json")) == second.remote
    github_sim.merge_pr(git, layout, 1)
    third = project(git, layout, second.model_dump(mode="json")).views
    assert "PR n°1 : mergée." in third.announce_text
    assert announce_remote(third.remote, third.remote) == ""
    assert previous_remote({"remote": 3}) is None and previous_remote(None) is None


def test_vue_sans_depot_distant_est_vide() -> None:
    assert RemoteView().branches == [] and RemoteView().error_text == ""


@pytest.mark.parametrize(
    ("ms", "text"),
    [(None, ""), (0, "0,0 s"), (2350, "2,4 s"), (59_000, "59,0 s"), (125_000, "2 min 05 s")],
)
def test_duree_en_mots(ms: int | None, text: str) -> None:
    assert _duration_text(ms) == text


def test_literal_redeclares_identiques_a_contracts_github() -> None:
    """Revue : `contracts.remote` redéclare les états de `contracts.github` (cycle d'import)."""
    from typing import get_args

    from wavedevsecops.contracts import github, remote

    for name in ("CheckState", "PrState", "ReviewState", "BlockKind"):
        assert get_args(getattr(remote, name)) == get_args(getattr(github, name)), name


def test_marques_designable_de_la_vue_distante(settings: Settings, git_path: Path) -> None:
    """Revue (contrat 5.2) : une désignation marque aussi branches, PR, checks et revues."""
    from wavedevsecops.engine.designation import mark_views

    layout, git = _prepare(settings, git_path, PR_SETUP)
    views = project(git, layout).views.model_dump(mode="json")
    marked = mark_views(views, frozenset({"check"}))
    remote = marked["remote"]
    card = remote["pulls"][0]
    assert all(c["designable"] for c in card["checks"])
    assert not card["designable"] and not any(b["designable"] for b in remote["branches"])
    assert not any(e["designable"] for e in card["review"]["entries"])
    assert previous_remote(marked) is not None  # la vue marquée se relit (annonces)
