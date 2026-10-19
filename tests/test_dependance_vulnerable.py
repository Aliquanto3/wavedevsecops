"""Scénario « dépendance vulnérable » (Story 8.3) : le job pip_audit du pipeline, ses lecteurs
(constats et SBOM), `sbom-view` et l'étape de PR qui juge un SBOM.

Le vrai pip-audit (version épinglée) tourne, avec les options exactes de `content/pipeline.yaml`,
contre le point OSV local servi depuis l'extrait figé : il refuse jinja2 3.1.2, puis accepte 3.1.6.
"""

from __future__ import annotations

import json
import os
import re
import sys
import tomllib
from collections.abc import Iterator
from pathlib import Path

import pytest

from wavedevsecops import ci, cli, github_sim, procs, toolrun
from wavedevsecops.ci import findings as parsers
from wavedevsecops.config import Settings
from wavedevsecops.contracts import element_id
from wavedevsecops.contracts.github import (
    Check,
    GithubState,
    PullRequest,
    SbomComponent,
    SbomVuln,
)
from wavedevsecops.engine import prepare_workspace
from wavedevsecops.engine.designation import correct, mark_views
from wavedevsecops.gitio import Git
from wavedevsecops.projections import EXPLAIN_REFS, project
from wavedevsecops.scenarios import load_scenario
from wavedevsecops.scenarios.steps import pr_state
from wavedevsecops.scenarios.steps._base import StepContext
from wavedevsecops.wsfs import Layout

SCENARIO = Settings().scenarios_path() / "dependance-vulnerable.A.yaml"
EXERCISE = Settings().content_path() / "exercise"
SHA, SHA2 = "a" * 40, "b" * 40
JOB = ci.load_pipeline(Settings()).job("pip_audit")
OSV_DATE = json.loads((Settings().osv_path() / "index.json").read_text("utf-8"))["extracted_on"]


# ------------------------------------------------------------------ contrat du job
def test_le_job_pip_audit_suit_le_contrat_d_ad_11() -> None:
    assert JOB is not None
    assert (JOB.tool, JOB.barrier, JOB.required) == ("pip-audit", "dependencies", True)
    assert JOB.exit_codes.meaning(0) == "success" and JOB.exit_codes.meaning(1) == "failure"
    assert JOB.exit_codes.meaning(2) == "error"
    # Les trois exécutions (humaine, json, cyclonedx-json) portent les mêmes options exactes.
    common = [
        "--vulnerability-service",
        "osv",
        "--osv-url",
        "{osv_url}",
        "--no-deps",
        "--disable-pip",
        "--progress-spinner",
        "off",
        "-r",
        "requirements.txt",
    ]
    assert JOB.human == common
    assert [m.argv for m in JOB.machine] == [
        [*common, "-f", "json"],
        [*common, "-f", "cyclonedx-json"],
    ]
    assert [(m.parse, m.when) for m in JOB.machine] == [
        ("pip_audit_json", "failure"),
        ("cyclonedx_json", "always"),
    ]
    # Aucune option qui ferait taire le constat : l'apprenant ne règle pas l'outil.
    flat = " ".join(JOB.human)
    assert "--ignore-vuln" not in flat and "--dry-run" not in flat and "pypi" not in flat


def test_le_pip_audit_epingle_est_celui_de_la_pile() -> None:
    root = Path(__file__).resolve().parent.parent
    chain = tomllib.loads((root / "pyproject.toml").read_text("utf-8"))["dependency-groups"][
        "chain"
    ]
    assert "pip-audit==2.10.1" in chain
    for track in ("no_ai", "llm"):
        project_file = tomllib.loads((EXERCISE / track / "pyproject.toml").read_text("utf-8"))
        assert "pip-audit==2.10.1" in project_file["dependency-groups"]["chain"]


