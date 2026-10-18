"""Règles de dépendance du spine (AD-1) et convention « Réglages »."""

from __future__ import annotations

from pathlib import Path

import pytest
from static_rules import dependency_violations, env_read_violations, iter_modules


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
            "procs/__init__.py": "import subprocess\n",
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
    ],
)
def test_lecture_d_environnement_detectee(tmp_path: Path, code: str) -> None:
    src = _write(tmp_path, {"engine/__init__.py": code, "config.py": code})
    violations = env_read_violations(src, "pkg")
    assert len(violations) == 1
    assert violations[0].startswith("pkg.engine")
