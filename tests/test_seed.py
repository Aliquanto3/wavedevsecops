"""Arborescence et manifeste du dépôt amorcé (Structural Seed du spine)."""

from __future__ import annotations

import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_gitattributes_force_lf() -> None:
    lines = (ROOT / ".gitattributes").read_text(encoding="utf-8").splitlines()
    assert "* text=auto eol=lf" in lines


def test_manifeste() -> None:
    data = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    assert data["project"]["version"] == "0.1.0"
    assert set(data["dependency-groups"]) >= {"chain", "dev"}
    assert data["project"]["optional-dependencies"]["window"] == ["pywebview==6.2.1"]


def test_arborescence() -> None:
    src = ROOT / "src" / "wavedevsecops"
    for path in (
        src / "config.py",
        src / "contracts" / "__init__.py",
        src / "events" / "__init__.py",
        src / "procs" / "__init__.py",
        ROOT / "content",
        ROOT / "tests",
        ROOT / "uv.lock",
    ):
        assert path.exists(), path


def test_version_du_paquet_installe() -> None:
    import wavedevsecops

    assert wavedevsecops.__version__ == "0.1.0"
