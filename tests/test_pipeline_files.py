"""Les trois écritures du pipeline (Story 7.6, AD-10) : balises `wds:job` / `wds:end` dans le
gabarit, plages de lignes tirées du SHA de tête, constats non bloquants, rien ne s'exécute.

Le test central relit `content/pipeline.yaml` : chaque tâche du pipeline simulé doit se retrouver
dans `.github/workflows/ci.yml`, `Jenkinsfile` et `.gitlab-ci.yml`, avec son libellé et la même
commande que `ci` lance (outil et argv de la sortie humaine) : les trois écritures ne peuvent pas
dériver du fichier que `ci` lit.
"""

from __future__ import annotations

import http.client
import shlex
from collections.abc import Iterator
from pathlib import Path

import pytest
from test_workspace_api import _call

from wavedevsecops import ci, cli, github_sim
from wavedevsecops.ci import pipeline_files as pf
from wavedevsecops.config import Settings
from wavedevsecops.contracts import AppError
from wavedevsecops.engine import INTENTS, prepare_workspace
from wavedevsecops.gitio import Git
from wavedevsecops.projections import project
from wavedevsecops.scenarios import LoadedScenario, load_scenario, parse_scenario
from wavedevsecops.terminal.allowlist import get_allowlist
from wavedevsecops.terminal.parse import Refused, parse_line
from wavedevsecops.web.code import pipeline_view
from wavedevsecops.web.exercise import RunExerciseCode

ROOT = Path(__file__).resolve().parent.parent
EXERCISE = ROOT / "content" / "exercise"
TRACKS = ("no_ai", "llm")
FILES = {f.tab_id: f for f in pf.PIPELINE_FILES}
PIPELINE = ci.load_pipeline(Settings())

SETUP = """\
schema_version: 1
scenario_id: essai
mode: A
title_text: Essai
tracks: [no_ai]
tools: [git]
setup:
  - op: exercise_stage
    stage: base
  - op: commit
    message: Gabarit
  - op: push
    branch: main
  - op: switch
    branch: feature
    create: true
{feature}
  - op: commit
    message: Change la branche
  - op: push
    as: feature
  - op: switch
    branch: main
  - op: open_pr
    head: feature
    title_text: Change la branche
    checks:
      - {{job_id: ruff, state: success}}
      - {{job_id: pytest, state: failure}}
      - {{job_id: gitleaks, state: queued}}
      - {{job_id: bandit, state: success}}
      - {{job_id: revue_manuelle, state: success}}
"""
NOTES = '  - op: write_file\n    path: NOTES.md\n    content: "notes\\n"'


# ------------------------------------------------------------------ le gabarit
def _contract(track: str, file: pf.PipelineFile, findings: object) -> str:
    """Message d'échec : la règle à suivre quand une story ajoute un job (8.1, 8.3, 8.4, 8.6)."""
    return (
        f"content/exercise/{track}/{file.path} ne suit pas content/pipeline.yaml "
        f"(attendu, dans cet ordre : {', '.join(PIPELINE.job_ids)}). Chaque job de "
        "pipeline.yaml s'écrit dans les 6 fichiers CI des gabarits (no_ai et llm : "
        ".github/workflows/ci.yml, Jenkinsfile, .gitlab-ci.yml), encadré par "
        "« wds:job <job_id> » et « wds:end », chacun en commentaire seul sur sa ligne, avec son "
        f"label_text et la commande « outil + human » de pipeline.yaml. Constats : {findings}"
    )


def _code_lines(block: list[str]) -> str:
    """Lignes de la tâche hors commentaires : une commande commentée ne compte pas."""
    return "\n".join(line for line in block if not line.lstrip().startswith(("#", "//")))


def test_une_commande_commentee_ne_compte_pas() -> None:
    block = ["      # - run: uv run ruff check .", "      - run: echo"]
    assert "ruff check ." not in _code_lines(block)
    assert "echo" in _code_lines(block)


