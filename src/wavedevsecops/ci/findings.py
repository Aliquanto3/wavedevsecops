"""Constats des checks tirés des sorties machine des outils, jamais du texte humain (AD-10).

Un lecteur par format (`ci.Parse`) : il reçoit le texte de la sortie machine (stdout, ou le
fichier `{report}` s'il existe) et l'arbre testé, et rend des `Finding` (règle, gravité,
message, fichier posix relatif à l'arbre, ligne). Un texte illisible lève `ValueError`.
"""

from __future__ import annotations

import json
import re
import xml.etree.ElementTree as ET  # noqa: S405 - rapport écrit par pytest dans ci/, pas du réseau
from collections.abc import Callable
from pathlib import Path
from typing import Any

from wavedevsecops.config import get_settings
from wavedevsecops.contracts.github import Finding, SbomComponent, SbomVuln
from wavedevsecops.toolrun.findings import relative_posix

MESSAGE_MAX = 500

UNSCANNED_RULE = "unscanned_file"
"""Constat d'un fichier que l'outil n'a pas pu analyser (syntaxe illisible) : un check vert
ne prouverait rien sur ce fichier, `ci.run_job` tient donc le check pour un échec."""


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
    # `errors` : fichiers que bandit n'a pas pu lire (syntaxe), qu'il saute en sortant 0.
    for item in data.get("errors") or []:
        if not isinstance(item, dict):
            continue
        path = relative_posix(str(item.get("filename") or ""), tree)
        reason = _short(item.get("reason")) or "fichier illisible"
        found.append(
            Finding(
                rule_id=UNSCANNED_RULE,
                severity="error",
                message_text=_short(
                    f"bandit n'a pas pu analyser ce fichier ({reason}) : un fichier non analysé "
                    "ne prouve pas que le code est sûr. Corrigez sa syntaxe."
                ),
                path=path,
            )
        )
    return found


REQUIREMENTS_FILE = "requirements.txt"
"""Fichier d'exigences épinglées que lit pip-audit (`-r`, AD-11) : le constat et le SBOM s'y
rattachent (ligne de la dépendance)."""
_REQUIREMENT = re.compile(r"\s*([A-Za-z0-9][A-Za-z0-9._-]*)\s*(?:\[[^\]]*\])?\s*==")


