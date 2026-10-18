"""Grammaire `element_id` d'AD-2 : chaque forme, aller-retour exact, refus des formes fausses."""

from __future__ import annotations

import pytest

from wavedevsecops.contracts import ELEMENT_FORMS, ELEMENT_KINDS, element_id, parse_element_id

SHA = "0123456789abcdef0123456789abcdef01234567"
ODD = "a:b%c d/é✓ 𝄞"
"""`:`, `%`, espace, `/`, Unicode (dont un caractère hors du plan de base)."""

FORMS: list[tuple[str, tuple[str, ...]]] = [
    ("commit", (SHA,)),
    ("ref", ("refs/heads/" + ODD,)),
    ("ref", ("HEAD",)),
    ("path", ("head", ODD)),
    ("path", ("index", "src/" + ODD + ".py")),
    ("path", ("worktree", ODD)),
    ("diffline", (SHA, ODD, "old", "12")),
    ("diffline", ("index", ODD, "new", "0")),
    ("diffline", ("worktree", ODD, "new", "3")),
    ("pr", ("1",)),
    ("check", ("2", "unit_tests", SHA)),
    ("review", ("2", "1")),
    ("sbom", ("@scope/paquet:é@1.0.0",)),
    ("tag", ("v1.0 " + ODD,)),
    ("output", ("op:" + ODD,)),
    ("outline", ("op1", "42")),
    ("barrier", (ODD,)),
    ("env", ("staging",)),
    ("env", ("prod",)),
]


def test_toutes_les_formes_d_ad2_sont_couvertes() -> None:
    assert {kind for kind, _ in FORMS} == ELEMENT_KINDS == set(ELEMENT_FORMS)


@pytest.mark.parametrize(("kind", "segments"), FORMS)
def test_aller_retour_exact(kind: str, segments: tuple[str, ...]) -> None:
    value = element_id(kind, *segments)
    assert parse_element_id(value) == (kind, list(segments))
    # Les séparateurs et caractères spéciaux sont encodés : un seul `:` par segment.
    assert value.count(":") == len(segments)
    assert " " not in value and value.isascii()


@pytest.mark.parametrize(
    ("kind", "segments"),
    [
        ("commit", ("abc1234",)),
        ("commit", (SHA.upper(),)),
        ("path", ("disque", "a.py")),
        ("path", ("worktree",)),
        ("path", ("worktree", "")),
        ("diffline", (SHA, "a.py", "milieu", "1")),
        ("diffline", (SHA, "a.py", "old", "-1")),
        ("pr", ("0",)),
        ("check", ("1", "job", "abc")),
        ("env", ("dev",)),
        ("inconnu", ("x",)),
    ],
)
def test_formes_invalides_refusees(kind: str, segments: tuple[str, ...]) -> None:
    with pytest.raises(ValueError):
        element_id(kind, *segments)


@pytest.mark.parametrize(
    "value",
    [
        "commit",
        "commit:",
        "inconnu:x",
        f"commit:{SHA}:x",
        "path:worktree:a%3ab",  # encodage non canonique (minuscules)
        "path:worktree:a%7Eb",  # `~` encodé sans nécessité
        "path:worktree:%FF",  # UTF-8 invalide
        "ref:refs/heads/a b",  # espace non encodé
    ],
)
def test_analyse_refuse_les_formes_non_canoniques(value: str) -> None:
    with pytest.raises(ValueError):
        parse_element_id(value)
