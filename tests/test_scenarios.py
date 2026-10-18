"""Modèle de scénario, registre d'ops et erreurs en français avec champ et ligne (AD-7)."""

from __future__ import annotations

from pathlib import Path

import pytest

from wavedevsecops.config import Settings
from wavedevsecops.scenarios import (
    REGISTRY,
    ScenarioError,
    load_scenario,
    parse_scenario,
    scenario_files,
)
from wavedevsecops.scenarios.ops import OpArgs

VALID = """\
schema_version: 1
scenario_id: essai
mode: A
title_text: Essai
tracks: [llm]
tools: [git]
setup:
  - op: write_file
    path: a.txt
    content: "a"
    as: fichier-a
  - op: commit
    message: Premier
    as: premier
  - op: branch
    name: feature
    start: "@premier"
steps:
  - step_id: premiere_etape
    type: free
"""


def _errors(text: str, **kwargs) -> list:
    with pytest.raises(ScenarioError) as info:
        parse_scenario(text, "essai.A.yaml", **kwargs)
    assert info.value.action_text
    return info.value.errors


def test_registre_des_ops() -> None:
    assert {"write_file", "commit", "branch", "switch", "push"} <= set(REGISTRY)
    for name, spec in REGISTRY.items():
        assert issubclass(spec.args, OpArgs)
        assert spec.args.model_fields["op"].annotation.__args__ == (name,)
        assert "as" in {f.alias for f in spec.args.model_fields.values()}
        assert spec.summary


def test_scenario_valide() -> None:
    scenario = parse_scenario(VALID, "essai.A.yaml", tool_ids={"git"}, expected_key="essai.A")
    assert scenario.key == "essai.A"
    assert [op.op for op in scenario.setup] == ["write_file", "commit", "branch"]
    assert scenario.setup[0].as_ == "fichier-a"
    assert scenario.steps[0].step_id == "premiere_etape"


def test_liste_d_etapes_vide_admise() -> None:
    text = VALID.split("steps:")[0] + "steps: []\n"
    assert parse_scenario(text, "essai.A.yaml").steps == []


def test_champ_manquant_nomme_le_champ_et_la_ligne() -> None:
    errors = _errors(VALID.replace("    message: Premier\n", ""))
    assert [(e.field, e.line) for e in errors] == [("setup[1].message", 12)]
    assert errors[0].message == "champ obligatoire absent"


def test_op_inconnue() -> None:
    errors = _errors(VALID.replace("op: branch", "op: rebase"))
    assert errors[0].field == "setup[2]"
    assert errors[0].line == 15
    assert "op inconnue « rebase »" in errors[0].message


def test_champ_inconnu_et_type_faux() -> None:
    text = VALID.replace("mode: A", "mode: C").replace("title_text: Essai", "titre: Essai")
    found = {(e.field, e.line): e.message for e in _errors(text)}
    assert "valeur non admise" in found[("mode", 3)]
    assert found[("titre", 4)] == "champ inconnu"
    assert found[("title_text", 1)] == "champ obligatoire absent"


def test_alias_non_defini_et_doublons() -> None:
    text = VALID.replace('start: "@premier"', 'start: "@absent"').replace(
        "as: premier", "as: fichier-a"
    )
    text += "  - step_id: premiere_etape\n    type: free\n"
    found = {e.field: (e.line, e.message) for e in _errors(text)}
    assert found["setup[2].start"] == (
        17,
        "l'alias « @absent » n'est défini par aucune op précédente",
    )
    assert "en double" in found["setup[1].as"][1]
    assert found["steps[1].step_id"][0] == 21


def test_outil_inconnu_et_nom_de_fichier() -> None:
    text = VALID.replace("tools: [git]", "tools: [git, svn]")
    found = {e.field: e for e in _errors(text, tool_ids={"git"}, expected_key="autre.B")}
    assert "outil inconnu" in found["tools[1]"].message
    assert found["tools[1]"].line == 6
    assert "essai.A.yaml" in found["scenario_id"].message


def test_chemin_hors_depot_refuse() -> None:
    errors = _errors(VALID.replace("path: a.txt", "path: ../a.txt"))
    assert errors[0].field == "setup[0].path"
    assert "remonte hors du dépôt" in errors[0].message


def test_yaml_illisible() -> None:
    errors = _errors("schema_version: 1\nsetup: [\n")
    assert errors[0].field == "(document)"
    assert errors[0].line is not None
    assert "YAML illisible" in errors[0].message


def test_message_complet_en_francais() -> None:
    with pytest.raises(ScenarioError) as info:
        parse_scenario(VALID.replace("    message: Premier\n", ""), "essai.A.yaml")
    assert info.value.cause_text == (
        "Le scénario « essai.A.yaml » est invalide :\n"
        "- ligne 12, champ setup[1].message : champ obligatoire absent"
    )


def test_switch_coherent() -> None:
    text = VALID.replace("  - op: branch\n    name: feature\n", "  - op: switch\n    branch: x\n")
    errors = _errors(text)
    assert errors[0].field == "setup[2]"
    assert "create: true" in errors[0].message


def test_scenarios_du_depot_valides() -> None:
    files = scenario_files(Settings())
    assert any(p.name == "bac-a-sable-libre.A.yaml" for p in files)
    for path in files:
        loaded = load_scenario(path, Settings())
        assert loaded.scenario.schema_version == 1
        assert len(loaded.content_hash) == 64


def test_content_hash_independant_des_fins_de_ligne(tmp_path: Path) -> None:
    folder = tmp_path / "scenarios"
    folder.mkdir()
    (folder / "essai.A.yaml").write_bytes(VALID.encode())
    lf = load_scenario(folder / "essai.A.yaml", Settings()).content_hash
    (folder / "essai.A.yaml").write_bytes(VALID.replace("\n", "\r\n").encode())
    assert load_scenario(folder / "essai.A.yaml", Settings()).content_hash == lf


def test_cle_en_double_refusee() -> None:
    text = VALID.replace("mode: A\n", "mode: A\nmode: B\n")
    errors = _errors(text)
    assert [(e.field, e.line, e.message) for e in errors] == [("mode", 4, "clé en double")]


def test_revision_de_depart_qui_ressemble_a_une_option() -> None:
    errors = _errors(VALID.replace('start: "@premier"', 'start: "--orphan"'))
    assert errors[0].field == "setup[2].start" and "révision invalide" in errors[0].message


def test_station_hors_de_la_chaine_refusee() -> None:
    errors = _errors(VALID.replace("tracks: [llm]", "station: 7\ntracks: [llm]"))
    assert [e.field for e in errors] == ["station"]
    four = VALID.replace("tracks: [llm]", "station: 4\ntracks: [llm]")
    assert parse_scenario(four, "essai.A.yaml").station == 4