def _pkg(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def _requirement_lines(tree: Path) -> dict[str, int]:
    """Ligne (à partir de 1) de chaque dépendance épinglée du fichier d'exigences, par nom."""
    try:
        text = (tree / REQUIREMENTS_FILE).read_text(encoding="utf-8")
    except OSError, UnicodeDecodeError:
        return {}
    found: dict[str, int] = {}
    for number, line in enumerate(text.splitlines(), start=1):
        match = _REQUIREMENT.match(line)
        if match:
            found.setdefault(_pkg(match[1]), number)
    return found


def osv_date() -> str:
    """Date de l'extrait OSV embarqué (`content/osv/index.json`), citée par les constats."""
    try:
        meta = json.loads((get_settings().osv_path() / "index.json").read_text("utf-8"))
        return str(meta.get("extracted_on") or "")
    except OSError, UnicodeDecodeError, ValueError, AttributeError:
        return ""


def _json_dict(text: str, what: str) -> dict[str, Any]:
    """JSON objet ; un texte vide est illisible (pip-audit n'écrit rien quand le fichier
    d'exigences est absent ou invalide : l'échec garde alors sa sortie humaine)."""
    try:
        data = json.loads(text)
    except ValueError:
        raise ValueError(f"la sortie machine de {what} est illisible") from None
    if not isinstance(data, dict):
        raise ValueError(f"la sortie machine de {what} est inattendue")
    return data


def parse_pip_audit_json(text: str, tree: Path) -> list[Finding]:
    """`pip-audit -f json` : un constat par couple (dépendance, vulnérabilité), sur la ligne
    du fichier d'exigences. Une dépendance que pip-audit n'a pas pu auditer (`skip_reason`)
    est un constat `unscanned_file` : un vert ne prouverait rien sur elle."""
    data = _json_dict(text, "pip-audit")
    deps = data.get("dependencies", [])
    if not isinstance(deps, list):
        raise ValueError("la sortie machine de pip-audit est inattendue")
    lines = _requirement_lines(tree)
    date = osv_date()
    base = f" Base embarquée, figée au {date}." if date else " Base embarquée et figée."
    path = REQUIREMENTS_FILE if (tree / REQUIREMENTS_FILE).is_file() else None
    found = []
    for dep in deps:
        if not isinstance(dep, dict):
            continue
        name = str(dep.get("name") or "")
        label = f"{name} {dep.get('version') or ''}".strip()
        line = lines.get(_pkg(name))
        if dep.get("skip_reason"):
            found.append(
                Finding(
                    rule_id=UNSCANNED_RULE,
                    severity="error",
                    message_text=_short(
                        f"pip-audit n'a pas pu auditer {label} ({dep.get('skip_reason')}) : "
                        "une dépendance non auditée ne prouve pas qu'elle est sûre."
                    ),
                    path=path,
                    line=line,
                )
            )
            continue
        seen: set[str] = set()
        for vuln in dep.get("vulns") or []:
            vuln_id = str(vuln.get("id") or "") if isinstance(vuln, dict) else ""
            if not vuln_id or vuln_id in seen:
                continue
            seen.add(vuln_id)
            fixes = [str(v) for v in vuln.get("fix_versions") or []]
            aliases = [str(a) for a in vuln.get("aliases") or []]
            message = f"{label} est vulnérable"
            if aliases:
                message += f" ({', '.join(aliases)})"
            description = str(vuln.get("description") or "").strip()
            message += f" : {description}." if description else "."
            if fixes:
                message += f" Corrigée dans la version {' ou '.join(fixes)}."
            found.append(
                Finding(
                    rule_id=vuln_id,
                    severity="error",
                    message_text=_short(message + base),
                    path=path,
                    line=line,
                )
            )
    return found


_REQUIREMENT_NAME = re.compile(r"\s*([A-Za-z0-9][A-Za-z0-9._-]*)")


def _required_names(tree: Path) -> dict[str, int]:
    """Nom et ligne de chaque exigence du fichier (épinglée ou non, avec ou sans marqueur)."""
    try:
        text = (tree / REQUIREMENTS_FILE).read_text(encoding="utf-8")
    except OSError, UnicodeDecodeError:
        return {}
    found: dict[str, int] = {}
    for number, line in enumerate(text.splitlines(), start=1):
        match = _REQUIREMENT_NAME.match(line.split("#", 1)[0])
        if match:
            found.setdefault(_pkg(match[1]), number)
    return found


def parse_cyclonedx_json(text: str, tree: Path) -> list[SbomComponent | Finding]:
    """`pip-audit -f cyclonedx-json` : un composant par dépendance (nom, version, licences si
    le document en porte, vulnérabilités rattachées par `affects`). Le SBOM ne juge rien, sauf
    une exigence du fichier absente du SBOM (marqueur d'environnement faux sur le runner,
    que pip-audit saute sans le dire) : constat `unscanned_file`, un vert ne prouverait rien."""
    data = _json_dict(text, "pip-audit (SBOM)")
    components = data.get("components", [])
    vulns = data.get("vulnerabilities", [])
    if not isinstance(components, list) or not isinstance(vulns, list):
        raise ValueError("le SBOM de pip-audit est inattendu")
    lines = _requirement_lines(tree)
    by_ref: dict[str, list[SbomVuln]] = {}
    for item in vulns:
        if not isinstance(item, dict) or not item.get("id"):
            continue
        entry = SbomVuln(vuln_id=_short(item["id"]))
        for affect in item.get("affects") or []:
            ref = str(affect.get("ref") or "") if isinstance(affect, dict) else ""
            bucket = by_ref.setdefault(ref, [])
            if ref and all(v.vuln_id != entry.vuln_id for v in bucket):
                bucket.append(entry)
    found = []
    for item in components:
        if not isinstance(item, dict) or not item.get("name"):
            continue
        licenses = []
        for lic in item.get("licenses") or []:
            if not isinstance(lic, dict):
                continue
            body = lic.get("license") if isinstance(lic.get("license"), dict) else {}
            label = body.get("id") or body.get("name") or lic.get("expression")
            if label:
                licenses.append(_short(label))
        name = _short(item["name"])
        found.append(
            SbomComponent(
                name=name,
                version=_short(item.get("version")),
                licenses=licenses,
                vulns=by_ref.get(str(item.get("bom-ref") or ""), []),
                line=lines.get(_pkg(name)),
            )
        )
    listed = {_pkg(c.name) for c in found}
    for name, line in _required_names(tree).items():
        if name not in listed:
            found.append(
                Finding(
                    rule_id=UNSCANNED_RULE,
                    severity="error",
                    message_text=_short(
                        f"pip-audit n'a pas audité l'exigence {name} (ligne {line}), absente du "
                        "SBOM : un marqueur d'environnement l'écarte peut-être sur ce runner. Une "
                        "dépendance non auditée ne prouve pas qu'elle est sûre."
                    ),
                    path=REQUIREMENTS_FILE,
                    line=line,
                )
            )
    return found


QUALITY_GATE_THRESHOLD = 80
"""Seuil de couverture du nouveau code, en %. Le même chiffre que `--fail-under` du job
`quality_gate` de `content/pipeline.yaml` (un test les rapproche) : le lecteur l'affiche."""
DIFF_COVERAGE_RULE = "diff_coverage"
NO_DIFF_RULE = "diff_coverage_none"
"""Constat quand le diff n'a aucune ligne mesurée : le vert ne prouve rien sur du code testé."""
UNCOVERED_RULE = "uncovered_lines"
TOTAL_COVERAGE_RULE = "total_coverage"


def _ranges(lines: list[int]) -> str:
    """`[59, 60, 61, 65]` -> « 59-61, 65 »."""
    found: list[str] = []
    start = previous = None
    for line in sorted(set(lines)):
        if start is None:
            start = previous = line
        elif line == previous + 1:
            previous = line
        else:
            found.append(str(start) if start == previous else f"{start}-{previous}")
            start = previous = line
    if start is not None:
        found.append(str(start) if start == previous else f"{start}-{previous}")
    return ", ".join(found)


def diff_coverage_text(percent: int | None, passed: bool) -> str:
    """« Couverture du nouveau code n % · seuil 80 % · ✓ » : la ligne que le check affiche.
    `percent` vide : aucune ligne mesurée dans le diff (rien à tester, donc rien de non testé)."""
    mark = "✓" if passed else "✗"
    value = "aucune ligne à mesurer" if percent is None else f"{percent} %"
    return f"Couverture du nouveau code {value} · seuil {QUALITY_GATE_THRESHOLD} % · {mark}"


def parse_diff_cover_json(text: str, tree: Path) -> list[Finding]:
    """`diff-cover --format json:` : la valeur et le seuil (un constat `diff_coverage`, ✓ ou ✗),
    puis un constat par fichier dont des lignes nouvelles ne sont couvertes par aucun test. Le
    pourcentage est celui de diff-cover (entier, arrondi vers le bas) : celui du seuil."""
    data = _json_dict(text, "diff-cover")
    total = data.get("total_num_lines")
    percent = data.get("total_percent_covered")
    stats = data.get("src_stats")
    if not isinstance(total, int) or not isinstance(stats, dict):
        raise ValueError("la sortie machine de diff-cover est inattendue")
    measured = total > 0
    if measured and not isinstance(percent, int | float):
        raise ValueError("la sortie machine de diff-cover est inattendue")
    value = int(percent) if measured else None
    passed = value is None or value >= QUALITY_GATE_THRESHOLD
    found = [
        Finding(
            rule_id=DIFF_COVERAGE_RULE if measured else NO_DIFF_RULE,
            severity="info" if passed else "error",
            message_text=diff_coverage_text(value, passed),
        )
    ]
    for name, item in stats.items():
        if not isinstance(item, dict):
            continue
        missing = [n for n in item.get("violation_lines") or [] if isinstance(n, int)]
        if not missing:
            continue
        path = relative_posix(str(name).replace("\\", "/"), tree)
        count = len(missing)
        noun = "ligne" if count == 1 else "lignes"
        found.append(
            Finding(
                rule_id=UNCOVERED_RULE,
                severity="error" if not passed else "info",
                message_text=(f"{count} {noun} du nouveau code sans test : {_ranges(missing)}"),
                path=path,
                line=_line(min(missing)),
            )
        )
    return found


def parse_coverage_json(text: str, tree: Path) -> list[Finding]:
    """`coverage json` : la couverture de tout le dépôt testé (information : le seuil ne porte
    que sur le nouveau code). Aucun fichier mesuré : la mesure n'a pas eu lieu, illisible."""
    data = _json_dict(text, "coverage")
    totals = data.get("totals")
    files = data.get("files")
    if not isinstance(totals, dict) or not isinstance(files, dict) or not files:
        raise ValueError("la mesure de couverture est vide ou inattendue")
    try:
        percent = int(float(totals["percent_covered"]))
    except KeyError, TypeError, ValueError:
        raise ValueError("la mesure de couverture est inattendue") from None
    return [
        Finding(
            rule_id=TOTAL_COVERAGE_RULE,
            severity="info",
            message_text=f"Couverture de l'ensemble du dépôt : {percent} % (information).",
        )
    ]


LOCK_MISMATCH_RULE = "lock_mismatch"
LOCK_FILE = "uv.lock"


def parse_uv_lock_check(text: str, tree: Path) -> list[Finding]:  # noqa: ARG001
    """`uv lock --check` en échec : un constat en français. uv n'a pas de sortie machine ; sa
    sortie brute (« No solution found… network was disabled » hors ligne) reste affichée sous
    le constat, verbatim. Ne tourne que sur un échec (`when: failure`)."""
    return [
        Finding(
            rule_id=LOCK_MISMATCH_RULE,
            severity="error",
            message_text=(
                "Le verrou uv.lock ne correspond plus à pyproject.toml : mettez-les en accord "
                "(la sortie de uv, ci-dessous, nomme la dépendance en cause)."
            ),
            path=LOCK_FILE,
        )
    ]


PARSERS: dict[str, Callable[[str, Path], list[Any]]] = {
    "ruff_json": parse_ruff_json,
    "junit": parse_junit,
    "gitleaks_json": parse_gitleaks_json,
    "bandit_json": parse_bandit_json,
    "pip_audit_json": parse_pip_audit_json,
    "cyclonedx_json": parse_cyclonedx_json,
    "coverage_json": parse_coverage_json,
    "diff_cover_json": parse_diff_cover_json,
    "uv_lock_check": parse_uv_lock_check,
}
"""Lecteur de chaque valeur de `parse` ; une valeur de `ci.Parse` sans lecteur est refusée.
Un lecteur rend des `Finding`, sauf `cyclonedx_json` : des `SbomComponent` (le SBOM)."""
