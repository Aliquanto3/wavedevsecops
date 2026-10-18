"""`Settings` : objet unique, lu depuis les variables `WDS_*`."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from wavedevsecops.config import Settings, get_settings


def test_valeurs_par_defaut_sans_environnement() -> None:
    assert Settings.from_env({}).data_dir is None


def test_lecture_des_variables_prefixees(tmp_path: Path) -> None:
    settings = Settings.from_env({"WDS_DATA_DIR": str(tmp_path), "DATA_DIR": "ignoré"})
    assert settings.data_dir == tmp_path


def test_reglages_figes() -> None:
    with pytest.raises(ValidationError):
        Settings.from_env({}).data_dir = Path("x")  # type: ignore[misc]


def test_get_settings_unique() -> None:
    assert get_settings() is get_settings()
