"""Story 8.2 : point OSV local servi depuis l'extrait figé de `content/osv/` (AD-11, AD-19)."""

from __future__ import annotations

import http.client
import json
import os
import subprocess
import sys
import threading
import tomllib
from collections.abc import Iterator
from pathlib import Path

import pytest
from packaging.version import InvalidVersion, Version

from wavedevsecops import cli, osv
from wavedevsecops.config import Settings, project_root

OSV_DIR = project_root() / "content" / "osv"
EXERCISE = project_root() / "content" / "exercise"


@pytest.fixture(scope="module")
def instance(tmp_path_factory: pytest.TempPathFactory) -> Iterator[cli.Instance]:
    inst = cli.start_instance(Settings(data_dir=tmp_path_factory.mktemp("data")))
    try:
        yield inst
    finally:
        inst.stop()


def call(
    inst: cli.Instance,
    method: str,
    body: bytes | str | None = None,
    path: str = "/osv/v1/query",
    headers: dict[str, str] | None = None,
) -> tuple[int, bytes]:
    conn = http.client.HTTPConnection(cli.HOST, inst.port, timeout=10)
    conn.request(method, path, body=body, headers=headers or {})
    resp = conn.getresponse()
    return resp.status, resp.read()


def query(inst: cli.Instance, name: str, version: str | None) -> tuple[int, dict]:
    body: dict = {"package": {"name": name, "ecosystem": "PyPI"}}
    if version is not None:
        body["version"] = version
    status, raw = call(inst, "POST", json.dumps(body))
    return status, json.loads(raw)


# --- L'extrait -----------------------------------------------------------------------------


def test_extrait_date_et_enregistrements_copies_tels_quels() -> None:
    meta = json.loads((OSV_DIR / "index.json").read_text(encoding="utf-8"))
    assert meta["extracted_on"].count("-") == 2
    assert (OSV_DIR / "ATTRIBUTION.md").read_text(encoding="utf-8").count("CC-BY 4.0") >= 1
    listed = {i for ids in meta["packages"].values() for i in ids}
    files = {p.stem for p in (OSV_DIR / "vulns").glob("*.json")}
    assert listed == files
    for vuln_id in sorted(files)[:20]:
        record = json.loads((OSV_DIR / "vulns" / f"{vuln_id}.json").read_text(encoding="utf-8"))
        assert record["id"] == vuln_id
        assert record["affected"]


def test_paquets_des_gabarits_couverts() -> None:
    meta = json.loads((OSV_DIR / "index.json").read_text(encoding="utf-8"))
    for lock in EXERCISE.glob("*/uv.lock"):
        for package in tomllib.loads(lock.read_text(encoding="utf-8"))["package"]:
            if package["name"] != "inventory":
                assert osv.normalize(package["name"]) in meta["packages"]


def test_gabarits_propres_dans_la_base_figee() -> None:
    """Aucune dépendance verrouillée des gabarits n'est vulnérable : le départ est au vert."""
    extract = osv.load_extract(OSV_DIR)
    for lock in EXERCISE.glob("*/uv.lock"):
        for package in tomllib.loads(lock.read_text(encoding="utf-8"))["package"]:
            if package["name"] != "inventory":
                found = extract.query(package["name"], package["version"])
                assert found == [], (lock, package["name"], package["version"])


def test_versions_vulnerables_prevues_pour_la_station_3() -> None:
    extract = osv.load_extract(OSV_DIR)
    assert extract.query("jinja2", "3.1.2")
    assert extract.query("jinja2", "3.1.6") == []
    assert extract.query("requests", "2.25.0")
    assert extract.query("urllib3", "1.26.4")


def test_ordre_des_versions_comme_packaging() -> None:
    """Notre clé d'ordre donne le même classement que `packaging` sur toutes les versions."""
    extract = osv.load_extract(OSV_DIR)
    versions: set[str] = set()
    for record in extract.records.values():
        for entry in record["affected"]:
            versions.update(entry.get("versions", []))
            for rng in entry.get("ranges", []):
                for event in rng["events"]:
                    versions.update(v for v in event.values() if v != "0")
    parsable = []
    for text in versions:
        try:
            parsable.append((Version(text), text))
        except InvalidVersion:
            continue
    assert len(parsable) > 50
    ours = sorted((t for _, t in parsable), key=lambda t: osv.version_key(t))
    theirs = [t for _, t in sorted(parsable)]
    assert [Version(t) for t in ours] == [Version(t) for t in theirs]