@pytest.mark.parametrize("track", ["no_ai", "llm"])
def test_les_exigences_du_gabarit_suivent_pyproject_et_uv_lock(track: str) -> None:
    """Le fichier lu par pip-audit : épinglé exactement, aux versions du `uv.lock`, et il
    couvre les dépendances de pyproject.toml (départ au vert, sans vulnérabilité connue)."""
    text = (EXERCISE / track / "requirements.txt").read_text("utf-8")
    pins = dict(re.findall(r"^([A-Za-z0-9._-]+)==([\w.]+)$", text, re.MULTILINE))
    lock = tomllib.loads((EXERCISE / track / "uv.lock").read_text("utf-8"))
    locked = {p["name"]: p["version"] for p in lock["package"]}
    assert all(locked[name] == version for name, version in pins.items())
    project_file = tomllib.loads((EXERCISE / track / "pyproject.toml").read_text("utf-8"))
    for spec in project_file["project"]["dependencies"]:
        assert spec in {f"{name}=={version}" for name, version in pins.items()}


# ------------------------------------------------------------------ lecteurs
PIP_AUDIT_JSON = json.dumps(
    {
        "dependencies": [
            {
                "name": "jinja2",
                "version": "3.1.2",
                "vulns": [
                    {
                        "id": "PYSEC-2026-1471",
                        "fix_versions": ["3.1.6"],
                        "aliases": ["CVE-2025-27516", "GHSA-cpwx-vrp4-4pq7"],
                        "description": "Sandbox breakout",
                    },
                    {"id": "PYSEC-2026-1471", "fix_versions": ["3.1.6"], "aliases": []},
                    {"id": "PYSEC-2026-1472", "fix_versions": [], "aliases": []},
                ],
            },
            {"name": "markupsafe", "version": "3.0.3", "vulns": []},
        ]
    }
)


def _tree(
    tmp_path: Path, requirements: str | None = "# x\nMarkupSafe==3.0.3\njinja2==3.1.2\n"
) -> Path:
    if requirements is not None:
        (tmp_path / "requirements.txt").write_text(requirements, "utf-8")
    return tmp_path


def test_le_lecteur_pip_audit_nomme_la_dependance_la_faille_la_ligne_et_la_base(
    tmp_path: Path,
) -> None:
    found = parsers.parse_pip_audit_json(PIP_AUDIT_JSON, _tree(tmp_path))
    # Un constat par couple (dépendance, faille) : le doublon de pip-audit est écarté.
    assert [(f.rule_id, f.path, f.line) for f in found] == [
        ("PYSEC-2026-1471", "requirements.txt", 3),
        ("PYSEC-2026-1472", "requirements.txt", 3),
    ]
    first = found[0].message_text
    assert "jinja2 3.1.2 est vulnérable" in first and "GHSA-cpwx-vrp4-4pq7" in first
    assert "Corrigée dans la version 3.1.6" in first
    assert f"Base embarquée, figée au {OSV_DATE}" in first
    assert parsers.parse_pip_audit_json('{"dependencies": []}', tmp_path) == []


def test_le_lecteur_pip_audit_refuse_un_texte_vide_ou_illisible(tmp_path: Path) -> None:
    for bad in ("", "pas du json", "[]", '{"dependencies": 3}'):
        with pytest.raises(ValueError):
            parsers.parse_pip_audit_json(bad, tmp_path)


def test_une_dependance_non_auditee_est_un_constat_unscanned(tmp_path: Path) -> None:
    text = json.dumps(
        {"dependencies": [{"name": "inconnu", "version": "", "skip_reason": "introuvable"}]}
    )
    (found,) = parsers.parse_pip_audit_json(text, _tree(tmp_path))
    assert found.rule_id == parsers.UNSCANNED_RULE and "introuvable" in found.message_text


CYCLONEDX = json.dumps(
    {
        "components": [
            {"bom-ref": "r1", "name": "jinja2", "type": "library", "version": "3.1.2"},
            {
                "bom-ref": "r2",
                "name": "MarkupSafe",
                "version": "3.0.3",
                "licenses": [{"license": {"id": "BSD-3-Clause"}}],
            },
        ],
        "vulnerabilities": [
            {"id": "PYSEC-2026-1471", "affects": [{"ref": "r1"}]},
            {"id": "PYSEC-2026-1471", "affects": [{"ref": "r1"}]},
            {"id": "PYSEC-2026-1472", "affects": [{"ref": "r1"}]},
        ],
    }
)


