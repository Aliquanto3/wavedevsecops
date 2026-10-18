"""AD-13, contrôles 1 et 2 : aucun import réseau ni URL externe hors des exceptions."""

from __future__ import annotations

from pathlib import Path

import pytest
from static_rules import (
    misplaced_static_dirs,
    network_import_violations,
    static_url_violations,
)


def _write(root: Path, name: str, code: str) -> Path:
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(code, encoding="utf-8")
    return root


def test_aucun_import_reseau_dans_src() -> None:
    assert network_import_violations() == []


def test_aucune_url_externe_dans_static() -> None:
    assert static_url_violations() == []


def test_static_au_chemin_controle() -> None:
    # Un dossier static déplacé échapperait au contrôle 2 sans le faire échouer.
    assert misplaced_static_dirs() == []


def test_static_deplace_detecte(tmp_path: Path) -> None:
    src = tmp_path / "pkg"
    (src / "ui" / "static").mkdir(parents=True)
    assert misplaced_static_dirs(src, src / "web" / "static") == ["ui/static"]


@pytest.mark.parametrize(
    "code",
    [
        "import socket\n",
        "import http.client\n",
        "from http import client\n",
        "import urllib.request\n",
        "from urllib import request\n",
        "from urllib.request import urlopen\n",
        "import httpx\n",
        "import requests\n",
        "from aiohttp import ClientSession\n",
        "import ssl\n",
        "import _socket\n",
        "import urllib3\n",
        "from smtplib import SMTP\n",
    ],
)
def test_import_reseau_refuse(tmp_path: Path, code: str) -> None:
    src = _write(tmp_path / "pkg", "engine/__init__.py", code)
    assert len(network_import_violations(src, "pkg")) == 1


@pytest.mark.parametrize(
    ("name", "code", "allowed"),
    [
        ("llmrun/__init__.py", "import httpx\nimport socket\n", True),
        ("web/server.py", "import socket\n", True),
        ("cli.py", "import socket\n", True),
        ("web/server.py", "import httpx\n", False),
        ("cli.py", "import ssl\n", False),
        ("engine/__init__.py", "import urllib.parse\nimport http\n", True),
    ],
)
def test_exceptions_reseau(tmp_path: Path, name: str, code: str, allowed: bool) -> None:
    src = _write(tmp_path / "pkg", name, code)
    assert (network_import_violations(src, "pkg") == []) is allowed


def test_url_externe_refusee(tmp_path: Path) -> None:
    static = tmp_path / "static"
    _write(static, "app.js", "fetch('https://cdn.example.com/lib.js');\n")
    _write(static, "style.css", "@import url(http://fonts.example.org/a.css);\n")
    _write(static, "ws.js", "new WebSocket('wss://relay.example.net/s');\n")
    violations = static_url_violations(static)
    assert len(violations) == 3
    assert violations[0].startswith("app.js:1 https://cdn.example.com/lib.js")


def test_url_loopback_et_espaces_de_noms_permis(tmp_path: Path) -> None:
    static = tmp_path / "static"
    _write(
        static,
        "app.js",
        "fetch('http://127.0.0.1:8000/api');\n"
        "fetch('http://localhost/x');\n"
        "fetch('http://[::1]:9/');\n"
        "new WebSocket('ws://127.0.0.1:8000/events');\n"
        "document.createElementNS('http://www.w3.org/2000/svg', 'svg');\n",
    )
    (static / "font.woff2").write_bytes(b"\x00http://example.com\x00")
    assert static_url_violations(static) == []


def test_licence_de_police_exclue_mais_pas_le_code(tmp_path: Path) -> None:
    static = tmp_path / "static"
    _write(static, "fonts/OFL-fredoka.txt", "See http://scripts.sil.org/OFL\n")
    assert static_url_violations(static) == []
    _write(static, "fonts/OFL-fredoka.js", "fetch('http://scripts.sil.org/OFL');\n")
    _write(static, "fonts/autre.txt", "http://scripts.sil.org/OFL\n")
    _write(static, "OFL-racine.txt", "http://scripts.sil.org/OFL\n")
    assert len(static_url_violations(static)) == 3


def test_hote_deguise_refuse(tmp_path: Path) -> None:
    static = tmp_path / "static"
    _write(static, "app.js", "fetch('http://127.evil.example/x');\n")
    assert len(static_url_violations(static)) == 1