@pytest.mark.parametrize(
    ("low", "high"),
    [
        ("1.0.dev1", "1.0a1"),
        ("1.0a1", "1.0b1"),
        ("1.0rc1", "1.0"),
        ("1.0", "1.0.post1"),
        ("1.0", "1.0.1"),
        ("0.9", "1.0"),
        ("2.0", "1!0.1"),
        ("1.0", "1.0.0.1"),
        ("1.0", "1.0+local"),
        ("1.0+abc", "1.0+1"),
        ("1.0+1", "1.0+1.a"),
        ("1.0+local", "1.0.post1"),
    ],
)
def test_cle_de_version(low: str, high: str) -> None:
    assert Version(low) < Version(high)  # l'oracle est `packaging`, pas notre clé
    assert osv.version_key(low) < osv.version_key(high)
    assert osv.version_key("1.0") == osv.version_key("1.0.0")
    assert osv.version_key("pas une version") is None


def _record(events: list[dict], versions: list[str] | None = None) -> dict:
    return {
        "id": "TEST-1",
        "affected": [
            {
                "package": {"name": "x", "ecosystem": "PyPI"},
                "ranges": [{"type": "ECOSYSTEM", "events": events}],
                "versions": versions or [],
            }
        ],
    }


def test_partie_locale_apres_last_affected() -> None:
    """`1.0+local` est postérieure à `1.0` (packaging) : hors d'une plage `last_affected: 1.0`."""
    record = _record([{"introduced": "0"}, {"last_affected": "1.0"}])
    assert osv._is_affected(record, "x", "1.0") is True
    assert osv._is_affected(record, "x", "1.0+local") is False


def test_evenement_illisible_echec_ferme() -> None:
    """Un `introduced` illisible ne doit pas faire disparaître la vulnérabilité."""
    record = _record([{"introduced": "n'importe quoi"}, {"fixed": "2.0"}])
    assert osv._is_affected(record, "x", "1.0") is True
    assert osv._is_affected(_record([{"introduced": "0"}]), "x", "pas une version") is True


def test_liste_versions_comparee_en_pep440() -> None:
    record = _record([], versions=["1.0.0"])
    assert osv._is_affected(record, "x", "1.0") is True
    assert osv._is_affected(record, "x", "1.0.1") is False


# --- Le point HTTP ---------------------------------------------------------------------------


def test_requete_pip_audit_version_vulnerable(instance: cli.Instance) -> None:
    status, body = query(instance, "jinja2", "3.1.2")
    assert status == 200
    ids = {v["id"] for v in body["vulns"]}
    assert "GHSA-cpwx-vrp4-4pq7" in ids
    record = next(v for v in body["vulns"] if v["id"] == "GHSA-cpwx-vrp4-4pq7")
    on_disk = json.loads((OSV_DIR / "vulns" / "GHSA-cpwx-vrp4-4pq7.json").read_text("utf-8"))
    assert record == on_disk


def test_nom_non_normalise_et_version_corrigee(instance: cli.Instance) -> None:
    assert query(instance, "Jinja2", "3.1.2")[1]["vulns"]
    assert query(instance, "jinja2", "3.1.6") == (200, {})


def test_version_absente_renvoie_tous_les_enregistrements_du_paquet(
    instance: cli.Instance,
) -> None:
    meta = json.loads((OSV_DIR / "index.json").read_text(encoding="utf-8"))
    status, body = query(instance, "jinja2", None)
    assert status == 200
    assert {v["id"] for v in body["vulns"]} == set(meta["packages"]["jinja2"])


def test_paquet_inconnu_ou_autre_ecosysteme(instance: cli.Instance) -> None:
    assert query(instance, "paquet-qui-n-existe-pas", "1.0") == (200, {})
    other = {"package": {"name": "jinja2", "ecosystem": "npm"}, "version": "3.1.2"}
    status, raw = call(instance, "POST", json.dumps(other))
    assert (status, json.loads(raw)) == (200, {})


