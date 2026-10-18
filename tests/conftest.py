"""Configuration commune des tests : garde réseau active dès le démarrage (AD-13)."""

from __future__ import annotations

from netguard import install_network_guard


def pytest_configure(config) -> None:
    install_network_guard()
