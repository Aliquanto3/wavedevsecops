"""Page Diagnostic (Story 1.5) : rapport, API, premier lancement, console, pastille."""

from __future__ import annotations

import http.client
import json
from collections.abc import Iterator
from pathlib import Path

import pytest

from wavedevsecops import cli, diagnostic, toolrun
from wavedevsecops.config import Settings, read_proxy_environment
from wavedevsecops.diagnostic import build_report, check_proxy, console_lines, load_texts

SETTINGS = Settings()
TEXTS = load_texts(SETTINGS)


def _fake_resolve(missing: set[str], old: set[str] = frozenset()):
    def resolve(tool_id: str, *args: object, **kwargs: object) -> toolrun.ToolStatus:
        if tool_id in missing:
            return toolrun.ToolStatus(tool_id, "missing", reason="introuvable")
        if tool_id in old:
            return toolrun.ToolStatus(tool_id, "too_old", "0.1", None, "host", "trop ancien")
        return toolrun.ToolStatus(tool_id, "ok", "9.9.9", Path("x"), "host")

    return resolve


def _checks(monkeypatch: pytest.MonkeyPatch, missing=(), old=(), environ=None, scenarios=None):
    monkeypatch.setattr(diagnostic.toolrun, "resolve", _fake_resolve(set(missing), set(old)))
    monkeypatch.setattr(diagnostic.gitio, "probe_language", lambda *a, **k: _FR)
    return diagnostic.run_diagnostic(SETTINGS, environ=environ or {}, scenarios=scenarios)


class _Lang:
    lang = "fr"


_FR = _Lang()


# --- NO_PROXY : la revue 1.4 ------------------------------------------------------------------


def test_no_proxy_et_no_proxy_minuscule_qui_different_sont_fusionnes() -> None:
    env = {"NO_PROXY": "10.0.0.1", "no_proxy": "127.0.0.1,localhost", "HTTP_PROXY": "http://p:1"}
    assert read_proxy_environment(env)["NO_PROXY"] == "10.0.0.1,127.0.0.1,localhost"
    check = check_proxy(env, TEXTS)
    assert "NO_PROXY contient 127.0.0.1 et localhost" in check.detail_text
    assert check.status == "info"  # plus de faux avertissement


def test_no_proxy_identique_n_est_pas_duplique() -> None:
    env = {"NO_PROXY": "a,b", "no_proxy": "b,a"}
    assert read_proxy_environment(env)["NO_PROXY"] == "a,b"


# --- section Proxy ----------------------------------------------------------------------------


def test_proxy_detecte_trois_lignes_avec_leur_que_faire() -> None:
    env = {"HTTPS_PROXY": "http://u:pw@p.corp:3128", "NO_PROXY": "intra.local"}
    check = check_proxy(env, TEXTS)
    labels = [part.label_text for part in check.parts]
    assert labels == ["Proxy", "NO_PROXY", "UV_SYSTEM_CERTS"]
    proxy, no_proxy, certs = check.parts
    assert proxy.status_text == "Détecté" and "pw" not in proxy.value_text
    assert no_proxy.status == "warn" and "`127.0.0.1`" in no_proxy.what_to_do_text
    assert certs.what_to_do_text and certs.status == "info"


def test_aucun_proxy_une_seule_ligne() -> None:
    check = check_proxy({}, TEXTS)
    assert [part.status_text for part in check.parts] == ["Aucun"]


# --- rapport -----------------------------------------------------------------------------------


def test_rapport_tout_est_pret(monkeypatch: pytest.MonkeyPatch) -> None:
    report = build_report(_checks(monkeypatch), TEXTS)
    assert report["problem_count"] == 0 and report["badge_text"] == ""
    assert report["git_notice"] is None
    assert report["summary_text"].startswith("Recherche terminée : tous les ")


def test_rapport_outils_en_defaut_synthese_et_pastille(monkeypatch: pytest.MonkeyPatch) -> None:
    env = {"HTTP_PROXY": "http://p:1", "NO_PROXY": "intra"}
    checks = _checks(monkeypatch, missing={"gitleaks"}, old={"uv"}, environ=env)
    report = build_report(checks, TEXTS)
    total = sum(1 for c in report["checks"] if c["group"] == "tool")
    assert report["problem_count"] == 2
    assert report["summary_text"] == (
        f"Recherche terminée : 2 outils sur {total} demandent une action, "
        "et NO_PROXY demande un réglage."
    )
    assert report["badge_text"] == "Diagnostic, 2 outils absents ou trop anciens"
    by_id = {c["check_id"]: c for c in report["checks"]}
    assert by_id["tool.gitleaks"]["status_text"] == "Absent"
    assert by_id["tool.gitleaks"]["what_to_do_text"]  # « Que faire ? » de content/diagnostic.yaml
    assert by_id["tool.git"]["usage_text"] and by_id["tool.git"]["required_version"] == "≥ 2.38"
    assert report["git_notice"] is None  # git va bien


def test_groupes_par_jalon_dans_l_ordre(monkeypatch: pytest.MonkeyPatch) -> None:
    report = build_report(_checks(monkeypatch), TEXTS)
    titles = [g["title_text"] for g in report["groups"]]
    assert titles[0] == "Outils requis (v0.1)"
    assert all(t.startswith("Outils de la chaîne (") for t in titles[1:])
    grouped = [i for g in report["groups"] for i in g["check_ids"]]
    expected = [c["check_id"] for c in report["checks"] if c["group"] == "tool"]
    assert sorted(grouped) == sorted(expected)


