"""Catalogue et ouverture d'un espace (Story 2.3), sur le vrai serveur et le vrai git."""

from __future__ import annotations

import http.client
import json
import time
from collections.abc import Iterator
from pathlib import Path

import pytest

from wavedevsecops import cli
from wavedevsecops.config import Settings
from wavedevsecops.web.catalogue import chain_body

WAIT_S = 60.0


@pytest.fixture
def instance(tmp_path: Path, git_path: Path) -> Iterator[cli.Instance]:
    inst = cli.start_instance(Settings(data_dir=tmp_path / "data"))
    try:
        yield inst
    finally:
        inst.stop()


@pytest.fixture
def cookie(instance: cli.Instance) -> dict[str, str]:
    conn = http.client.HTTPConnection(cli.HOST, instance.port, timeout=10)
    conn.request("GET", f"/?t={instance.token}")
    resp = conn.getresponse()
    resp.read()
    conn.close()
    return {"Cookie": resp.getheader("Set-Cookie", "").split(";")[0]}


def call(inst: cli.Instance, method: str, path: str, cookie: dict, body: object = None):
    headers = dict(cookie)
    data = None
    if method == "POST":
        headers["Origin"] = f"http://{cli.HOST}:{inst.port}"
        headers["Content-Type"] = "application/json"
        data = body if isinstance(body, bytes) else json.dumps(body).encode("utf-8")
    conn = http.client.HTTPConnection(cli.HOST, inst.port, timeout=WAIT_S)
    conn.request(method, path, body=data, headers=headers)
    resp = conn.getresponse()
    raw = resp.read()
    conn.close()
    is_json = resp.getheader("Content-Type", "").startswith("application/json")
    return resp.status, (json.loads(raw) if raw and is_json else raw)


def test_catalogue_liste_le_socle_git_avec_titres_et_modes(
    instance: cli.Instance, cookie: dict
) -> None:
    status, body = call(instance, "GET", "/api/catalogue", cookie)
    assert status == 200
    assert body["default_track"] == "no_ai"
    (section,) = body["sections"]
    assert section["title"] == "Socle git"
    by_id = {s["scenario_id"]: s for s in section["scenarios"]}
    assert "bac-a-sable-libre" in by_id
    # Les gabarits d'exercice (`catalogue: false`) sont internes : jamais proposés (revue 2.3).
    assert not {"gabarit-sans-ia", "gabarit-llm"} & by_id.keys()
    free = by_id["bac-a-sable-libre"]
    assert free["title"] == "Bac à sable libre"
    (mode,) = free["modes"]
    # Le parcours sans IA est le parcours par défaut quand le scénario le propose.
    assert mode == {
        "mode": "A",
        "tracks": ["llm", "no_ai"],
        "track": "no_ai",
        "workspace_id": "no_ai.bac-a-sable-libre.A",
    }


def test_catalogue_derriere_le_cookie(instance: cli.Instance) -> None:
    status, _ = call(instance, "GET", "/api/catalogue", {})
    assert status == 401
    status, _ = call(instance, "POST", "/api/open", {}, {"scenario_id": "x", "mode": "A"})
    assert status == 401


def test_ouvrir_un_mode_prepare_l_espace_puis_le_rouvre(
    instance: cli.Instance, cookie: dict
) -> None:
    workspace_id = "no_ai.bac-a-sable-libre.A"
    # Un espace jamais ouvert n'a pas d'en-tête à servir.
    status, _ = call(instance, "GET", f"/api/workspaces/{workspace_id}", cookie)
    assert status == 404
    status, opened = call(
        instance, "POST", "/api/open", cookie, {"scenario_id": "bac-a-sable-libre", "mode": "A"}
    )
    assert status == 202
    assert opened == {"workspace_id": workspace_id, "title": "Bac à sable libre", "preparing": True}
    # Double clic : la seconde demande voit la préparation en cours, sans second `setup`.
    status, twice = call(
        instance, "POST", "/api/open", cookie, {"scenario_id": "bac-a-sable-libre", "mode": "A"}
    )
    assert (status, twice["preparing"]) in {(202, True), (200, False)}
    status, _ = call(instance, "GET", f"/api/workspaces/{workspace_id}", cookie)
    assert status == 200

    # L'état de la projection arrive du serveur : repos atteint, `views` fourni (AD-2, AD-17).
    deadline = time.monotonic() + WAIT_S
    while True:
        status, state = call(instance, "GET", f"/api/ws/{workspace_id}/state", cookie)
        assert status == 200
        if state["state"] == "idle" and state["epoch"] >= 1:
            break
        assert time.monotonic() < deadline, state
        time.sleep(0.1)
    assert isinstance(state["views"], dict) and state["boot_id"]

    status, again = call(
        instance, "POST", "/api/open", cookie, {"scenario_id": "bac-a-sable-libre", "mode": "A"}
    )
    assert status == 200 and again["preparing"] is False
    # Un seul `setup` a tourné (un second aurait ouvert l'`epoch` 2).
    time.sleep(0.5)
    status, state = call(instance, "GET", f"/api/ws/{workspace_id}/state", cookie)
    assert (state["state"], state["epoch"]) == ("idle", 1), state

    status, info = call(instance, "GET", f"/api/workspaces/{workspace_id}", cookie)
    assert status == 200
    assert info == {
        "workspace_id": workspace_id,
        "scenario_id": "bac-a-sable-libre",
        "mode": "A",
        "track": "no_ai",
        "title": "Bac à sable libre",
        "chain": chain_body(1),
    }

    status, page = call(instance, "GET", f"/espace/{workspace_id}", cookie)
    assert status == 200 and b"<main" in page


def test_refus_d_ouverture(instance: cli.Instance, cookie: dict) -> None:
    status, body = call(instance, "POST", "/api/open", cookie, b"pas du json")
    assert status == 422 and "illisible" in body["reason_text"]
    status, body = call(
        instance, "POST", "/api/open", cookie, {"scenario_id": "absent", "mode": "A"}
    )
    assert status == 404 and "n'existe pas" in body["reason_text"]
    status, body = call(
        instance,
        "POST",
        "/api/open",
        cookie,
        {"scenario_id": "bac-a-sable-libre", "mode": "A", "track": "inconnu"},
    )
    assert status == 422 and "parcours" in body["reason_text"]
    # Un scénario interne ne s'ouvre pas depuis le catalogue.
    status, body = call(
        instance, "POST", "/api/open", cookie, {"scenario_id": "gabarit-llm", "mode": "A"}
    )
    assert status == 404
    status, body = call(instance, "GET", "/api/workspaces/..%2Fx", cookie)
    assert status == 404
    status, body = call(instance, "GET", "/api/workspaces/no_ai.absent.A", cookie)
    assert status == 404
    # Sans `Origin`, une ouverture est refusée (AD-19).
    conn = http.client.HTTPConnection(cli.HOST, instance.port, timeout=10)
    conn.request("POST", "/api/open", body=b"{}", headers=cookie)
    assert conn.getresponse().status == 403
    conn.close()


def test_bandeau_de_la_chaine_fourni_par_le_serveur() -> None:
    assert chain_body(None) is None and chain_body(0) is None and chain_body(5) is None
    chain = chain_body(3)
    assert chain is not None and chain["current"] == 3
    assert [s["text"] for s in chain["stations"]] == [
        "Station 1 · Poste local",
        "Station 2 · PR et CI",
        "Station 3 · Sécurité et qualité",
        "Station 4 · Livraison",
    ]
    assert (chain["here_text"], chain["boundary_text"], chain["boundary_after"]) == (
        "Vous êtes ici",
        "CI | CD",
        3,
    )
