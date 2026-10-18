"""Chargement d'un scénario YAML : validation pydantic, erreurs en français avec la ligne.

Une erreur nomme le champ (`setup[1].message`) et sa ligne dans le fichier, pour que
l'auteur du scénario la corrige sans lire de trace Python.
"""

from __future__ import annotations

import hashlib
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from wavedevsecops.config import Settings, get_settings
from wavedevsecops.contracts import AppError
from wavedevsecops.registry import load_registry
from wavedevsecops.scenarios.model import Scenario
from wavedevsecops.wsfs import to_lf

MAX_REPORTED = 8


@dataclass(frozen=True)
class FieldError:
    """Un écart : champ (`setup[1].path`), ligne (1 = première), message en français."""

    field: str
    line: int | None
    message: str

    def text(self) -> str:
        where = f"ligne {self.line}, " if self.line else ""
        return f"{where}champ {self.field} : {self.message}"


class ScenarioError(AppError):
    """Scénario invalide : chaque écart nomme son champ et sa ligne."""

    def __init__(self, source: str, errors: list[FieldError]) -> None:
        shown = "\n".join(f"- {e.text()}" for e in errors[:MAX_REPORTED])
        more = len(errors) - MAX_REPORTED
        if more > 0:
            shown += f"\n- … et {more} autre(s) écart(s)"
        super().__init__(
            f"Le scénario « {source} » est invalide :\n{shown}",
            "Corrigez le fichier YAML du scénario, puis rechargez-le.",
        )
        self.source = source
        self.errors = errors


@dataclass(frozen=True)
class LoadedScenario:
    """Scénario validé, son fichier et l'empreinte de son contenu (`content_hash`)."""

    scenario: Scenario
    path: Path
    content_hash: str


def content_hash(text: str) -> str:
    """sha256 du texte en LF : identique quel que soit le `core.autocrlf` du clone."""
    return hashlib.sha256(to_lf(text).encode("utf-8")).hexdigest()


def _record_lines(
    node: yaml.Node, path: tuple, lines: dict[tuple, int], duplicates: list[FieldError]
) -> None:
    lines.setdefault(path, node.start_mark.line + 1)
    if isinstance(node, yaml.MappingNode):
        seen: set[str] = set()
        for key_node, value_node in node.value:
            key = key_node.value if isinstance(key_node, yaml.ScalarNode) else None
            if key is None:
                continue
            if key in seen:  # PyYAML garderait la dernière valeur sans rien dire
                duplicates.append(
                    FieldError(_label([*path, key]), key_node.start_mark.line + 1, "clé en double")
                )
            seen.add(key)
            lines.setdefault((*path, key), key_node.start_mark.line + 1)
            _record_lines(value_node, (*path, key), lines, duplicates)
    elif isinstance(node, yaml.SequenceNode):
        for index, item in enumerate(node.value):
            _record_lines(item, (*path, index), lines, duplicates)


def _parse(text: str, source: str) -> tuple[Any, dict[tuple, int]]:
    loader = yaml.SafeLoader(text)
    try:
        node = loader.get_single_node()
        data = loader.construct_document(node) if node is not None else None
    except yaml.MarkedYAMLError as exc:
        mark = exc.problem_mark or exc.context_mark
        line = mark.line + 1 if mark else None
        problem = exc.problem or "syntaxe invalide"
        raise ScenarioError(
            source, [FieldError("(document)", line, f"YAML illisible ({problem})")]
        ) from None
    except yaml.YAMLError as exc:
        raise ScenarioError(
            source, [FieldError("(document)", None, f"YAML illisible ({exc})")]
        ) from None
    finally:
        loader.dispose()
    lines: dict[tuple, int] = {}
    duplicates: list[FieldError] = []
    if node is not None:
        _record_lines(node, (), lines, duplicates)
    if duplicates:
        raise ScenarioError(source, duplicates)
    return data, lines


def _label(parts: list[Any]) -> str:
    label = ""
    for part in parts:
        label += f"[{part}]" if isinstance(part, int) else (f".{part}" if label else str(part))
    return label or "(racine)"


def locate(
    loc: Iterable[Any], data: Any, lines: dict[tuple, int], *, missing: bool = False
) -> tuple[str, int | None]:
    """Champ et ligne d'une erreur pydantic, à partir de son `loc`.

    Les éléments du `loc` absents des données (étiquette d'une union discriminée) sont
    sautés ; pour un champ manquant (`missing`), le dernier élément absent est nommé et
    situé à la ligne du parent.
    """
    parts = list(loc)
    consumed: list[Any] = []
    current = data
    line = lines.get(())
    for index, part in enumerate(parts):
        if isinstance(current, dict) and part in current:
            current = current[part]
        elif isinstance(current, list) and isinstance(part, int) and 0 <= part < len(current):
            current = current[part]
        elif missing and index == len(parts) - 1:
            consumed.append(part)
            break
        else:
            continue
        consumed.append(part)
        line = lines.get(tuple(consumed), line)
    return _label(consumed), line