def test_git_absent_donne_un_encart_d_erreur(monkeypatch: pytest.MonkeyPatch) -> None:
    report = build_report(_checks(monkeypatch, missing={"git"}), TEXTS)
    notice = report["git_notice"]
    assert notice["cause_text"] and notice["action_text"]
    assert report["problem_count"] >= 1


def test_un_seul_outil_au_singulier(monkeypatch: pytest.MonkeyPatch) -> None:
    report = build_report(_checks(monkeypatch, missing={"uv"}), TEXTS)
    assert " 1 outil sur " in report["summary_text"] and "demande une action" in report[
        "summary_text"
    ]


def test_scenarios_indisponibles_viennent_du_diagnostic(monkeypatch: pytest.MonkeyPatch) -> None:
    checks = _checks(
        monkeypatch,
        missing={"gitleaks"},
        scenarios={"gitleaks": ["Hook pre-commit"], "uv": ["Autre"]},
    )
    by_id = {c.check_id: c for c in checks}
    assert by_id["tool.gitleaks"].unavailable_scenarios == ["Hook pre-commit"]
    assert by_id["tool.uv"].unavailable_scenarios == []  # outil en règle : rien d'indisponible
    assert all(c.unavailable_scenarios == [] for c in _checks(monkeypatch, missing={"uv"}))


def test_plan_liste_les_lignes_en_cours() -> None:
    plan = diagnostic.plan(SETTINGS)
    ids = [r["check_id"] for r in plan["rows"]]
    assert "tool.git" in ids and "tool.pixi" not in ids
    assert plan["ui"]["running"] == "En cours"
    assert sorted(i for g in plan["groups"] for i in g["check_ids"]) == sorted(ids)


def test_console_reprend_le_meme_diagnostic(monkeypatch: pytest.MonkeyPatch) -> None:
    lines = console_lines(_checks(monkeypatch, missing={"gitleaks"}), TEXTS)
    text = "\n".join(lines)
    assert lines[0] == "Diagnostic du poste :"
    assert "gitleaks : Absent (absent)" in text and "git : Prêt (9.9.9)" in text
    assert "À faire :" in text


# --- API et premier lancement ------------------------------------------------------------------


@pytest.fixture
def instance(tmp_path: Path) -> Iterator[cli.Instance]:
    inst = cli.start_instance(Settings(data_dir=tmp_path / "data"))
    try:
        yield inst
    finally:
        inst.stop()


def _call(inst: cli.Instance, method: str, path: str, cookie: dict[str, str]):
    headers = dict(cookie)
    if method == "POST":
        headers["Origin"] = f"http://{cli.HOST}:{inst.port}"
    conn = http.client.HTTPConnection(cli.HOST, inst.port, timeout=30)
    conn.request(method, path, headers=headers)
    resp = conn.getresponse()
    body = resp.read()
    conn.close()
    return resp, body


@pytest.fixture
def cookie(instance: cli.Instance) -> dict[str, str]:
    resp, _ = _call(instance, "GET", f"/?t={instance.token}", {})
    return {"Cookie": resp.getheader("Set-Cookie", "").split(";")[0]}


def test_premier_lancement_ouvre_le_diagnostic_puis_l_accueil(
    instance: cli.Instance, cookie: dict[str, str]
) -> None:
    first, _ = _call(instance, "GET", "/", cookie)
    assert (first.status, first.getheader("Location")) == (303, "/diagnostic")
    page, _ = _call(instance, "GET", "/diagnostic", cookie)
    assert page.status == 200
    later, _ = _call(instance, "GET", "/", cookie)
    assert later.status == 200  # lancements suivants : l'accueil
    assert (Path(instance.data_dir) / "diagnostic_seen").is_file()


def test_api_diagnostic_plan_puis_rapport_et_console(
    instance: cli.Instance,
    cookie: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(diagnostic.toolrun, "resolve", _fake_resolve({"gitleaks"}))
    monkeypatch.setattr(diagnostic.gitio, "probe_language", lambda *a, **k: _FR)
    resp, body = _call(instance, "GET", "/api/diagnostic", cookie)
    state = json.loads(body)
    assert resp.status == 200 and state["report"] is None
    assert state["rows"] and state["groups"] and state["ui"]["rerun"] == "Relancer le diagnostic"

    resp, body = _call(instance, "POST", "/api/diagnostic/run", cookie)
    report = json.loads(body)
    assert resp.status == 200 and report["problem_count"] == 1
    assert report["badge_text"].startswith("Diagnostic, 1 ")
    assert "gitleaks : Absent" in capsys.readouterr().out  # écrit dans la console de lancement

    _, body = _call(instance, "GET", "/api/diagnostic", cookie)
    assert json.loads(body)["report"]["problem_count"] == 1  # rapport gardé pour la pastille


def test_run_refuse_sans_origine(instance: cli.Instance, cookie: dict[str, str]) -> None:
    conn = http.client.HTTPConnection(cli.HOST, instance.port, timeout=5)
    conn.request("POST", "/api/diagnostic/run", headers=cookie)
    assert conn.getresponse().status == 403
    conn.close()


def test_echec_du_diagnostic_sans_trace(
    instance: cli.Instance, cookie: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    def boom(*a: object, **k: object) -> None:
        raise RuntimeError("secret interne")

    monkeypatch.setattr(diagnostic, "run_diagnostic", boom)
    resp, body = _call(instance, "POST", "/api/diagnostic/run", cookie)
    assert resp.status == 500
    assert "secret interne" not in body.decode() and "Relancez-le" in body.decode()