@pytest.mark.parametrize("track", TRACKS)
@pytest.mark.parametrize("tab", [f.tab_id for f in pf.PIPELINE_FILES])
def test_chaque_job_id_est_encadre_dans_les_trois_ecritures_du_gabarit(
    track: str, tab: str
) -> None:
    file = FILES[tab]
    text = (EXERCISE / track / file.path).read_text(encoding="utf-8")
    found = pf.job_ranges(file, text, PIPELINE.job_ids)
    assert found.findings == [], _contract(track, file, found.findings)
    # Même ordre que le pipeline : les tâches tournent en série.
    assert list(found.ranges) == PIPELINE.job_ids, _contract(track, file, found.findings)
    previous = 0
    for job_id, rng in found.ranges.items():
        assert rng.first > previous, job_id
        assert rng.last >= rng.first
        previous = rng.last
    # Aucune balise n'encadre une tâche que le pipeline ne connaît pas.
    marked = [pf.JOB_MARK.match(line) for line in text.splitlines()]
    assert [m["job_id"] for m in marked if m] == PIPELINE.job_ids
    assert sum(1 for line in text.splitlines() if pf.END_MARK.match(line)) == len(PIPELINE.job_ids)


@pytest.mark.parametrize("track", TRACKS)
@pytest.mark.parametrize("tab", [f.tab_id for f in pf.PIPELINE_FILES])
def test_les_trois_ecritures_refletent_content_pipeline_yaml(track: str, tab: str) -> None:
    """Libellé et commande de chaque tâche : ceux de `content/pipeline.yaml`, sans dérive."""
    file = FILES[tab]
    text = (EXERCISE / track / file.path).read_text(encoding="utf-8")
    ranges = pf.job_ranges(file, text, PIPELINE.job_ids).ranges
    lines = text.splitlines()
    for job in PIPELINE.jobs:
        rng = ranges[job.job_id]
        block = lines[rng.first - 1 : rng.last]
        code = _code_lines(block)
        command = shlex.join([job.tool, *job.human])
        assert command in code, (
            f"{track}/{file.path} : « {command} » (outil + human de content/pipeline.yaml) "
            f"absent des lignes non commentées de la tâche {job.job_id}"
        )
        assert job.label_text in "\n".join(block), f"{file.path} : libellé de {job.job_id}"
        # Une commande de la tâche n'est jamais celle d'une autre.
        for other in PIPELINE.jobs:
            if other.job_id != job.job_id:
                assert shlex.join([other.tool, *other.human]) not in code


def test_les_trois_gabarits_sont_identiques_entre_parcours() -> None:
    for file in pf.PIPELINE_FILES:
        texts = {(EXERCISE / t / file.path).read_text(encoding="utf-8") for t in TRACKS}
        assert len(texts) == 1, file.path


def test_les_balises_ne_sont_pas_reconnues_dans_une_phrase() -> None:
    """L'en-tête des fichiers cite « wds:job » et « wds:end » sans les ouvrir."""
    text = "# Les commentaires « wds:job » et « wds:end » encadrent chaque tâche.\n"
    found = pf.job_ranges(FILES["github"], text, [])
    assert found.ranges == {} and found.findings == []


# ------------------------------------------------------------------ plages et constats
def test_plages_sans_les_balises_et_texte_d_affichage() -> None:
    text = "a\n# wds:job ruff\nb\nc\n# wds:end\n// wds:job pytest\nd\n// wds:end\ne\n"
    found = pf.job_ranges(FILES["github"], text, ["ruff", "pytest"])
    assert found.findings == []
    assert found.ranges["ruff"] == pf.JobRange(3, 4) and found.ranges["ruff"].text == "lignes 3 à 4"
    assert found.ranges["pytest"].text == "ligne 7"


def test_crlf_et_balise_indentee() -> None:
    text = "x\r\n  # wds:job ruff\r\nb\r\n  # wds:end\r\n"
    found = pf.job_ranges(FILES["github"], text.replace("\r\n", "\n"), ["ruff"])
    assert found.ranges["ruff"] == pf.JobRange(3, 3)