def test_le_lecteur_cyclonedx_rend_les_composants_du_sbom(tmp_path: Path) -> None:
    jinja, markup = parsers.parse_cyclonedx_json(CYCLONEDX, _tree(tmp_path))
    assert (jinja.name, jinja.version, jinja.line) == ("jinja2", "3.1.2", 3)
    assert [v.vuln_id for v in jinja.vulns] == ["PYSEC-2026-1471", "PYSEC-2026-1472"]
    assert jinja.licenses == []  # pip-audit n'en écrit pas sans résolution
    assert (markup.licenses, markup.vulns, markup.line) == (["BSD-3-Clause"], [], 2)
    assert jinja.element() == "sbom:jinja2@3.1.2"
    with pytest.raises(ValueError):
        parsers.parse_cyclonedx_json("", tmp_path)
    with pytest.raises(ValueError):
        parsers.parse_cyclonedx_json('{"components": {}}', tmp_path)


# ------------------------------------------------------------------ le scénario
def test_le_scenario_declare_le_parcours_sans_ia_et_la_station_3() -> None:
    loaded = load_scenario(SCENARIO, Settings(), explain_keys=EXPLAIN_REFS)
    scenario = loaded.scenario
    assert scenario.pipeline is True and scenario.tracks == ["no_ai"]
    assert (scenario.station, scenario.section, scenario.catalogue) == (3, "stations", True)
    assert "pip-audit" in scenario.tools and not scenario.authoring_warnings()
    assert [s.step_id for s in scenario.steps] == [
        "pousser_feature",
        "ouvrir_pr",
        "lire_le_blocage",
        "designer_la_dependance",
        "corriger_et_pousser",
    ]
    for step in scenario.steps:
        assert step.hints is not None
        lead = step.hints.lead_text
        assert "3.1.6" not in lead  # le premier palier ne donne pas la réponse
    last = scenario.steps[-1]
    assert last.check_states == {"pip_audit": "success"}
    assert last.sbom_has == {"pip_audit": ["jinja2"]}  # ni fichier vidé, ni dépendance retirée


def test_les_termes_sca_et_sbom_renvoient_au_scenario() -> None:
    import yaml

    glossary = yaml.safe_load((Settings().content_path() / "glossary.yaml").read_text("utf-8"))
    terms = {t["id"]: t for t in glossary["terms"]}
    for term in ("sca", "sbom"):
        assert terms[term]["scenario_id"] == "dependance-vulnerable"


# ------------------------------------------------------------------ étape de PR et SBOM
def _layout(tmp_path: Path, check: Check | None, *, head: str = SHA) -> Layout:
    layout = Layout(tmp_path / "ws")
    layout.root.mkdir(parents=True)
    checks = [] if check is None else [check]
    pr = PullRequest(
        number=1, head="feature", base="main", head_sha=head, base_sha=SHA, checks=checks
    )
    github_sim._save(layout, GithubState(pulls=[pr], next_number=2))
    return layout


def _step(**extra: object) -> pr_state.Args:
    return pr_state.Args(
        type="pr_state",
        step_id="essai",
        title_text="t",
        instruction_text="i",
        explanation_text="e",
        head="feature",
        check_states={"pip_audit": "success"},
        sbom_has={"pip_audit": ["jinja2"]},
        **extra,
    )


def _check(state: str, sbom: list[SbomComponent], head: str = SHA) -> Check:
    return Check(job_id="pip_audit", head_sha=head, base_sha=SHA, state=state, sbom=sbom)  # type: ignore[arg-type]


def _status(layout: Layout) -> str:
    return pr_state.check(None, StepContext(step=_step(), layout=layout)).status


