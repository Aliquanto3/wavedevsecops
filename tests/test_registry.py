"""AD-16 : `tools.toml` est le registre unique, bien formé, et ses versions se comparent."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from wavedevsecops.registry import (
    Tool,
    at_least,
    extract_version,
    load_registry,
    parse_version,
)

ROOT = Path(__file__).resolve().parent.parent


def test_le_registre_declare_chaque_champ_de_chaque_outil() -> None:
    registry = load_registry(ROOT / "tools.toml")
    assert {"git", "uv", "gitleaks"} <= {t.id for t in registry.tool}
    for tool in registry.tool:
        assert tool.usage and tool.milestone and tool.provisioned_version
        assert isinstance(tool.network, bool)
        assert tool.network is False or tool.network_switch


def test_versions_minimales() -> None:
    registry = load_registry(ROOT / "tools.toml")
    assert registry.get("git").min_version == "2.38"
    assert registry.get("uv").min_version == "0.11.0"
    assert registry.get("gitleaks").min_version == "8.20.0"


def test_outil_inconnu() -> None:
    with pytest.raises(KeyError):
        load_registry(ROOT / "tools.toml").get("inconnu")


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("git version 2.55.0.windows.1", (2, 55, 0)),
        ("uv 0.12.23 (46b84fd0b 2026-10-03)", (0, 12, 23)),
        ("8.30.1", (8, 30, 1)),
        ("rien", None),
    ],
)
def test_parse_version(text: str, expected: tuple[int, ...] | None) -> None:
    assert parse_version(text) == expected


@pytest.mark.parametrize(
    ("found", "minimum", "expected"),
    [
        ((2, 38), "2.38", True),
        ((2, 38, 0), "2.38", True),
        ((2, 37, 9), "2.38", False),
        ((0, 11), "0.11.0", True),
        ((0, 10, 99), "0.11.0", False),
        ((3,), "2.38", True),
    ],
)
def test_at_least(found: tuple[int, ...], minimum: str, expected: bool) -> None:
    assert at_least(found, minimum) is expected


def test_extraction_par_l_expression_de_l_outil() -> None:
    tool = load_registry(ROOT / "tools.toml").get("git")
    assert extract_version(tool, "git version 2.55.0.windows.1\n") == (2, 55, 0)
    assert extract_version(tool, "autre chose 1.2.3") is None


def _tool(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "id": "x",
        "usage": "u",
        "milestone": "m",
        "resolution": "host",
        "provisioned_version": "1.0",
        "probe": ["--version"],
        "network": False,
    }
    return base | overrides


@pytest.mark.parametrize(
    "overrides",
    [
        {"probe": []},
        {"resolution": "provisioned"},
        {"network": True},
        {"version_regex": "("},
        {"resolution": "inconnue"},
        {"extra": 1},
    ],
)
def test_entrees_invalides_refusees(overrides: dict[str, object]) -> None:
    with pytest.raises((ValidationError, ValueError)):
        Tool.model_validate(_tool(**overrides))


def test_identifiants_en_double_refuses(tmp_path: Path) -> None:
    entry = (
        '[[tool]]\nid="a"\nusage="u"\nmilestone="m"\nresolution="host"\n'
        'provisioned_version="1"\nprobe=["-v"]\nnetwork=false\n'
    )
    path = tmp_path / "tools.toml"
    path.write_text(entry + entry, encoding="utf-8")
    with pytest.raises(ValueError, match="double"):
        load_registry(path)