@pytest.mark.parametrize(
    ("text", "rule", "kept"),
    [
        ("sans balise\n", pf.MARK_MISSING_RULE, []),
        ("# wds:job ruff\nb\n", pf.MARK_BROKEN_RULE, []),  # jamais fermée
        ("b\n# wds:end\n", pf.MARK_BROKEN_RULE, []),  # fermeture sans ouverture
        ("# wds:job ruff\n# wds:end\n", pf.MARK_BROKEN_RULE, []),  # tâche vide
        ("# wds:job ruff\nb\n# wds:job pytest\nc\n# wds:end\n", pf.MARK_BROKEN_RULE, ["pytest"]),
        (
            "# wds:job ruff\nb\n# wds:end\n# wds:job ruff\nc\n# wds:end\n",
            pf.MARK_BROKEN_RULE,
            ["ruff"],
        ),
    ],
)
def test_balise_absente_ou_mal_formee_donne_un_constat_jamais_une_exception(
    text: str, rule: str, kept: list[str]
) -> None:
    found = pf.job_ranges(FILES["jenkins"], text, ["ruff", "pytest"])
    assert any(f.rule_id == rule for f in found.findings), found.findings
    assert sorted(found.ranges) == sorted(kept)
    for finding in found.findings:
        assert finding.severity == "info" and finding.path == "Jenkinsfile"
        assert finding.message_text and "Traceback" not in finding.message_text


def test_une_tache_sans_balise_est_signalee_dans_le_fichier_concerne() -> None:
    found = pf.job_ranges(FILES["gitlab"], "# wds:job ruff\nx\n# wds:end\n", ["ruff", "pytest"])
    [missing] = [f for f in found.findings if f.rule_id == pf.MARK_MISSING_RULE]
    assert "pytest" in missing.message_text and missing.path == ".gitlab-ci.yml"
    assert "ruff" in found.ranges


# ------------------------------------------------------------------ sur le SHA de tête
def _prepare(tmp_path: Path, git_path: Path, feature: str = NOTES):
    settings = Settings(data_dir=tmp_path / "data")
    loaded = LoadedScenario(
        parse_scenario(SETUP.format(feature=feature), "essai.A.yaml"), Path("essai.A.yaml"), "0"
    )
    prepared = prepare_workspace(loaded, "no_ai", settings=settings, git_path=git_path)
    git = Git.for_workspace(git_path, prepared.layout.root, settings)
    return prepared.layout, git, settings


def test_les_plages_viennent_du_sha_de_tete_de_la_pr(tmp_path: Path, git_path: Path) -> None:
    layout, git, _ = _prepare(tmp_path, git_path)
    view = pipeline_view(git, layout, PIPELINE, 1)
    pull = github_sim.load(layout).pulls[0]
    assert view["head_sha"] == pull.head_sha and view["findings"] == []
    assert view["read_only_text"] == "Lecture seule" and view["notice_text"] == ""
    assert [t["label_text"] for t in view["tabs"]] == ["GitHub Actions", "Jenkins", "GitLab CI"]
    assert [t["path"] for t in view["tabs"]] == [
        ".github/workflows/ci.yml",
        "Jenkinsfile",
        ".gitlab-ci.yml",
    ]
    for tab in view["tabs"]:
        assert tab["available"] and list(tab["jobs"]) == PIPELINE.job_ids
        text = (EXERCISE / "no_ai" / tab["path"]).read_text(encoding="utf-8")
        assert tab["content"] == text
        for job_id, rng in tab["jobs"].items():
            assert rng["range_text"].startswith("ligne")
            assert job_id in tab["jobs"] and rng["first"] <= rng["last"]
    ruff = view["tabs"][1]["jobs"]["ruff"]
    assert ruff["a11y_name_text"] == f"Lint (ruff) : {ruff['range_text']} de Jenkins"


