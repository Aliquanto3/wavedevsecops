"""Empreintes de référence (AD-18) : chaque scénario, sur chaque système, donne
l'empreinte de `content/fingerprints.json`.

La CI rejoue ce test sous Windows sur un clone `core.autocrlf=true`, et sous Linux dans un
espace de noms sans réseau (`unshare -n`, contrôle 4 d'AD-13).
Après la modification d'un scénario : `uv run python scripts/update_fingerprints.py`.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from wavedevsecops.config import Settings
from wavedevsecops.engine import load_references, prepare_workspace, reference_key
from wavedevsecops.scenarios import load_scenario, scenario_files

CASES = [
    (path, track)
    for path in scenario_files(Settings())
    for track in load_scenario(path, Settings()).scenario.tracks
]


@pytest.mark.parametrize(("path", "track"), CASES, ids=[f"{t}/{p.stem}" for p, t in CASES] or None)
def test_empreinte_de_reference(path: Path, track: str, tmp_path: Path, git_path: Path) -> None:
    loaded = load_scenario(path, Settings())
    key = reference_key(track, loaded.scenario.key)
    expected = load_references(Settings()).get(key)
    assert expected, f"{key} absente de content/fingerprints.json (scripts/update_fingerprints.py)"
    prepared = prepare_workspace(
        loaded, track, settings=Settings(data_dir=tmp_path), git_path=git_path
    )
    assert prepared.fingerprint == expected, (
        f"{key} : empreinte {prepared.fingerprint} au lieu de {expected}"
    )


def test_aucune_reference_orpheline() -> None:
    known = {reference_key(track, path.name.removesuffix(".yaml")) for path, track in CASES}
    assert CASES, "aucun scénario dans content/scenarios/"
    assert set(load_references(Settings())) == known
