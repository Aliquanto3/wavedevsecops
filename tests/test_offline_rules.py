"""AD-13, contrôles 1 et 2 : aucun import réseau ni URL externe hors des exceptions."""

from __future__ import annotations

from pathlib import Path

import pytest
from static_rules import network_import_violations, static_url_violations


def _write(root: Path, name: str, code: str) -> Path:
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(code, encoding="utf-8")
    return root


def test_aucun_import_reseau_dans_src() -> None:
    assert network_import_violations() == []


def test_aucune_url_externe_dans_static() -> None:
    assert static_url_violations() == []


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
    violations = static_url_violations(static)
    assert len(violations) == 2
    assert violations[0].startswith("app.js:1 https://cdn.example.com/lib.js")


def test_url_loopback_et_espaces_de_noms_permis(tmp_path: Path) -> None:
    static = tmp_path / "static"
    _write(
        static,
        "app.js",
        "fetch('http://127.0.0.1:8000/api');\n"
        "fetch('http://localhost/x');\n"
        "fetch('http://[::1]:9/');\n"
        "document.createElementNS('http://www.w3.org/2000/svg', 'svg');\n",
    )
    (static / "font.woff2").write_bytes(b"\x00http://example.com\x00")
    assert static_url_violations(static) == []


def test_hote_deguise_refuse(tmp_path: Path) -> None:
    static = tmp_path / "static"
    _write(static, "app.js", "fetch('http://127.evil.example/x');\n")
    assert len(static_url_violations(static)) == 1
