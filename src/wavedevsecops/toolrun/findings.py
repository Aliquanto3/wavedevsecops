"""Constats d'un outil tirés d'une exécution machine, jamais du texte humain (AD-10).

`ruff check --output-format json` donne les fichier:ligne exacts. pytest n'a pas de sortie
machine avec les lignes : `--junitxml` donne les fichiers des tests en échec (le nom de classe
est le chemin du module). Le terminal ne lie dans la sortie humaine que ce que ces constats
désignent.
"""

from __future__ import annotations

import json
import uuid
import xml.etree.ElementTree as ET  # noqa: S405 - fichier écrit par pytest dans cache/, pas du réseau
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path

from wavedevsecops import toolrun
from wavedevsecops.config import Settings

RUFF_HUMAN_ONLY = frozenset({"--fix", "--statistics", "--show-fixes", "--diff"})
"""Options de la sortie humaine ou d'écriture, retirées de l'exécution machine de ruff."""


@dataclass(frozen=True)
class Findings:
    """Fichiers (chemins posix relatifs au dépôt) désignés par l'outil."""

    lines: dict[str, frozenset[int]] = field(default_factory=dict)
    """Fichier -> lignes exactes (ruff) ; une ligne vide : tout numéro de ligne du fichier."""
    error: str = ""
    """Raison pour laquelle l'exécution machine n'a rien donné ; vide si elle a abouti."""

    def covers(self, path: str, line: int) -> bool:
        if path not in self.lines:
            return False
        exact = self.lines[path]
        return not exact or line in exact


def relative_posix(name: str, repo: Path) -> str | None:
    """Chemin posix relatif à `repo` d'un nom de fichier d'outil ; `None` s'il en sort."""
    path = Path(name)
    try:
        if path.is_absolute() or name.startswith("/"):
            path = path.resolve().relative_to(repo.resolve())
    except (OSError, ValueError):
        return None
    posix = path.as_posix()
    return None if posix.startswith("../") or posix in ("", ".") else posix.removeprefix("./")


def parse_ruff(stdout: str, repo: Path) -> Findings:
    """Constats du JSON de `ruff check --output-format json`."""
    try:
        data = json.loads(stdout or "[]")
    except ValueError:
        return Findings(error="la sortie machine de ruff est illisible")
    if not isinstance(data, list):
        return Findings(error="la sortie machine de ruff est inattendue")
    lines: dict[str, set[int]] = {}
    for item in data:
        try:
            path = relative_posix(item["filename"], repo)
            row = int(item["location"]["row"])
        except (KeyError, TypeError, ValueError):
            continue
        if path is not None:
            lines.setdefault(path, set()).add(row)
    return Findings({path: frozenset(rows) for path, rows in lines.items()})


def parse_junit(xml_text: str, repo: Path) -> Findings:
    """Fichiers des tests en échec ou en erreur d'un rapport JUnit de pytest."""
    try:
        root = ET.fromstring(xml_text)  # noqa: S314 - rapport écrit par notre propre pytest
    except ET.ParseError:
        return Findings(error="le rapport machine de pytest est illisible")
    files: dict[str, frozenset[int]] = {}
    for case in root.iter("testcase"):
        if case.find("failure") is None and case.find("error") is None:
            continue
        parts = (case.get("classname") or "").split(".")
        # `tests.test_a` ou `tests.test_a.TestClasse` : le plus long préfixe qui est un module.
        for end in range(len(parts), 0, -1):
            candidate = "/".join(parts[:end]) + ".py"
            if (repo / candidate).is_file():
                files[candidate] = frozenset()
                break
    return Findings(files)


def machine_ruff_args(args: Sequence[str]) -> list[str]:
    """Arguments de l'exécution machine : mêmes cibles, sans écriture, sortie JSON."""
    kept = [a for a in args if a not in RUFF_HUMAN_ONLY]
    return [*kept, "--output-format", "json", "--no-fix"]


def collect(
    tool_id: str,
    args: Sequence[str],
    *,
    repo: Path,
    venv: Path,
    cache: Path,
    settings: Settings,
    timeout: float,
) -> Findings:
    """Relance `tool_id` en mode machine sur le même arbre et en tire les constats."""
    if tool_id == "ruff":
        ran = toolrun.run_tool(
            "ruff", machine_ruff_args(args), cwd=repo, timeout=timeout, settings=settings, venv=venv
        )
        if ran.error or ran.timed_out or ran.returncode not in (0, 1):
            return Findings(error=ran.error or "ruff n'a pas donné de sortie machine")
        return parse_ruff(ran.stdout, repo)
    if tool_id == "pytest":
        report = cache / f"junit-{uuid.uuid4().hex[:8]}.xml"
        cache.mkdir(parents=True, exist_ok=True)
        extra = ["--junitxml", str(report), "--tb=no", "-q"]
        ran = toolrun.run_tool(
            "pytest", [*args, *extra], cwd=repo, timeout=timeout, settings=settings, venv=venv
        )
        try:
            if ran.error or ran.timed_out:
                return Findings(error=ran.error or "pytest n'a pas donné de rapport machine")
            try:
                return parse_junit(report.read_text("utf-8"), repo)
            except OSError:
                return Findings(error="pytest n'a pas écrit son rapport machine")
        finally:
            report.unlink(missing_ok=True)
    return Findings(error=f"pas de sortie machine connue pour {tool_id}")