def _is_step_type(loc: Iterable[Any]) -> bool:
    parts = list(loc)
    return parts[:1] == ["steps"] and parts[-1:] == ["type"]


def french_message(error: dict[str, Any]) -> str:
    """Message en français d'une erreur pydantic."""
    kind = error.get("type", "")
    ctx = error.get("ctx") or {}
    messages = {
        "missing": "champ obligatoire absent",
        "extra_forbidden": "champ inconnu",
        "string_type": "texte attendu",
        "int_type": "nombre entier attendu",
        "int_parsing": "nombre entier attendu",
        "bool_type": "booléen attendu (true ou false)",
        "bool_parsing": "booléen attendu (true ou false)",
        "list_type": "liste attendue",
        "dict_type": "table (clé: valeur) attendue",
        "model_type": "table (clé: valeur) attendue",
        "model_attributes_type": "table (clé: valeur) attendue",
        "union_tag_not_found": "champ `op` absent",
        "timezone_aware": "date ISO 8601 avec fuseau attendue",
        "datetime_type": "date ISO 8601 avec fuseau attendue",
        "datetime_parsing": "date ISO 8601 avec fuseau attendue",
        "datetime_from_date_parsing": "date ISO 8601 avec fuseau attendue",
        "greater_than_equal": f"valeur trop petite (minimum {ctx.get('ge')})",
    }
    if kind == "union_tag_not_found" and list(error.get("loc", ())[:1]) == ["steps"]:
        return "champ `type` absent"
    if kind in messages:
        return messages[kind]
    if kind == "literal_error" and _is_step_type(error.get("loc", ())):
        return f"type d'étape inconnu (types connus : {ctx.get('expected')})"
    if kind == "literal_error":
        return f"valeur non admise (attendu : {ctx.get('expected')})"
    if kind == "union_tag_invalid":
        if list(error.get("loc", ())[:1]) == ["steps"]:
            return (
                f"type d'étape inconnu « {ctx.get('tag')} » "
                f"(types connus : {ctx.get('expected_tags')})"
            )
        return f"op inconnue « {ctx.get('tag')} » (ops connues : {ctx.get('expected_tags')})"
    if kind == "string_pattern_mismatch":
        return "format invalide (kebab-case ou snake_case selon le champ)"
    if kind in {"too_short", "string_too_short"}:
        return "valeur vide ou liste trop courte"
    if kind == "value_error":
        return str(ctx.get("error", error.get("msg", "valeur invalide")))
    return f"valeur invalide ({error.get('msg', kind)})"


def parse_scenario(
    text: str,
    source: str,
    *,
    tool_ids: Iterable[str] | None = None,
    expected_key: str | None = None,
    explain_keys: Iterable[str] | None = None,
) -> Scenario:
    """Valide le texte d'un scénario ; `ScenarioError` avec champs et lignes sinon."""
    data, lines = _parse(text, source)
    if not isinstance(data, dict):
        raise ScenarioError(source, [FieldError("(racine)", 1, "table (clé: valeur) attendue")])
    try:
        scenario = Scenario.model_validate(data)
    except ValidationError as exc:
        errors = []
        for error in exc.errors():
            field, line = locate(error["loc"], data, lines, missing=error["type"] == "missing")
            errors.append(FieldError(field, line, french_message(dict(error))))
        raise ScenarioError(source, errors) from None
    found = []
    for loc, message in scenario.semantic_errors(
        None if tool_ids is None else set(tool_ids),
        None if explain_keys is None else set(explain_keys),
    ):
        field, line = locate(loc, data, lines)
        found.append(FieldError(field, line, message))
    if expected_key is not None and scenario.key != expected_key:
        found.append(
            FieldError(
                "scenario_id",
                lines.get(("scenario_id",)),
                f"le fichier doit s'appeler « {scenario.key}.yaml » "
                f"(scenario_id et mode), et non « {expected_key}.yaml »",
            )
        )
    if found:
        raise ScenarioError(source, found)
    return scenario


def load_scenario(
    path: Path, settings: Settings | None = None, *, explain_keys: Iterable[str] | None = None
) -> LoadedScenario:
    """Charge `content/scenarios/<scenario_id>.<mode>.yaml` ; outils vérifiés par le registre.

    `explain_keys` : clés du catalogue d'explications (lint de contenu) ; `None` : non vérifiées."""
    settings = settings or get_settings()
    text = path.read_bytes().decode("utf-8")
    tool_ids = {tool.id for tool in load_registry(settings=settings).tool}
    expected = path.name.removesuffix(".yaml")
    scenario = parse_scenario(
        text, path.name, tool_ids=tool_ids, expected_key=expected, explain_keys=explain_keys
    )
    return LoadedScenario(scenario, path, content_hash(text))


def scenario_files(settings: Settings | None = None) -> list[Path]:
    """Fichiers de `content/scenarios/`, triés."""
    folder = (settings or get_settings()).scenarios_path()
    return sorted(folder.glob("*.yaml")) if folder.is_dir() else []
