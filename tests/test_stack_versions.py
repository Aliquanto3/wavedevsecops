"""AD-16 : les versions épinglées concordent avec la table Stack du spine.

Story 1.1 : on compare la table Stack, `pyproject.toml` et `uv.lock`. Story 1.4 : le registre
`tools.toml` entre dans cette comparaison.
"""

from __future__ import annotations

import re
import tomllib
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
PIN = re.compile(r"(?P<name>[A-Za-z0-9][A-Za-z0-9._-]*)\s*==\s*(?P<version>[A-Za-z0-9.+!-]+)")
SPINE_GLOB = "_bmad-output/planning-artifacts/architecture/*/ARCHITECTURE-SPINE.md"

# Paquets Python de la table Stack qui doivent figurer, épinglés, dans `uv.lock`.
PYTHON_PACKAGES = frozenset(
    {
        "fastapi",
        "uvicorn",
        "pydantic",
        "jinja2",
        "pyyaml",
        "watchfiles",
        "platformdirs",
        "pywebview",
        "ruff",
        "pytest",
        "pytest-cov",
        "pytest-xdist",
        "coverage",
        "diff-cover",
        "bandit",
        "pip-audit",
        "pre-commit",
    }
)


def normalize(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def spine_path() -> Path:
    candidates = sorted(ROOT.glob(SPINE_GLOB))
    assert candidates, f"spine introuvable ({SPINE_GLOB})"
    return candidates[-1]


def parse_stack_table(markdown: str) -> dict[str, str]:
    """Lignes de la section `## Stack` : nom normalisé (avant toute parenthèse) -> version."""
    match = re.search(r"^## Stack\s*$(.*?)(?=^## |\Z)", markdown, re.MULTILINE | re.DOTALL)
    assert match, "section « ## Stack » absente du spine"
    table: dict[str, str] = {}
    for line in match.group(1).splitlines():
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if len(cells) != 2 or cells[0] in {"Name", ""} or set(cells[0]) <= {"-", " "}:
            continue
        name = normalize(cells[0].split("(")[0].strip())
        table[name] = cells[1]
    return table


def parse_lock(text: str) -> dict[str, set[str]]:
    versions: dict[str, set[str]] = {}
    for package in tomllib.loads(text).get("package", []):
        if "version" in package:
            versions.setdefault(normalize(package["name"]), set()).add(package["version"])
    return versions


def stack_mismatches(stack: dict[str, str], lock: dict[str, set[str]]) -> list[str]:
    problems = []
    for name in sorted(PYTHON_PACKAGES):
        expected = stack.get(name)
        if expected is None:
            problems.append(f"{name} absent de la table Stack")
        elif name not in lock:
            problems.append(f"{name} absent de uv.lock")
        elif lock[name] != {expected}:
            problems.append(f"{name} : uv.lock {sorted(lock[name])} != Stack {expected}")
    return problems


def pyproject_pins() -> dict[str, str]:
    data = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    requirements = list(data["project"]["dependencies"])
    for extra in data["project"].get("optional-dependencies", {}).values():
        requirements += extra
    for group in data.get("dependency-groups", {}).values():
        requirements += [r for r in group if isinstance(r, str)]
    pins: dict[str, str] = {}
    for raw in requirements:
        match = PIN.fullmatch(raw.strip())
        assert match, f"{raw} n'est pas épinglé par =="
        pins[normalize(match["name"])] = match["version"]
    return pins


@pytest.fixture(scope="module")
def stack() -> dict[str, str]:
    return parse_stack_table(spine_path().read_text(encoding="utf-8"))


def test_uv_lock_conforme_a_la_table_stack(stack: dict[str, str]) -> None:
    lock = parse_lock((ROOT / "uv.lock").read_text(encoding="utf-8"))
    assert stack_mismatches(stack, lock) == []


def test_pyproject_conforme_a_la_table_stack(stack: dict[str, str]) -> None:
    pins = pyproject_pins()
    assert set(pins) == PYTHON_PACKAGES
    assert {name: stack[name] for name in pins} == pins


def test_python_3_14(stack: dict[str, str]) -> None:
    assert stack["python"] == "3.14.x"
    data = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    assert data["project"]["requires-python"] == ">=3.14,<3.15"
    assert (ROOT / ".python-version").read_text(encoding="utf-8").strip() == "3.14"


def test_ecart_de_version_detecte() -> None:
    stack = {name: "1.0.0" for name in PYTHON_PACKAGES}
    lock = {name: {"1.0.0"} for name in PYTHON_PACKAGES}
    assert stack_mismatches(stack, lock) == []
    lock["fastapi"] = {"1.0.1"}
    del lock["ruff"]
    del stack["bandit"]
    problems = stack_mismatches(stack, lock)
    assert len(problems) == 3
    assert any(p.startswith("fastapi : uv.lock") for p in problems)


def test_lecture_de_la_table() -> None:
    markdown = (
        "## Stack\n\n| Name | Version |\n| --- | --- |\n"
        "| pywebview (extra facultatif `window`) | 6.2.1 |\n| PyYAML | 6.0.3 |\n"
        "\n## Suite\n| a | b |\n"
    )
    assert parse_stack_table(markdown) == {"pywebview": "6.2.1", "pyyaml": "6.0.3"}


# --- Story 1.4 : le registre `tools.toml` (AD-16) concorde avec la table Stack et `uv.lock` ---

CHAIN_TOOLS = frozenset(
    {"ruff", "pytest", "pytest-cov", "coverage", "diff-cover", "bandit", "pip-audit", "pre-commit"}
)
MINIMUMS = {"git": "2.38", "uv": "0.11.0", "gitleaks": "8.20.0"}  # tableau d'AD-16


def registry_mismatches(
    registry: dict[str, dict], stack: dict[str, str], lock: dict[str, set[str]]
) -> list[str]:
    """Écarts entre `tools.toml`, la table Stack et `uv.lock`."""
    problems = []
    expected = {
        ("git", "windows"): stack.get("git for windows"),
        ("git", "posix"): stack.get("git"),
        ("gitleaks", None): stack.get("gitleaks"),
        ("pixi", None): stack.get("pixi"),
        ("uv", None): (stack.get("uv") or "").split("(vérifié :")[-1].strip(" )"),
    }
    for name in sorted(CHAIN_TOOLS):
        entry = registry.get(name)
        if entry is None:
            problems.append(f"{name} absent de tools.toml")
            continue
        version = entry["provisioned_version"]
        if lock.get(name) != {version} or stack.get(name) != version:
            problems.append(f"{name} : tools.toml {version} != Stack/uv.lock")
    for (name, family), version in expected.items():
        entry = registry.get(name)
        if entry is None:
            problems.append(f"{name} absent de tools.toml")
            continue
        provisioned = entry["provisioned_version"]
        value = provisioned[family] if isinstance(provisioned, dict) else provisioned
        if value != version:
            problems.append(f"{name} ({family or 'tous'}) : tools.toml {value} != Stack {version}")
    for name, minimum in MINIMUMS.items():
        entry = registry.get(name)
        if entry is None or entry.get("min_version") != minimum:
            problems.append(f"{name} : version minimale != {minimum}")
        elif name == "uv" and f"≥ {minimum}" not in stack.get("uv", ""):
            problems.append(f"uv : la table Stack ne dit pas ≥ {minimum}")
    for name in sorted(set(registry) - CHAIN_TOOLS - set(MINIMUMS) - {"pixi"}):
        problems.append(f"{name} : outil du registre sans contrôle de cohérence")
    return problems


def load_registry_dict() -> dict[str, dict]:
    data = tomllib.loads((ROOT / "tools.toml").read_text(encoding="utf-8"))
    return {entry["id"]: entry for entry in data["tool"]}


def test_tools_toml_conforme_a_la_table_stack_et_a_uv_lock(stack: dict[str, str]) -> None:
    lock = parse_lock((ROOT / "uv.lock").read_text(encoding="utf-8"))
    assert registry_mismatches(load_registry_dict(), stack, lock) == []


def test_outils_de_chaine_de_tools_toml_egaux_au_groupe_chain() -> None:
    data = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    chain = {normalize(PIN.fullmatch(r)["name"]) for r in data["dependency-groups"]["chain"]}
    uv_lock_tools = {n for n, e in load_registry_dict().items() if e["resolution"] == "uv-lock"}
    assert chain == uv_lock_tools == CHAIN_TOOLS


def test_ecart_du_registre_detecte(stack: dict[str, str]) -> None:
    lock = parse_lock((ROOT / "uv.lock").read_text(encoding="utf-8"))
    registry = load_registry_dict()
    registry["ruff"] = registry["ruff"] | {"provisioned_version": "0.0.1"}
    registry["gitleaks"] = registry["gitleaks"] | {"min_version": "8.0.0"}
    del registry["bandit"]
    assert len(registry_mismatches(registry, stack, lock)) == 3
