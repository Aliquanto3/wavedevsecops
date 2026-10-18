"""Diagnostic (FR-19) : outils, langue de git, proxy ; `gitio.probe_language`."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from wavedevsecops import diagnostic, gitio, procs
from wavedevsecops.config import Settings, read_proxy_environment
from wavedevsecops.diagnostic import check_proxy, load_texts, mask_proxy

GIT = shutil.which("git")


@pytest.fixture(scope="module")
def texts() -> dict:
    return load_texts(Settings())


def test_masquage_du_proxy() -> None:
    assert mask_proxy("http://alice:s3cret@proxy.corp:3128/x?y=1") == "http://***@proxy.corp:3128"
    assert mask_proxy("proxy.corp:3128") == "proxy.corp:3128"
    assert "s3cret" not in mask_proxy("https://alice:s3cret@p:8080")
    assert mask_proxy("http://") == "***"


def test_lecture_des_variables_de_proxy() -> None:
    env = {"https_proxy": " http://p:1 ", "PATH": "x", "NO_PROXY": ""}
    assert read_proxy_environment(env) == {"HTTPS_PROXY": "http://p:1"}


def test_sans_proxy(texts: dict) -> None:
    check = check_proxy({}, texts)
    assert (check.status, check.blocking) == ("info", False)
    assert "Aucun proxy" in check.detail_text and check.what_to_do_text == ""


def test_proxy_complet(texts: dict) -> None:
    env = {
        "HTTP_PROXY": "http://u:pw@p.corp:3128",
        "HTTPS_PROXY": "http://u:pw@p.corp:3128",
        "NO_PROXY": "10.0.0.1, 127.0.0.1,LOCALHOST",
        "UV_SYSTEM_CERTS": "true",
    }
    check = check_proxy(env, texts)
    assert check.status == "info"
    assert "pw" not in check.detail_text and "***@p.corp:3128" in check.detail_text
    assert "NO_PROXY contient 127.0.0.1 et localhost" in check.detail_text
    assert "UV_SYSTEM_CERTS est posé (true)" in check.detail_text
    assert check.what_to_do_text == ""


def test_proxy_sans_no_proxy_ni_certificats(texts: dict) -> None:
    check = check_proxy({"HTTPS_PROXY": "http://p:1", "NO_PROXY": "localhost"}, texts)
    assert check.status == "warn" and check.blocking is False
    assert "ne contient pas 127.0.0.1" in check.detail_text
    assert "UV_SYSTEM_CERTS n'est pas posé" in check.detail_text
    assert "NO_PROXY" in check.what_to_do_text and "UV_SYSTEM_CERTS" in check.what_to_do_text


def test_langue_de_git_francaise_et_anglaise(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def fake(messages: dict[str, str]):  # noqa: ANN202
        def run(argv, *, env, cwd, timeout):  # noqa: ANN001, ANN202
            return procs.ProcResult(128, stderr=messages.get(env["LC_ALL"], ""))

        return run

    monkeypatch.setattr(gitio.procs, "run", fake({"C": "fatal: not a git repository"}))
    assert gitio.probe_language(tmp_path / "git").lang == "en"
    monkeypatch.setattr(
        gitio.procs,
        "run",
        fake({"C": "fatal: not a git repository", "fr_FR.utf8": "fatal : pas un dépôt git"}),
    )
    assert gitio.probe_language(tmp_path / "git") == gitio.GitLanguage("fr", "fr_FR.utf8")
    monkeypatch.setattr(gitio.procs, "run", lambda *a, **k: procs.ProcResult(None, error="x"))
    assert gitio.probe_language(tmp_path / "git").lang == "en"


@pytest.mark.skipif(GIT is None, reason="git absent du poste")
def test_langue_du_vrai_git() -> None:
    assert gitio.probe_language(Path(GIT)).lang in {"fr", "en"}


def test_diagnostic_sans_aucun_outil(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("wavedevsecops.toolrun.shutil.which", lambda name: None)
    checks = diagnostic.run_diagnostic(Settings(data_dir=tmp_path), environ={})
    by_id = {c.check_id: c for c in checks}
    assert by_id["tool.git"].status == "missing" and by_id["tool.git"].blocking
    assert "installeur" in by_id["tool.git"].what_to_do_text
    assert by_id["tool.uv"].status == "missing"
    assert "tool.pixi" not in by_id  # outil d'installeur : hors diagnostic
    assert "git_language" not in by_id  # pas de git trouvé, pas de ligne de langue
    assert by_id["proxy"].blocking is False


@pytest.mark.skipif(GIT is None, reason="git absent du poste")
def test_diagnostic_reel_emet_chaque_resultat(tmp_path: Path) -> None:
    events: list[tuple[str, dict]] = []
    checks = diagnostic.run_diagnostic(
        Settings(data_dir=tmp_path), emit=lambda k, p: events.append((k, p)), environ={}
    )
    assert [kind for kind, _ in events] == ["diagnostic_check"] * len(checks)
    assert [p["check_id"] for _, p in events] == [c.check_id for c in checks]
    by_id = {c.check_id: c for c in checks}
    assert by_id["tool.git"].status in {"ok", "too_old"}
    assert by_id["tool.gitleaks"].status in {"ok", "missing", "too_old"}  # absent en CI
    line = by_id.get("git_language")
    if by_id["tool.git"].status == "ok":
        assert line and line.status == "info" and not line.blocking
        assert line.detail_text.startswith("git parle ")
    for check in checks:
        assert check.label_text and check.status_text and check.detail_text
        if check.status != "ok" and check.group == "tool":
            assert check.what_to_do_text, check.check_id
