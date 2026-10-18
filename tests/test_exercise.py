"""Gabarits d'exercice des deux parcours (Story 2.11, AD-7, AD-12, AD-13, FR-16).

Les tests des gabarits tournent ici dans un sous-processus pytest, sans `httpx` ni réseau :
leur appel LLM est remplacé.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
import tomllib
from pathlib import Path

import pytest

from wavedevsecops.config import Settings
from wavedevsecops.engine import WorkspaceError, prepare_workspace
from wavedevsecops.scenarios import LoadedScenario, SetupError, parse_scenario
from wavedevsecops.scenarios.ops.exercise_stage import LLM_STAGES, template_files

EXERCISE = Path(__file__).resolve().parent.parent / "content" / "exercise"
REQUIRED = ("pyproject.toml", "uv.lock", "tests", ".gitignore", ".pre-commit-config.yaml")
# Le code d'exercice : ce qui est propre à un parcours (FR-16).
LLM_ONLY = {
    "llm.toml",
    "src/inventory/__main__.py",
    "src/inventory/llm_client.py",
    "src/inventory/llm_config.py",
    "tests/test_llm.py",
}
PIN = re.compile(r"^(?P<name>[A-Za-z0-9._-]+)==(?P<version>[\w.]+)$")


def _files(track: str) -> set[str]:
    files = template_files(EXERCISE / track)
    return {path for path in files if not path.startswith("stages/")}


@pytest.mark.parametrize("track", ["llm", "no_ai"])
def test_chaque_gabarit_a_les_fichiers_requis(track: str) -> None:
    for name in REQUIRED:
        assert (EXERCISE / track / name).exists(), f"{track}/{name}"


def test_seul_le_code_d_exercice_differe() -> None:
    llm, no_ai = _files("llm"), _files("no_ai")
    assert no_ai < llm
    assert llm - no_ai == LLM_ONLY
    for name in sorted(no_ai - {"pyproject.toml", "uv.lock"}):
        assert (EXERCISE / "llm" / name).read_bytes() == (EXERCISE / "no_ai" / name).read_bytes()


def test_les_outils_sont_verrouilles_aux_versions_de_la_pile() -> None:
    root = Path(__file__).resolve().parent.parent
    main = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    chain = set(main["dependency-groups"]["chain"])
    for track in ("llm", "no_ai"):
        project = tomllib.loads((EXERCISE / track / "pyproject.toml").read_text(encoding="utf-8"))
        assert set(project["dependency-groups"]["chain"]) == chain
        pins = {}
        for spec in chain | set(project["project"]["dependencies"]):
            found = PIN.match(spec)
            assert found, f"{track} : dépendance non épinglée : {spec}"
            pins[found["name"]] = found["version"]
        lock = tomllib.loads((EXERCISE / track / "uv.lock").read_text(encoding="utf-8"))
        locked = {p["name"]: p["version"] for p in lock["package"]}
        for name, version in pins.items():
            assert locked.get(name) == version, f"{track} : {name} {locked.get(name)} != {version}"


def test_llm_toml_vise_ollama_local_et_declare_ses_endpoints() -> None:
    config = tomllib.loads((EXERCISE / "llm" / "llm.toml").read_text(encoding="utf-8"))
    assert config["base_url"] == "http://127.0.0.1:11434/v1"
    assert config["base_url"] in config["allowed_endpoints"]
    assert "httpx" in " ".join(
        tomllib.loads((EXERCISE / "llm" / "pyproject.toml").read_text(encoding="utf-8"))["project"][
            "dependencies"
        ]
    )


def test_le_code_d_exercice_n_est_pas_dans_la_base_du_gabarit_llm() -> None:
    assert "src/inventory/assistant.py" not in _files("llm")
    stages = {p.name for p in (EXERCISE / "llm" / "stages").iterdir()}
    assert stages == set(LLM_STAGES)


def _loaded(track: str, stage: str) -> LoadedScenario:
    text = (
        "schema_version: 1\nscenario_id: essai\nmode: A\ntitle_text: Essai\n"
        f"tracks: [{track}]\ntools: [git]\nsetup:\n"
        f"  - op: exercise_stage\n    stage: {stage}\n  - op: commit\n    message: Gabarit\n"
    )
    return LoadedScenario(parse_scenario(text, "essai.A.yaml"), Path("essai.A.yaml"), "h")


def _prepare(track: str, stage: str, tmp_path: Path, git_path: Path) -> Path:
    settings = Settings(data_dir=tmp_path / "data")
    prepared = prepare_workspace(_loaded(track, stage), track, settings=settings, git_path=git_path)
    return prepared.layout.repo


USE_TEMPLATE_LOCK = os.environ.get("WDS_EXERCISE_UV") == "1"
"""En CI : les tests du gabarit tournent dans son environnement verrouillé, créé par
`uv sync --offline --frozen` depuis le cache uv préchargé (AD-12), `httpx` compris.
Sinon : avec l'interpréteur de l'application, sans `httpx`."""


def _run_tests(repo: Path) -> subprocess.CompletedProcess[str]:
    env = {k: v for k, v in os.environ.items() if not k.startswith(("PYTHON", "WDS_"))}
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    pytest_args = ["pytest", "-q", "--tb=short", "-rs", "-p", "no:cacheprovider"]
    if USE_TEMPLATE_LOCK:
        env["UV_PROJECT_ENVIRONMENT"] = str(repo.parent / "cache" / "venv")
        argv = ["uv", "run", "--offline", "--frozen", *pytest_args]
    else:
        argv = [sys.executable, "-I", "-m", *pytest_args]
    result = subprocess.run(  # noqa: S603 - sous-processus de test, argv fixe
        argv, cwd=repo, env=env, capture_output=True, text=True, timeout=300
    )
    if USE_TEMPLATE_LOCK:
        # Dans l'environnement du gabarit, aucun test n'est sauté (chemin `httpx` compris).
        assert "skipped" not in result.stdout, result.stdout
    return result


def test_parcours_sans_ia_pose_le_gabarit_et_ses_tests_passent(
    tmp_path: Path, git_path: Path
) -> None:
    repo = _prepare("no_ai", "base", tmp_path, git_path)
    for name in REQUIRED:
        assert (repo / name).exists(), name
    assert not (repo / "llm.toml").exists()
    result = _run_tests(repo)
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.parametrize("stage", LLM_STAGES)
def test_parcours_llm_pose_chaque_stade_et_ses_tests_passent_hors_ligne(
    stage: str, tmp_path: Path, git_path: Path
) -> None:
    repo = _prepare("llm", stage, tmp_path, git_path)
    for name in (*REQUIRED, "llm.toml", "src/inventory/assistant.py"):
        assert (repo / name).exists(), name
    assert not (repo / "stages").exists()
    assert (repo / "src/inventory/assistant.py").read_bytes().count(b"\r") == 0
    result = _run_tests(repo)
    assert result.returncode == 0, result.stdout + result.stderr


def test_les_stades_avancent(tmp_path: Path, git_path: Path) -> None:
    seen = {}
    for stage in LLM_STAGES:
        repo = _prepare("llm", stage, tmp_path / stage, git_path)
        seen[stage] = (repo / "src/inventory/assistant.py").read_text(encoding="utf-8")
    assert "SYSTEM_PROMPT" not in seen["simple_call"]
    assert "SYSTEM_PROMPT" in seen["system_prompt"] and "TOOLS" not in seen["system_prompt"]
    assert "TOOLS" in seen["tools"] and "MAX_STEPS" not in seen["tools"]
    assert "MAX_STEPS" in seen["loop"]


def test_un_stade_du_mauvais_parcours_est_refuse(tmp_path: Path, git_path: Path) -> None:
    with pytest.raises(SetupError, match="n'existe pas pour le parcours « no_ai »"):
        _prepare("no_ai", "loop", tmp_path / "a", git_path)
    with pytest.raises(SetupError, match="demande un stade du code LLM"):
        _prepare("llm", "base", tmp_path / "b", git_path)


def test_un_gabarit_absent_laisse_un_espace_propre(tmp_path: Path, git_path: Path) -> None:
    settings = Settings(data_dir=tmp_path / "data", content_dir=tmp_path / "vide")
    with pytest.raises(SetupError, match="introuvable"):
        prepare_workspace(
            _loaded("no_ai", "base"), "no_ai", settings=settings, git_path=git_path
        )
    assert not (tmp_path / "data" / "workspaces" / "no_ai").exists() or not any(
        (tmp_path / "data" / "workspaces" / "no_ai").iterdir()
    )


def test_un_parcours_non_servi_reste_refuse(tmp_path: Path, git_path: Path) -> None:
    with pytest.raises(WorkspaceError):
        prepare_workspace(
            _loaded("llm", "simple_call"),
            "no_ai",
            settings=Settings(data_dir=tmp_path),
            git_path=git_path,
        )