def test_purl(instance: cli.Instance) -> None:
    body = {"package": {"purl": "pkg:pypi/jinja2@3.1.2"}}
    status, raw = call(instance, "POST", json.dumps(body))
    assert status == 200
    assert json.loads(raw)["vulns"]


@pytest.mark.parametrize(
    "body",
    [b"pas du json", b"[]", b"{}", b'{"package": {"name": "jinja2"}}', b'{"package": 3}', b""],
)
def test_corps_invalide(instance: cli.Instance, body: bytes) -> None:
    status, raw = call(instance, "POST", body)
    assert status == 400
    assert "message" in json.loads(raw)


def test_corps_trop_gros(instance: cli.Instance) -> None:
    status, _ = call(instance, "POST", b" " * (osv.MAX_BODY_BYTES + 1))
    assert status == 413


def test_corps_trop_gros_annonce_refuse_sans_le_lire(instance: cli.Instance) -> None:
    conn = http.client.HTTPConnection(cli.HOST, instance.port, timeout=10)
    conn.putrequest("POST", "/osv/v1/query")
    conn.putheader("Content-Length", str(500 * 1024 * 1024))
    conn.endheaders()
    conn.send(b"{}")
    assert conn.getresponse().status == 413


def test_corps_trop_gros_sans_longueur_coupe_au_flux(instance: cli.Instance) -> None:
    """Corps envoyé par morceaux (`chunked`, sans `Content-Length`) : coupé à la limite."""
    chunk = b" " * 16 * 1024
    conn = http.client.HTTPConnection(cli.HOST, instance.port, timeout=10)
    conn.request("POST", "/osv/v1/query", body=iter([chunk] * 8), encode_chunked=True)
    assert conn.getresponse().status == 413
    status, raw = call(
        instance, "POST", iter([b'{"package": {"name": "jinja2", ', b'"ecosystem": "PyPI"}}'])
    )
    assert status == 200 and json.loads(raw)["vulns"]


def test_json_trop_imbrique_400(instance: cli.Instance) -> None:
    status, _ = call(instance, "POST", b"[" * 50_000)
    assert status == 400


@pytest.mark.parametrize("method", ["GET", "PUT", "DELETE", "PATCH", "HEAD"])
def test_autre_methode_refusee(instance: cli.Instance, method: str) -> None:
    status, _ = call(instance, method)
    assert status == 405
    assert call(instance, "GET", path="/osv/")[0] == 405


def test_sans_cookie_ni_origine(instance: cli.Instance) -> None:
    """Le point est public : aucun cookie, aucune origine, et ses réponses n'ouvrent pas CORS.

    Une page web d'une autre origine (le navigateur ajoute `Origin`) est refusée.
    """
    assert call(instance, "POST", "{}")[0] == 400  # corps invalide, mais pas 401 ni 403
    conn = http.client.HTTPConnection(cli.HOST, instance.port, timeout=10)
    conn.request("POST", "/osv/v1/query", body="{}", headers={"Origin": "http://autre.example"})
    resp = conn.getresponse()
    resp.read()
    assert resp.status == 403
    assert not [n for n, _ in resp.getheaders() if n.lower().startswith("access-control")]
    assert call(instance, "GET", path="/api/health")[0] == 401  # le reste exige le cookie


def test_host_controle(instance: cli.Instance) -> None:
    status, _ = call(instance, "POST", "{}", headers={"Host": "evil.example"})
    assert status == 403


def test_autre_chemin_sous_osv_inconnu(instance: cli.Instance) -> None:
    assert call(instance, "POST", "{}", path="/osv/v2/query")[0] == 404


def test_extrait_absent_refuse_au_lieu_de_repondre_propre(tmp_path: Path) -> None:
    assert osv.load_extract(tmp_path).available is False
    assert osv.answer(osv.load_extract(tmp_path), b"{}")[0] == 503


def test_url_osv_depuis_les_reglages() -> None:
    assert Settings().osv_url(4242) == "http://127.0.0.1:4242/osv/v1/query"