def test_balises_absentes_sur_le_sha_de_tete_donnent_un_constat_non_bloquant(
    tmp_path: Path, git_path: Path
) -> None:
    broken = (
        '  - op: write_file\n    path: Jenkinsfile\n    content: "pipeline { agent any }\\n"\n'
        "  - op: write_file\n    path: .gitlab-ci.yml\n"
        '    content: "# wds:job ruff\\nruff:\\n  script: [x]\\n# wds:end\\n"'
    )
    layout, git, _ = _prepare(tmp_path, git_path, broken)
    view = pipeline_view(git, layout, PIPELINE, 1)  # aucune exception
    by_tab = {t["id"]: t for t in view["tabs"]}
    assert all(r is not None for r in by_tab["github"]["jobs"].values())
    assert set(by_tab["jenkins"]["jobs"].values()) == {None}
    assert (
        by_tab["gitlab"]["jobs"]["ruff"] is not None and by_tab["gitlab"]["jobs"]["pytest"] is None
    )
    paths = {f["path"] for f in view["findings"]}
    assert paths == {"Jenkinsfile", ".gitlab-ci.yml"}
    assert {f["rule_id"] for f in view["findings"]} == {pf.MARK_MISSING_RULE}
    assert view["notice_text"]
    # Sur `main` (sans cette modification), les balises sont toutes là : c'est bien le SHA de tête.
    main = pf.read_pipeline_files(
        git, layout, git.internal("rev-parse", "main", cwd=layout.repo).strip(), PIPELINE
    )
    assert all(not item.findings for item in main)


def test_un_fichier_absent_au_sha_de_tete_est_un_constat(tmp_path: Path, git_path: Path) -> None:
    layout, git, _ = _prepare(tmp_path, git_path)
    files = pf.read_pipeline_files(git, layout, "f" * 40, PIPELINE)  # SHA inconnu
    assert [item.available for item in files] == [False, False, False]
    assert all(item.findings[0].rule_id == pf.FILE_MISSING_RULE for item in files)
    view = pipeline_view(git, layout, PIPELINE, 1)
    assert view["tabs"][0]["available"]
    with pytest.raises(AppError):
        pipeline_view(git, layout, PIPELINE, 99)  # PR inconnue : refus propre, route en 404


def test_voir_dans_le_pipeline_n_est_propose_que_pour_les_taches_du_pipeline(
    tmp_path: Path, git_path: Path
) -> None:
    layout, git, _ = _prepare(tmp_path, git_path)
    rows = {
        c.job_id: c
        for c in project(git, layout, pipeline_jobs=frozenset(PIPELINE.job_ids))
        .views.remote.pulls[0]
        .checks
    }
    assert {j: c.in_pipeline for j, c in rows.items()} == {
        "ruff": True,
        "pytest": True,
        "gitleaks": True,
        "bandit": True,
        # Un check hors de content/pipeline.yaml n'a pas de tâche à montrer.
        "revue_manuelle": False,
    }
    default = project(git, layout).views.remote.pulls[0].checks
    assert not any(c.in_pipeline for c in default)


# ------------------------------------------------------------------ rien ne s'exécute
@pytest.mark.parametrize(
    "line",
    [
        "./Jenkinsfile",
        "bash Jenkinsfile",
        "sh .github/workflows/ci.yml",
        "python .gitlab-ci.yml",
        "jenkins",
        "gitlab-runner exec shell ruff",
        "act",
        "act -j ruff",
        "gh workflow run ci.yml",
        "git daemon",
    ],
)
def test_le_terminal_ne_lance_aucun_des_trois_fichiers(line: str) -> None:
    with pytest.raises(Refused):
        parse_line(line, get_allowlist(Settings()))


def test_aucune_intention_ne_lance_un_fichier_du_pipeline() -> None:
    """Aucune intention ne prend un chemin ou une commande à exécuter, hors le terminal gardé
    par la liste blanche ; le code d'exercice se lance sans argument (confirmation seule)."""
    risky = {"command", "argv", "script", "file", "job_id", "workflow"}
    for name, intent in INTENTS.items():
        fields = set(intent.model.model_fields)
        if name in {"check_rerun", "check_output_seen"}:
            continue  # `job_id` d'un check : relance un outil de `ci`, jamais un fichier
        assert not fields & risky, (name, fields & risky)
    assert set(RunExerciseCode.model_fields) == {"confirmed"}


