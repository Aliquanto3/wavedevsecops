"""Règles de dépendance du spine (AD-1) et convention « Réglages »."""

from __future__ import annotations

from pathlib import Path

import pytest
from static_rules import (
    dependency_violations,
    env_read_violations,
    explanation_publish_violations,
    iter_modules,
    sandbox_write_violations,
)


def test_seule_la_file_publie_une_explication() -> None:
    assert explanation_publish_violations() == []


@pytest.mark.parametrize(
    "code",
    [
        "from wavedevsecops.events import StepExplanation\n",
        "from wavedevsecops import events\nevents.Kind.STEP_EXPLANATION\n",
        "emit('step_explanation', {})\n",
    ],
)
def test_explication_hors_file_detectee(tmp_path: Path, code: str) -> None:
    src = _write(
        tmp_path,
        {"web/x.py": code, "events/__init__.py": code, "engine/operations.py": code},
    )
    violations = explanation_publish_violations(src, "pkg")
    assert len(violations) == 1, violations
    assert violations[0].startswith("pkg.web.x")


def _write(root: Path, files: dict[str, str]) -> Path:
    src = root / "pkg"
    for name, code in files.items():
        path = src / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(code, encoding="utf-8")
    return src


def test_depot_respecte_les_regles_de_dependance() -> None:
    assert dependency_violations() == []


def test_seul_config_lit_l_environnement() -> None:
    assert env_read_violations() == []


def test_les_modules_feuilles_existent() -> None:
    modules = {name for name, _ in iter_modules()}
    assert {
        "wavedevsecops.config",
        "wavedevsecops.contracts",
        "wavedevsecops.events",
        "wavedevsecops.procs",
    } <= modules


@pytest.mark.parametrize(
    ("files", "expected"),
    [
        ({"contracts/__init__.py": "from pkg import config\n"}, "pkg.contracts (feuille)"),
        ({"events/__init__.py": "from ..contracts import x\n"}, "pkg.events (feuille)"),
        ({"config.py": "import pkg.events\n"}, "pkg.config (feuille)"),
        ({"engine/__init__.py": "from pkg.web import app\n"}, "importe web"),
        ({"web/__init__.py": "from pkg import cli\n"}, "importe cli"),
        ({"engine/__init__.py": "from pkg.procs import spawn\n"}, "réservé à gitio"),
        ({"engine/__init__.py": "import subprocess\n"}, "seul procs"),
        ({"engine/__init__.py": "import os\nos.system('x')\n"}, "appelle os.system"),
        ({"engine/__init__.py": "import os as o\no.popen('x')\n"}, "appelle os.popen"),
        ({"engine/__init__.py": "from os import spawnv\n"}, "appelle os.spawnv"),
        ({"engine/__init__.py": "import os\nos.execvp('x', [])\n"}, "appelle os.execvp"),
        (
            {"engine/__init__.py": "import asyncio\nasyncio.create_subprocess_exec('x')\n"},
            "appelle asyncio.create_subprocess_exec",
        ),
        (
            {"engine/__init__.py": "from asyncio import create_subprocess_shell\n"},
            "seul procs",
        ),
        (
            {"engine/__init__.py": "from concurrent.futures import ProcessPoolExecutor\n"},
            "seul procs",
        ),
    ],
)
def test_violations_de_dependance_detectees(
    tmp_path: Path, files: dict[str, str], expected: str
) -> None:
    src = _write(tmp_path, files)
    violations = dependency_violations(src, "pkg")
    assert any(expected in v for v in violations), violations


def test_dependances_permises(tmp_path: Path) -> None:
    src = _write(
        tmp_path,
        {
            "cli.py": "from pkg.web import app\nfrom pkg import config\n",
            "web/__init__.py": "from . import routes\nfrom pkg.contracts import x\n",
            "gitio/__init__.py": "from pkg.procs import spawn\n",
            "procs/__init__.py": "import subprocess\nimport os\nos.system('x')\n",
            "engine/__init__.py": "import os\nos.path.join('a')\nimport asyncio\nasyncio.run\n",
        },
    )
    assert dependency_violations(src, "pkg") == []


@pytest.mark.parametrize(
    "code",
    [
        "import os\nos.environ['X']\n",
        "import os\nos.getenv('X')\n",
        "from os import environ\n",
        "from os import getenv\n",
        "import os as o\no.environ['X']\n",
    ],
)
def test_lecture_d_environnement_detectee(tmp_path: Path, code: str) -> None:
    src = _write(tmp_path, {"engine/__init__.py": code, "config.py": code})
    violations = env_read_violations(src, "pkg")
    assert len(violations) == 1
    assert violations[0].startswith("pkg.engine")


def test_seul_wsfs_ecrit_dans_le_bac_a_sable() -> None:
    assert sandbox_write_violations() == []


@pytest.mark.parametrize(
    ("code", "expected"),
    [
        ("open('x', 'w')\n", "open()"),
        ("from pathlib import Path\nPath('x').write_text('a')\n", ".write_text()"),
        ("import shutil\n", "importe shutil"),
        ("p = None\np.unlink()\n", ".unlink()"),
    ],
)
def test_ecriture_hors_wsfs_detectee(tmp_path: Path, code: str, expected: str) -> None:
    src = _write(tmp_path, {"scenarios/ops/x.py": code, "wsfs/__init__.py": code})
    violations = sandbox_write_violations(src, "pkg")
    assert len(violations) == 1, violations
    assert violations[0].startswith("pkg.scenarios") and expected in violations[0]