def test_l_etape_exige_le_composant_au_sbom_du_check(tmp_path: Path) -> None:
    jinja = SbomComponent(name="Jinja2", version="3.1.6")
    assert _status(_layout(tmp_path / "a", _check("success", [jinja]))) == "passed"
    # Contournement : le fichier de dépendances vidé ou supprimé, le check est vert mais le SBOM
    # ne contient plus jinja2 : l'étape ne valide pas.
    assert _status(_layout(tmp_path / "b", _check("success", []))) == "pending"
    other = SbomComponent(name="markupsafe", version="3.0.3")
    assert _status(_layout(tmp_path / "c", _check("success", [other]))) == "pending"
    # Un SBOM calculé pour un ancien SHA de tête ne compte pas ; un check encore rouge non plus.
    assert _status(_layout(tmp_path / "d", _check("success", [jinja], SHA2))) == "pending"
    assert _status(_layout(tmp_path / "e", _check("failure", [jinja]))) == "pending"
    assert _status(_layout(tmp_path / "f", None)) == "pending"


# ------------------------------------------------------------------ sbom-view (projection)
@pytest.fixture
def prepared(tmp_path: Path, git_path: Path):
    settings = Settings(data_dir=tmp_path / "data")
    loaded = load_scenario(SCENARIO, settings)
    prepared = prepare_workspace(loaded, "no_ai", settings=settings, git_path=git_path)
    git = Git.for_workspace(git_path, prepared.layout.root, settings)
    return prepared.layout, git, settings


def _open_pr_with_sbom(layout: Layout, git: Git) -> None:
    git.run("push", "-u", "origin", "feature", cwd=layout.repo)
    pr = github_sim.open_pr(git, layout, "feature", "main")
    github_sim.ensure_checks(git, layout, pr.number, [("pip_audit", True)])
    github_sim.set_check_state(
        git,
        layout,
        pr.number,
        "pip_audit",
        "failure",
        output="sortie",
        sbom=[
            SbomComponent(
                name="jinja2",
                version="3.1.2",
                line=4,
                vulns=[SbomVuln(vuln_id="PYSEC-2026-1471")],
            ),
            SbomComponent(name="markupsafe", version="3.0.3", licenses=["BSD-3-Clause"], line=5),
        ],
    )


def test_sbom_view_montre_composant_version_licence_vulnerabilites(
    prepared,
) -> None:
    layout, git, _ = prepared
    _open_pr_with_sbom(layout, git)
    views = project(git, layout).views
    (check,) = views.remote.pulls[0].checks
    jinja, markup = check.sbom
    assert (jinja.name, jinja.version, jinja.vulnerable) == ("jinja2", "3.1.2", True)
    assert [v.vuln_id for v in jinja.vulns] == ["PYSEC-2026-1471"]
    assert jinja.license_text == "non indiquée" and markup.license_text == "BSD-3-Clause"
    assert not markup.vulnerable and markup.vulns == []
    assert jinja.declared_text == "requirements.txt:4"
    assert "vulnérable : PYSEC-2026-1471" in jinja.a11y_name_text
    # Chaque ligne est liée à pyproject.toml, au fichier épinglé et au check, et désignable.
    assert jinja.element_id == "sbom:jinja2@3.1.2"
    assert set(jinja.links) == {
        check.element_id,
        element_id("path", "head", "requirements.txt"),
        element_id("path", "head", "pyproject.toml"),
    }
    assert views.links[jinja.element_id] == jinja.links
    assert jinja.element_id in views.links[check.element_id]
    assert jinja.element_id in views.names and jinja.element_id in views.explain
    assert views.explain[jinja.element_id] in EXPLAIN_REFS
    marked = mark_views(views.model_dump(mode="json"), frozenset({"sbom"}))
    rows = marked["remote"]["pulls"][0]["checks"][0]["sbom"]
    assert [r["designable"] for r in rows] == [True, True]
    other = mark_views(views.model_dump(mode="json"), frozenset({"commit"}))
    assert not other["remote"]["pulls"][0]["checks"][0]["sbom"][0]["designable"]


