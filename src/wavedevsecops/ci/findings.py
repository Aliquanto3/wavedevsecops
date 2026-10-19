"""Constats des checks tirés des sorties machine des outils, jamais du texte humain (AD-10).

Un lecteur par format (`ci.Parse`) : il reçoit le texte de la sortie machine (stdout, ou le
fichier `{report}` s'il existe) et l'arbre testé, et rend des `Finding` (règle, gravité,
message, fichier posix relatif à l'arbre, ligne). Un texte illisible lève `ValueError`.
"""

from __future__ import annotations

import json
import xml.etree.ElementTree as ET  # noqa: S405 - rapport écrit par pytest dans ci/, pas du réseau
from collections.abc import Callable
from pathlib import Path
from typing import Any

from wavedevsecops.contracts.github import Finding
from wavedevsecops.toolrun.findings import relative_posix

MESSAGE_MAX = 500


def _line(value: Any) -> int | None:
    try:
        line = int(value)
    except TypeError, ValueError:
        return None
    return line if line >= 1 else None


def _short(text: Any) -> str:
    return str(text or "").strip()[:MESSAGE_MAX]


def _json_list(text: str, what: str) -> list[Any]:
    try:
        data = json.loads(text or "[]")
    except ValueError:
        raise ValueError(f"la sortie machine de {what} est illisible") from None
    if data is None:
        return []
    if not isinstance(data, list):
        raise ValueError(f"la sortie machine de {what} est inattendue")
    return data


def parse_ruff_json(text: str, tree: Path) -> list[Finding]:
    """`ruff check --output-format json` : un constat par violation."""
    found = []
    for item in _json_list(text, "ruff"):
        if not isinstance(item, dict):
            continue
        location = item.get("location") if isinstance(item.get("location"), dict) else {}
        found.append(
            Finding(
                rule_id=_short(item.get("code")),
                severity="error",
                message_text=_short(item.get("message")),
                path=relative_posix(str(item.get("filename") or ""), tree),
                line=_line(location.get("row")),
            )
        )
    return found


def parse_junit(text: str, tree: Path) -> list[Finding]:
    """Rapport `--junitxml` de pytest : un constat par test en échec ou en erreur, sur le
    fichier du test (le nom de classe est le chemin du module)."""
    try:
        root = ET.fromstring(text)  # noqa: S314 - rapport écrit par le pytest du run
    except ET.ParseError:
        raise ValueError("le rapport machine de pytest est illisible") from None
    found = []
    for case in root.iter("testcase"):
        problem = case.find("failure")
        if problem is None:
            problem = case.find("error")
        if problem is None:
            continue
        parts = (case.get("classname") or "").split(".")
        path = None
        # `tests.test_a` ou `tests.test_a.TestClasse` : le plus long préfixe qui est un module.
        for end in range(len(parts), 0, -1):
            candidate = "/".join(parts[:end]) + ".py"
            if (tree / candidate).is_file():
                path = candidate
                break
        found.append(
            Finding(
                rule_id=_short(case.get("name")),
                severity="failure" if problem.tag == "failure" else "error",
                message_text=_short(problem.get("message")),
                path=path,
            )
        )
    return found


def parse_gitleaks_json(text: str, tree: Path) -> list[Finding]:
    """`gitleaks --report-format json` : un constat par secret (valeur masquée par `--redact`)."""
    found = []
    for item in _json_list(text, "gitleaks"):
        if not isinstance(item, dict):
            continue
        found.append(
            Finding(
                rule_id=_short(item.get("RuleID")),
                severity="error",
                message_text=_short(item.get("Description")),
                path=relative_posix(str(item.get("File") or ""), tree),
                line=_line(item.get("StartLine")),
            )
        )
    return found


def parse_bandit_json(text: str, tree: Path) -> list[Finding]:
    """`bandit -f json` : un constat par résultat (règle `test_id`, fichier, ligne)."""
    try:
        data = json.loads(text or "{}")
    except ValueError:
        raise ValueError("la sortie machine de bandit est illisible") from None
    if not isinstance(data, dict) or not isinstance(data.get("results", []), list):
        raise ValueError("la sortie machine de bandit est inattendue")
    found = []
    for item in data.get("results", []):
        if not isinstance(item, dict):
            continue
        found.append(
            Finding(
                rule_id=_short(item.get("test_id")),
                severity="error",
                message_text=_short(item.get("issue_text")),
                path=relative_posix(str(item.get("filename") or ""), tree),
                line=_line(item.get("line_number")),
            )
        )
    return found


PARSERS: dict[str, Callable[[str, Path], list[Finding]]] = {
    "ruff_json": parse_ruff_json,
    "junit": parse_junit,
    "gitleaks_json": parse_gitleaks_json,
    "bandit_json": parse_bandit_json,
}
"""Lecteur de chaque valeur de `parse` ; une valeur de `ci.Parse` sans lecteur est refusée."""
