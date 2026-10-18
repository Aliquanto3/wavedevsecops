"""Story 1.2 : serveur local protégé, instance unique, données de premier lancement (AD-19, AD-20).

Les tests lancent un vrai serveur sur 127.0.0.1 (port choisi par le système), dans un dossier
de données temporaire, et ne l'interrogent que par le loopback. Aucun navigateur réel.
"""

from __future__ import annotations

import http.client
import json
import logging
from collections.abc import Iterator
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import pytest

from wavedevsecops import cli
from wavedevsecops.config import Settings
from wavedevsecops.progress import FutureSchemaError, ensure_progress
from wavedevsecops.web import SESSION_COOKIE


@pytest.fixture
def instance(tmp_path: Path) -> Iterator[cli.Instance]:
    inst = cli.start_instance(Settings(data_dir=tmp_path / "data"))
    try:
        yield inst
    finally:
        inst.stop()


def request(
    inst: cli.Instance,
    method: str,
    path: str,
    headers: dict[str, str] | None = None,
) -> http.client.HTTPResponse:
    conn = http.client.HTTPConnection(cli.HOST, inst.port, timeout=5)
    conn.request(method, path, headers=headers or {})
    return conn.getresponse()


def session_cookie(inst: cli.Instance) -> dict[str, str]:
    resp = request(inst, "GET", f"/?t={inst.token}")
    resp.read()
    return {"Cookie": resp.getheader("Set-Cookie", "").split(";")[0]}


def assert_no_cors(resp: http.client.HTTPResponse) -> None:
    assert not [name for name, _ in resp.getheaders() if name.lower().startswith("access-control")]


def test_ecoute_sur_loopback_et_port_libre(instance: cli.Instance) -> None:
    assert instance.sock.getsockname()[0] == "127.0.0.1"
    assert instance.port > 0
    parts = urlsplit(instance.url)
    assert (parts.hostname, parts.port) == ("127.0.0.1", instance.port)
    assert parse_qs(parts.query)["t"] == [instance.token]


def test_jeton_echange_contre_cookie_puis_redirection(instance: cli.Instance) -> None:
    resp = request(instance, "GET", f"/?t={instance.token}")
    assert resp.status == 303
    assert resp.getheader("Location") == "/"
    cookie = resp.getheader("Set-Cookie", "")
    assert cookie.startswith(f"{SESSION_COOKIE}=")
    assert "HttpOnly" in cookie and "SameSite=strict" in cookie
    assert instance.token not in cookie
    page = request(instance, "GET", "/", {"Cookie": cookie.split(";")[0]})
    assert page.status == 200 and "WaveDevSecOps" in page.read().decode()
    assert_no_cors(page)


def test_refus_sans_cookie(instance: cli.Instance) -> None:
    for path in ("/", "/autre", f"/?t={instance.token}x"):
        resp = request(instance, "GET", path)
        assert resp.status == 401
        assert "Set-Cookie" not in dict(resp.getheaders())
        assert_no_cors(resp)


def test_refus_host_etranger(instance: cli.Instance) -> None:
    cookie = session_cookie(instance)
    for host in ("evil.example", f"127.0.0.1:{instance.port + 1}", "localhost", "[::1]"):
        resp = request(instance, "GET", "/", {**cookie, "Host": host})
        assert resp.status == 403, host
        assert_no_cors(resp)
    ok = request(instance, "GET", "/", {**cookie, "Host": f"localhost:{instance.port}"})
    assert ok.status == 200


def test_refus_post_origine_differente(instance: cli.Instance) -> None:
    cookie = session_cookie(instance)
    for origin in ("http://evil.example", f"http://localhost:{instance.port}", None):
        headers = dict(cookie) | ({"Origin": origin} if origin else {})
        resp = request(instance, "POST", "/api/x", headers)
        assert resp.status == 403, origin
        assert_no_cors(resp)
    same = {**cookie, "Origin": f"http://127.0.0.1:{instance.port}"}
    assert request(instance, "POST", "/api/x", same).status != 403


def test_osv_public_en_post_seulement(instance: cli.Instance) -> None:
    assert request(instance, "POST", "/osv/v1/query").status == 404  # route livrée plus tard
    resp = request(instance, "GET", "/osv/v1/query")
    assert resp.status == 405
    assert_no_cors(resp)


