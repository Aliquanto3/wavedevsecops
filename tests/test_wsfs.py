"""Fichiers d'un espace : chemins confinés, LF, écritures atomiques (wsfs)."""

from __future__ import annotations

import json
import os
import stat
from pathlib import Path

import pytest

from wavedevsecops import wsfs
from wavedevsecops.contracts import element_id, parse_element_id


@pytest.mark.parametrize(
    "path",
    [
        "",
        "/etc/passwd",
        "../dehors.txt",
        "a/../../b",
        ".git/config",
        "src/.GIT/x",
        "C:/x",
        "a\\b",
        # Alias Windows de `.git` : points ou espaces finaux, nom court 8.3.
        ".git./config",
        ".git /config",
        "GIT~1/config",
        # Noms réservés ou non portables sous Windows.
        "NUL",
        "src/con.txt",
        "lpt1",
        "x.",
        "dossier /a.txt",
    ],
)
def test_chemins_refuses(tmp_path: Path, path: str) -> None:
    with pytest.raises(wsfs.SandboxPathError) as info:
        wsfs.write_text(tmp_path, path, "x")
    assert "refusé" in info.value.cause_text


def test_ecriture_en_lf_et_utf8(tmp_path: Path) -> None:
    target = wsfs.write_text(tmp_path, "src/é.txt", "un\r\ndeux\rtrois\n")
    assert target.read_bytes() == b"un\ndeux\ntrois\n"
    assert wsfs.read_bytes(tmp_path, "src/é.txt") == b"un\ndeux\ntrois\n"
    assert wsfs.read_bytes(tmp_path, "absent.txt") is None
    assert wsfs.iter_files(tmp_path) == ["src/é.txt"]
    assert not [p for p in tmp_path.rglob(".wds-*")]


def test_lien_qui_sort_refuse(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    outside = tmp_path / "dehors"
    outside.mkdir()
    try:
        (root / "lien").symlink_to(outside, target_is_directory=True)
    except OSError:
        pytest.skip("liens symboliques indisponibles sur ce poste")
    with pytest.raises(wsfs.SandboxPathError):
        wsfs.write_text(root, "lien/x.txt", "x")


def test_lien_vers_git_refuse(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    (root / ".git").mkdir(parents=True)
    try:
        (root / "lien").symlink_to(root / ".git", target_is_directory=True)
    except OSError:
        pytest.skip("liens symboliques indisponibles sur ce poste")
    with pytest.raises(wsfs.SandboxPathError):
        wsfs.write_text(root, "lien/config", "x")
    assert not (root / ".git" / "config").exists()


def test_noms_ordinaires_admis(tmp_path: Path) -> None:
    for path in (".github/workflows/ci.yml", ".gitignore", "console.py", "src/nullable.txt"):
        wsfs.write_text(tmp_path, path, "x")
    assert wsfs.read_bytes(tmp_path, ".gitignore") == b"x"


def test_json_canonique(tmp_path: Path) -> None:
    wsfs.write_json(tmp_path / "run.json", {"b": 1, "a": "é"})
    raw = (tmp_path / "run.json").read_bytes()
    assert raw == '{\n  "a": "é",\n  "b": 1\n}\n'.encode()
    assert json.loads(raw) == {"a": "é", "b": 1}


def test_suppression_de_fichiers_en_lecture_seule(tmp_path: Path) -> None:
    target = tmp_path / "espace" / "objet"
    target.parent.mkdir()
    target.write_bytes(b"x")
    os.chmod(target, stat.S_IREAD)
    wsfs.remove_tree(tmp_path / "espace")
    assert not (tmp_path / "espace").exists()
    wsfs.remove_tree(tmp_path / "espace")


def test_disposition_d_un_espace(tmp_path: Path) -> None:
    layout = wsfs.Layout.for_scenario(tmp_path, "llm", "bac-a-sable-libre", "A")
    assert layout.root == tmp_path / "llm" / "bac-a-sable-libre.A"
    assert layout.repo.name == "repo" and layout.origin.name == "origin.git"


def test_element_id_aller_retour() -> None:
    eid = element_id("path", "worktree", "src/a:b%.py")
    assert eid == "path:worktree:src/a%3Ab%25.py"
    assert parse_element_id(eid) == ("path", ["worktree", "src/a:b%.py"])
    assert element_id("ref", "refs/heads/main") == "ref:refs/heads/main"
    with pytest.raises(ValueError):
        element_id("inconnu", "x")
    with pytest.raises(ValueError):
        parse_element_id("commit")