def test_le_module_ne_fait_que_lire() -> None:
    source = (ROOT / "src" / "wavedevsecops" / "ci" / "pipeline_files.py").read_text("utf-8")
    for forbidden in ("spawn", "run_tool", "subprocess", "os.system", "Popen", "procs"):
        assert forbidden not in source, forbidden
    assert '"cat-file"' in source  # lecture d'un blob, ni checkout ni exécution


# ------------------------------------------------------------------ la route de la vue Code
LINT = ROOT / "content" / "scenarios" / "defaut-de-lint.A.yaml"
LINT_WS = "no_ai.defaut-de-lint.A"


@pytest.fixture
def lint_instance(tmp_path: Path, git_path: Path) -> Iterator[cli.Instance]:
    """Serveur sur un espace du gabarit, avec une branche poussée et une PR ouverte."""
    settings = Settings(data_dir=tmp_path / "data")
    prepared = prepare_workspace(
        load_scenario(LINT, settings), "no_ai", settings=settings, git_path=git_path
    )
    git = Git.for_workspace(git_path, prepared.layout.root, settings)
    repo = prepared.layout.repo
    identity = ("-c", "user.name=Essai", "-c", "user.email=essai@example.test")
    git.internal("switch", "-c", "feature", cwd=repo)
    git.internal(*identity, "commit", "--allow-empty", "-m", "Change", cwd=repo)
    git.internal("push", "origin", "feature", cwd=repo)
    github_sim.open_pr(git, prepared.layout, "feature")
    inst = cli.start_instance(settings)
    try:
        yield inst
    finally:
        inst.stop()


def _session(inst: cli.Instance) -> dict[str, str]:
    conn = http.client.HTTPConnection(cli.HOST, inst.port, timeout=30)
    conn.request("GET", f"/?t={inst.token}")
    response = conn.getresponse()
    response.read()
    conn.close()
    return {"Cookie": response.getheader("Set-Cookie", "").split(";")[0]}


def test_la_route_sert_les_trois_ecritures_au_sha_de_tete(lint_instance: cli.Instance) -> None:
    session = _session(lint_instance)
    url = f"/api/ws/{LINT_WS}/code/pipeline"
    status, view = _call(lint_instance, "GET", f"{url}?pr=1", session)
    assert status == 200
    assert [t["id"] for t in view["tabs"]] == ["github", "jenkins", "gitlab"]
    assert view["findings"] == [] and view["read_only_text"] == "Lecture seule"
    for tab in view["tabs"]:
        assert all(tab["jobs"][job_id] for job_id in PIPELINE.job_ids), tab["id"]
    status, refused = _call(lint_instance, "GET", f"{url}?pr=9", session)
    assert status == 404 and "n'existe pas" in refused["reason_text"]
    anonymous = http.client.HTTPConnection(cli.HOST, lint_instance.port, timeout=30)
    anonymous.request("GET", f"{url}?pr=1")
    assert anonymous.getresponse().status in (401, 403)  # session requise, comme l'espace
    anonymous.close()
    # La vue est une lecture : aucune route d'écriture ni d'exécution n'existe pour ces fichiers.
    status, _ = _call(lint_instance, "POST", url, session, {})
    assert status in (404, 405)


def test_un_pipeline_yaml_illisible_est_un_refus_409_et_non_une_pr_absente(
    lint_instance: cli.Instance, monkeypatch: pytest.MonkeyPatch
) -> None:
    def broken(*_args: object, **_kwargs: object) -> ci.Pipeline:
        raise ci.PipelineError("content/pipeline.yaml est invalide.", "Corrigez le fichier.")

    monkeypatch.setattr(ci, "load_pipeline", broken)
    session = _session(lint_instance)
    status, refused = _call(
        lint_instance, "GET", f"/api/ws/{LINT_WS}/code/pipeline?pr=1", session
    )
    assert status == 409 and "pipeline.yaml est invalide" in refused["reason_text"]