def test_seconde_instance_ouvre_l_url_existante_sans_ecrire(
    instance: cli.Instance, capsys: pytest.CaptureFixture[str]
) -> None:
    before = {p: p.stat().st_mtime_ns for p in instance.data_dir.rglob("*") if p.is_file()}
    opened: list[str] = []
    code = cli.main([], settings=Settings(data_dir=instance.data_dir), opener=opened.append)
    assert code == 0
    assert opened == [instance.url]
    after = {p: p.stat().st_mtime_ns for p in instance.data_dir.rglob("*") if p.is_file()}
    assert after == before
    assert "déjà lancé" in capsys.readouterr().out


def test_verrou_perime_remplace(tmp_path: Path) -> None:
    data = tmp_path / "data"
    data.mkdir()
    (data / cli.LOCK_NAME).write_text(json.dumps({"pid": 1, "port": 1, "token": "x"}), "utf-8")
    assert cli.read_running_instance(data) is None
    inst = cli.start_instance(Settings(data_dir=data))
    try:
        assert json.loads((data / cli.LOCK_NAME).read_text("utf-8"))["port"] == inst.port
    finally:
        inst.stop()
    assert not (data / cli.LOCK_NAME).exists()


def test_donnees_du_premier_lancement(tmp_path: Path) -> None:
    data = tmp_path / "data"
    data.mkdir()
    (data / "install.json").write_text(
        json.dumps({"schema_version": 1, "installed_at": "2026-10-01T09:00:00+02:00"}), "utf-8"
    )
    inst = cli.start_instance(Settings(data_dir=data))
    inst.stop()
    progress = json.loads((data / "progress.json").read_text("utf-8"))
    assert progress["schema_version"] == 1
    assert progress["installed_at"] == "2026-10-01T09:00:00+02:00"
    assert progress["first_launch_at"]
    first = progress["first_launch_at"]
    inst = cli.start_instance(Settings(data_dir=data))  # relance : fichier inchangé
    inst.stop()
    assert json.loads((data / "progress.json").read_text("utf-8"))["first_launch_at"] == first


def test_progress_sans_install_json(tmp_path: Path) -> None:
    from datetime import datetime

    data = ensure_progress(tmp_path, datetime.fromisoformat("2026-10-18T10:00:00+02:00"))
    assert data["installed_at"] is None
    assert data["first_launch_at"] == "2026-10-18T10:00:00+02:00"


def test_version_future_non_modifiee_et_message_clair(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    data = tmp_path / "data"
    data.mkdir()
    future = '{"schema_version": 99, "autre": true}'
    (data / "progress.json").write_text(future, "utf-8")
    with pytest.raises(FutureSchemaError):
        ensure_progress(data, __import__("datetime").datetime.now().astimezone())
    code = cli.main([], settings=Settings(data_dir=data), opener=lambda url: None)
    assert code == 1
    assert (data / "progress.json").read_text("utf-8") == future
    assert not (data / cli.LOCK_NAME).exists()
    assert "plus récente" in capsys.readouterr().err


def test_dossier_par_defaut_platformdirs() -> None:
    path = Settings().resolved_data_dir()
    assert path.name == "WaveDevSecOps"


def test_console_et_journal(instance: cli.Instance, capsys: pytest.CaptureFixture[str]) -> None:
    cli._console(instance.url, existing=False)
    out = capsys.readouterr().out
    assert f"http://127.0.0.1:{instance.port}/" in out
    assert instance.token not in out
    assert "NO_PROXY" in out and "--window" in out
    logging.getLogger("wavedevsecops").info("essai")
    log = (instance.data_dir / "logs" / "app.log").read_text("utf-8")
    assert "essai" in log
    assert instance.token not in log


def test_window_sans_extra_replie_sur_le_navigateur(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setitem(__import__("sys").modules, "webview", None)  # import -> ImportError
    opened: list[str] = []

    def opener(url: str) -> None:
        opened.append(url)
        # l'arrêt du serveur libère l'attente de `main`
        threading_stop()

    started: list[cli.Instance] = []
    real_start = cli.start_instance

    def spy(settings: Settings) -> cli.Instance:
        inst = real_start(settings)
        started.append(inst)
        return inst

    def threading_stop() -> None:
        started[0].server.should_exit = True

    monkeypatch.setattr(cli, "start_instance", spy)
    code = cli.main(["--window"], settings=Settings(data_dir=tmp_path / "d"), opener=opener)
    assert code == 0
    assert opened == [started[0].url]
    assert "extra « window »" in capsys.readouterr().err