def test_l_empreinte_ignore_le_sbom(prepared) -> None:
    """Le SBOM est une sortie du job (comme `output`) : il ne change pas l'empreinte."""
    layout, git, _ = prepared
    _open_pr_with_sbom(layout, git)
    before = github_sim.canonical_digest(layout)
    state = github_sim.load(layout)
    check = state.pulls[0].checks[0].model_copy(update={"sbom": []})
    pulls = [state.pulls[0].model_copy(update={"checks": [check]})]
    github_sim._save(layout, state.model_copy(update={"pulls": pulls}))
    assert github_sim.canonical_digest(layout) == before


def test_la_designation_du_composant_vulnerable_est_corrigee(prepared) -> None:
    layout, git, settings = prepared
    step = next(
        s for s in load_scenario(SCENARIO, settings).scenario.steps if s.type == "designate"
    )
    assert step.accept == ["sbom"]
    good = correct(step, {}, ["sbom:jinja2@3.1.2"], None)
    assert good.correct and "le composant jinja2@3.1.2" in good.slots[0].text
    bad = correct(step, {}, ["sbom:markupsafe@3.0.3"], None)
    assert not bad.correct and "jinja2@3.1.2" in bad.slots[0].text


# ------------------------------------------------------------------ le vrai pip-audit
@pytest.fixture(scope="module")
def osv_url(tmp_path_factory: pytest.TempPathFactory) -> Iterator[str]:
    pytest.importorskip("pip_audit")
    inst = cli.start_instance(Settings(data_dir=tmp_path_factory.mktemp("osv")))
    try:
        yield Settings().osv_url(inst.port)
    finally:
        inst.stop()


@pytest.fixture
def real_pip_audit(monkeypatch: pytest.MonkeyPatch) -> None:
    """`ci` lance le pip-audit épinglé de l'environnement de développement, sans proxy."""
    for name in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("NO_PROXY", "127.0.0.1,localhost")
    real_spawn = procs.spawn

    def spawn(tool_id, args, *, cwd, venv, timeout, settings=None):  # noqa: ANN001, ANN202
        assert tool_id == "pip-audit"
        return real_spawn(
            [sys.executable, "-m", "pip_audit", *args],
            env=dict(os.environ),
            cwd=cwd,
            timeout=timeout,
        )

    monkeypatch.setattr(toolrun, "spawn_tool", spawn)


def _run(tree: Path, osv_url: str, tmp_path: Path) -> ci.JobResult:
    assert JOB is not None
    return ci.run_job(
        JOB,
        tree=tree,
        venv=None,
        tokens={"repo": str(tree), "osv_url": osv_url},
        settings=Settings(data_dir=tmp_path),
    )


def _scenario_tree(tmp_path: Path, git_path: Path) -> Path:
    prepared = prepare_workspace(
        load_scenario(SCENARIO, Settings()),
        "no_ai",
        settings=Settings(data_dir=tmp_path / "data"),
        git_path=git_path,
    )
    return prepared.layout.repo


def _fix(tree: Path) -> None:
    for name in ("pyproject.toml", "requirements.txt"):
        path = tree / name
        path.write_text(path.read_text("utf-8").replace("jinja2==3.1.2", "jinja2==3.1.6"), "utf-8")


@pytest.mark.slow
def test_le_vrai_pip_audit_refuse_jinja2_3_1_2_puis_accepte_3_1_6(
    tmp_path: Path, git_path: Path, osv_url: str, real_pip_audit: None
) -> None:
    tree = _scenario_tree(tmp_path, git_path)
    refused = _run(tree, osv_url, tmp_path)
    assert refused.state == "failure"
    # Sortie humaine verbatim de pip-audit : la dépendance et la faille.
    assert "jinja2" in refused.output and "3.1.2" in refused.output and "PYSEC-" in refused.output
    ids = {f.rule_id for f in refused.findings}
    assert "PYSEC-2026-1471" in ids
    assert all(f.path == "requirements.txt" and f.line == 4 for f in refused.findings)
    assert all(OSV_DATE in f.message_text for f in refused.findings)
    (jinja,) = refused.sbom
    assert (jinja.name, jinja.version) == ("jinja2", "3.1.2")
    assert "PYSEC-2026-1471" in {v.vuln_id for v in jinja.vulns}
    # La version corrigée : le check repasse au vert, le SBOM garde jinja2, sans vulnérabilité.
    _fix(tree)
    accepted = _run(tree, osv_url, tmp_path)
    assert (accepted.state, accepted.findings) == ("success", [])
    (jinja,) = accepted.sbom
    assert (jinja.name, jinja.version, jinja.vulns) == ("jinja2", "3.1.6", [])


