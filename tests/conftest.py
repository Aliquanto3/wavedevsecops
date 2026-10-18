"""Configuration commune des tests : garde réseau active dès le démarrage (AD-13)."""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from netguard import install_network_guard


def pytest_configure(config) -> None:
    install_network_guard()


@pytest.fixture(scope="session")
def git_path() -> Path:
    """Vrai git du poste, résolu par le registre. Absent : test ignoré, sauf en CI (échec)."""
    from wavedevsecops.config import Settings
    from wavedevsecops.toolrun import resolve

    status = resolve("git", Settings())
    if not status.ok or status.path is None:
        if os.environ.get("CI"):
            pytest.fail(f"git est requis en CI : {status.reason}")
        pytest.skip(f"git indisponible : {status.reason}")
    return status.path
