"""AD-13, contrôle 3 : le hook d'audit `socket.connect` est actif pendant les tests."""

from __future__ import annotations

import socket

import pytest
from netguard import NetworkAccessError, is_loopback_address


def test_connexion_non_loopback_refusee() -> None:
    # 192.0.2.1 (TEST-NET-1) n'est jamais routée : le hook refuse avant tout envoi.
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.5)
        with pytest.raises(NetworkAccessError):
            sock.connect(("192.0.2.1", 9))


def test_connexion_par_nom_refusee() -> None:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        with pytest.raises(NetworkAccessError):
            sock.connect(("example.org", 443))


def test_connexion_loopback_permise() -> None:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:
        server.bind(("127.0.0.1", 0))
        server.listen(1)
        with socket.create_connection(server.getsockname(), timeout=2):
            conn, _ = server.accept()
            conn.close()


@pytest.mark.parametrize(
    ("address", "expected"),
    [
        (("127.0.0.1", 80), True),
        (("127.8.9.10", 80), True),
        (("::1", 80, 0, 0), True),
        (("localhost", 80), True),
        (("10.0.0.1", 80), False),
        (("0.0.0.0", 80), False),
        (("2001:db8::1", 80, 0, 0), False),
        (("pypi.org", 443), False),
        ("/tmp/socket", True),
    ],
)
def test_is_loopback_address(address: object, expected: bool) -> None:
    assert is_loopback_address(address) is expected
