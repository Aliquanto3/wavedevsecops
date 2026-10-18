"""Garde réseau des tests (AD-13, contrôle 3).

Un hook d'audit `socket.connect`, posé par `conftest.py` pour toute la session, refuse
toute connexion vers une adresse non loopback en levant `NetworkAccessError` avant tout
envoi. Il refuse aussi la résolution d'un nom non loopback (`socket.getaddrinfo`,
`socket.gethostbyname`…), pour qu'aucune requête DNS ne parte : `create_connection`,
`urllib` et `httpx` résolvent le nom avant de se connecter.

Limite : `sock.connect(("nom", port))` résout le nom en C avant l'événement d'audit, sans
événement de résolution ; ce cas relève du contrôle (4) (`unshare -n`).

Un hook d'audit ne peut pas être retiré : il reste actif jusqu'à la fin de pytest.
"""

from __future__ import annotations

import ipaddress
import socket
import sys

_LOOPBACK_NAMES = {"localhost", "localhost.localdomain", "ip6-localhost", "ip6-loopback"}


class NetworkAccessError(RuntimeError):
    """Connexion sortante refusée pendant les tests : seul le loopback est permis."""


def is_loopback_address(address: object) -> bool:
    """Vrai si l'adresse passée à `socket.connect` reste sur le poste."""
    if isinstance(address, (str, bytes)):
        return True  # socket AF_UNIX : un chemin local
    if not isinstance(address, tuple) or not address:
        return False
    host = address[0]
    if isinstance(host, bytes):
        host = host.decode("ascii", "replace")
    if not isinstance(host, str):
        return False
    host = host.strip().lower()
    if host in _LOOPBACK_NAMES:
        return True
    try:
        return ipaddress.ip_address(host.split("%", 1)[0]).is_loopback
    except ValueError:
        return False


_RESOLUTION_EVENTS = {
    "socket.getaddrinfo",
    "socket.gethostbyname",
    "socket.gethostbyname_ex",
    "socket.gethostbyaddr",
}


def is_local_resolution(host: object) -> bool:
    """Vrai si résoudre `host` ne demande pas de DNS hors du poste."""
    if host is None or host in ("", b""):
        return True  # adresse joker de bind, ou getaddrinfo(None, port)
    if isinstance(host, bytes):
        host = host.decode("ascii", "replace")
    if not isinstance(host, str):
        return False
    try:
        ipaddress.ip_address(host.strip().split("%", 1)[0])
        return True  # adresse littérale : aucune requête DNS
    except ValueError:
        return is_loopback_address((host, 0))


def _audit_hook(event: str, args: tuple) -> None:
    if event in _RESOLUTION_EVENTS:
        if args and not is_local_resolution(args[0]):
            raise NetworkAccessError(f"résolution de nom non loopback refusée : {args[0]!r}")
        return
    if event != "socket.connect":
        return
    sock, address = args
    if getattr(sock, "family", None) == getattr(socket, "AF_UNIX", object()):
        return
    if not is_loopback_address(address):
        raise NetworkAccessError(f"connexion réseau non loopback refusée : {address!r}")


_installed = False


def install_network_guard() -> None:
    """Pose le hook d'audit une seule fois par processus."""
    global _installed
    if not _installed:
        sys.addaudithook(_audit_hook)
        _installed = True
