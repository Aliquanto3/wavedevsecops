# ruff: noqa: E501
"""Explications de la vue pipeline et lien actif « traçabilité » (story 9.6)."""

from __future__ import annotations

from pathlib import Path

import yaml
from test_catalogue import call, cookie, instance  # noqa: F401  (fixtures)

from wavedevsecops.config import Settings
from wavedevsecops.projections import EXPLAIN_REFS
from wavedevsecops.projections.views import PIPELINE_JOB_IDS, pipeline_explain_ref
from wavedevsecops.web.explanations import load_explanations
from wavedevsecops.web.glossary import _trace, glossary_body, load_glossary, open_station_workspace

CONTENT = Path(__file__).resolve().parent.parent / "content"


def _job_ids() -> list[str]:
    return [
        j["job_id"] for j in yaml.safe_load((CONTENT / "pipeline.yaml").read_text("utf-8"))["jobs"]
    ]


def test_chaque_job_du_pipeline_a_une_explication() -> None:
    assert list(PIPELINE_JOB_IDS) == _job_ids()
    catalogue = load_explanations(Settings(content_dir=CONTENT))
    assert catalogue is not None
    for job_id in _job_ids():
        ref = pipeline_explain_ref(job_id)
        assert ref == f"pipeline.{job_id}" and ref in EXPLAIN_REFS and ref in catalogue.entries


def test_un_job_inconnu_n_a_pas_d_explication_propre() -> None:
    assert pipeline_explain_ref("revue_manuelle") == ""
    assert pipeline_explain_ref("revue_manuelle", "remote.check") == "remote.check"


def test_la_tracabilite_a_un_lien_avec_espace_et_une_phrase_sans() -> None:
    glossary = load_glossary(Settings(content_dir=CONTENT))
    assert glossary is not None
    term = next(t for t in glossary.terms if t.id == "traceability")
    assert _trace(term, "sans-ia.revue-humaine.A") == {
        "link": {"href": "/espace/sans-ia.revue-humaine.A", "text": term.trace_link_text}
    }
    none = _trace(term, None)
    assert none is not None and none["link"] is None
    assert "ouvrez un scénario de station" in none["none_text"]
    body = glossary_body(Settings(content_dir=CONTENT), "sans-ia.x.A")
    by_id = {t["id"]: t for t in body["terms"]}
    assert by_id["traceability"]["trace"]["link"]["href"] == "/espace/sans-ia.x.A"
    assert by_id["sast"]["trace"] is None


def test_sans_dernier_espace_ou_avec_espace_disparu_pas_de_lien(tmp_path: Path) -> None:
    settings = Settings(content_dir=CONTENT, data_dir=tmp_path)
    assert open_station_workspace(settings, lambda _id: True) is None  # rien d'ouvert


def test_get_glossary_sans_espace_ouvert_donne_la_phrase(instance, cookie) -> None:  # noqa: F811
    status, body = call(instance, "GET", "/api/glossary", cookie)
    trace = next(t for t in body["terms"] if t["id"] == "traceability")["trace"]
    assert status == 200 and trace["link"] is None and trace["none_text"]