@pytest.mark.slow
def test_les_contournements_ne_font_pas_passer_l_etape(
    tmp_path: Path, git_path: Path, osv_url: str, real_pip_audit: None
) -> None:
    """Leçon 6.2 : retirer ou vider le fichier de dépendances ne remplace pas la mise à jour."""
    tree = _scenario_tree(tmp_path, git_path)
    requirements = tree / "requirements.txt"
    # Fichier supprimé : pip-audit sort 1 sans rien lire, le check reste rouge.
    requirements.unlink()
    removed = _run(tree, osv_url, tmp_path)
    assert removed.state == "failure" and removed.sbom == []
    # Dépendance non épinglée : refusée par --no-deps, pas d'audit « à peu près ».
    requirements.write_text("jinja2>=3.1.2\n", "utf-8")
    assert _run(tree, osv_url, tmp_path).state == "failure"
    # Fichier vidé : le check est vert, mais le SBOM n'a plus jinja2 : l'étape ne valide pas.
    requirements.write_text("# plus rien\n", "utf-8")
    emptied = _run(tree, osv_url, tmp_path)
    assert emptied.state == "success" and emptied.sbom == []
    layout = _layout(
        tmp_path / "pr",
        Check(job_id="pip_audit", head_sha=SHA, base_sha=SHA, state="success", sbom=emptied.sbom),
    )
    assert _status(layout) == "pending"
    # Dépendance renommée (un autre paquet, sans faille) : même refus.
    requirements.write_text("markupsafe==3.0.3\n", "utf-8")
    other = _run(tree, osv_url, tmp_path)
    assert other.state == "success"
    layout = _layout(
        tmp_path / "pr2",
        Check(job_id="pip_audit", head_sha=SHA, base_sha=SHA, state="success", sbom=other.sbom),
    )
    assert _status(layout) == "pending"


@pytest.mark.slow
@pytest.mark.parametrize("track", ["no_ai", "llm"])
def test_le_depart_des_gabarits_est_vert_sous_pip_audit(
    tmp_path: Path, git_path: Path, osv_url: str, real_pip_audit: None, track: str
) -> None:
    """Les autres scénarios de la station 2 attendent tous les checks verts : le gabarit tel
    quel passe pip_audit, dans les deux parcours."""
    tree = tmp_path / track
    tree.mkdir()
    (tree / "requirements.txt").write_text(
        (EXERCISE / track / "requirements.txt").read_text("utf-8"), "utf-8"
    )
    result = _run(tree, osv_url, tmp_path)
    assert (result.state, result.findings) == ("success", []), result.output


@pytest.mark.slow
def test_la_correction_ne_touche_pas_uv_lock_et_la_version_corrigee_y_est_deja(
    prepared,
) -> None:
    """La version corrigée (jinja2 3.1.6) est celle du `uv.lock` du gabarit : déjà dans le cache
    préchargé, donc `uv sync --offline --frozen` (celui du pipeline) réussit avant comme après
    la correction, sans réseau. Le commit du scénario ne modifie que les deux fichiers épinglés."""
    layout, git, _ = prepared
    changed = git.run("diff", "--name-only", "HEAD~1", "HEAD", cwd=layout.repo)
    assert sorted(changed.stdout.split()) == ["pyproject.toml", "requirements.txt"]
    lock = tomllib.loads((layout.repo / "uv.lock").read_text("utf-8"))
    assert {p["name"]: p["version"] for p in lock["package"]}["jinja2"] == "3.1.6"