def test_reponses_pendant_qu_un_outil_tourne(instance: cli.Instance) -> None:
    """Une requête OSV n'attend pas une opération longue : pas de verrou, pas de file."""
    results: list[int] = []

    def worker() -> None:
        results.append(query(instance, "urllib3", "1.26.4")[0])

    threads = [threading.Thread(target=worker) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=10)
    assert results == [200] * 8


# --- pip-audit pour de vrai ---------------------------------------------------------------


def _pip_audit(inst: cli.Instance, tmp_path: Path, pins: str, *extra: str) -> tuple[int, str]:
    pytest.importorskip("pip_audit")
    req = tmp_path / "requirements.txt"
    req.write_text(pins, encoding="utf-8", newline="\n")
    env = {
        k: v
        for k, v in os.environ.items()
        if k.upper() not in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY")
    }
    env["NO_PROXY"] = "127.0.0.1,localhost"
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "pip_audit",
            "--vulnerability-service",
            "osv",
            "--osv-url",
            Settings().osv_url(inst.port),
            "--no-deps",
            "--disable-pip",
            "-r",
            str(req),
            "--cache-dir",
            str(tmp_path / "cache"),
            *extra,
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=env,
        timeout=120,
        check=False,
    )
    return proc.returncode, proc.stdout


def test_pip_audit_bout_en_bout_vulnerable(instance: cli.Instance, tmp_path: Path) -> None:
    code, out = _pip_audit(instance, tmp_path, "jinja2==3.1.2\n", "-f", "json")
    assert code == 1
    deps = json.loads(out)["dependencies"]
    assert deps[0]["name"] == "jinja2"
    vulns = deps[0]["vulns"]
    # pip-audit garde l'identifiant PYSEC et range les GHSA équivalents dans `aliases`.
    names = {v["id"] for v in vulns} | {a for v in vulns for a in v["aliases"]}
    assert "GHSA-cpwx-vrp4-4pq7" in names
    assert all(v["fix_versions"] for v in vulns)


def test_pip_audit_bout_en_bout_propre_et_sbom(instance: cli.Instance, tmp_path: Path) -> None:
    code, out = _pip_audit(instance, tmp_path, "jinja2==3.1.6\n", "-f", "cyclonedx-json")
    assert code == 0
    bom = json.loads(out)
    assert any(c["name"] == "jinja2" for c in bom["components"])


# --- Script de maintenance ------------------------------------------------------------------


def test_script_de_maintenance_ecrit_extrait_et_date(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Le script (seul à contacter OSV) écrit l'extrait et sa date ; le réseau est simulé ici."""
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "update_osv", project_root() / "scripts" / "update_osv.py"
    )
    assert spec and spec.loader
    script = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(script)

    fake = {"id": "GHSA-test", "affected": [{"package": {"name": "x", "ecosystem": "PyPI"}}]}
    withdrawn = {"id": "GHSA-old", "withdrawn": "2025-01-01T00:00:00Z"}
    monkeypatch.setattr(
        script, "query_package", lambda name: [fake, withdrawn] if name == "x" else []
    )
    meta = script.update(["x", "y"], "2030-01-02", tmp_path)
    assert meta["extracted_on"] == "2030-01-02"
    assert meta["packages"] == {"x": ["GHSA-test"], "y": []}
    assert [p.name for p in (tmp_path / "vulns").glob("*.json")] == ["GHSA-test.json"]
    assert osv.load_extract(tmp_path).extracted_on == "2030-01-02"
    assert "inventory" not in script.template_packages()
    assert "jinja2" in script.template_packages()

    # Coupure réseau en cours de mise à jour : l'ancien extrait reste entier et lisible.
    def cut(name: str) -> list[dict]:
        if name == "y":
            raise OSError("réseau coupé")
        return [{"id": "GHSA-new", "affected": []}]

    monkeypatch.setattr(script, "query_package", cut)
    with pytest.raises(OSError):
        script.update(["x", "y"], "2031-01-01", tmp_path)
    assert osv.load_extract(tmp_path).extracted_on == "2030-01-02"
    assert [p.name for p in (tmp_path / "vulns").glob("*.json")] == ["GHSA-test.json"]
    assert sorted(p.name for p in tmp_path.iterdir()) == ["index.json", "vulns"]
