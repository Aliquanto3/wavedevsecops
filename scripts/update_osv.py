"""Met à jour l'extrait OSV figé de `content/osv/` (AD-11). À lancer par le mainteneur.

C'est le seul endroit qui contacte `api.osv.dev` : l'application et les tests ne téléchargent
jamais rien. Le script relit les paquets des gabarits d'exercice (`content/exercise/*/uv.lock`),
interroge OSV pour chacun (tous les enregistrements du paquet, toutes versions), copie chaque
enregistrement tel que renvoyé dans `content/osv/vulns/<id>.json`, et écrit
`content/osv/index.json` (date de l'extrait, source, paquets -> identifiants).

    uv run python scripts/update_osv.py [--date AAAA-MM-JJ] [--package nom ...]

Les enregistrements retirés (`withdrawn`) sont ignorés. Les données OSV sont sous licence
CC-BY 4.0 pour la plupart des sources : voir `content/osv/ATTRIBUTION.md`.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import tomllib
import urllib.request
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OSV_DIR = ROOT / "content" / "osv"
QUERY_URL = "https://api.osv.dev/v1/query"
SOURCE = "https://api.osv.dev"
TIMEOUT_S = 60


def normalize(name: str) -> str:
    """Nom de paquet normalisé (PEP 503)."""
    return re.sub(r"[-_.]+", "-", name).lower()


def template_packages(root: Path = ROOT) -> list[str]:
    """Paquets (hors le projet lui-même) des `uv.lock` de `content/exercise/*/`."""
    names: set[str] = set()
    for lock in sorted((root / "content" / "exercise").glob("*/uv.lock")):
        data = tomllib.loads(lock.read_text(encoding="utf-8"))
        project = tomllib.loads((lock.parent / "pyproject.toml").read_text(encoding="utf-8"))
        own = normalize(project["project"]["name"])
        names.update(normalize(p["name"]) for p in data.get("package", []))
        names.discard(own)
    return sorted(names)


def query_package(name: str) -> list[dict]:
    """Tous les enregistrements OSV d'un paquet PyPI (pages comprises)."""
    records: list[dict] = []
    token = None
    while True:
        body: dict = {"package": {"name": name, "ecosystem": "PyPI"}}
        if token:
            body["page_token"] = token
        req = urllib.request.Request(
            QUERY_URL,
            data=json.dumps(body).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=TIMEOUT_S) as resp:
            page = json.load(resp)
        records.extend(page.get("vulns", []))
        token = page.get("next_page_token")
        if not token:
            return records


def write_json(path: Path, value: object) -> None:
    text = json.dumps(value, indent=1, ensure_ascii=False) + "\n"
    path.write_text(text, encoding="utf-8", newline="\n")


def update(packages: list[str], extracted_on: str, out: Path = OSV_DIR) -> dict:
    vulns_dir = out / "vulns"
    vulns_dir.mkdir(parents=True, exist_ok=True)
    for old in vulns_dir.glob("*.json"):
        old.unlink()
    index: dict[str, list[str]] = {}
    for name in packages:
        ids: set[str] = set()
        for record in query_package(name):
            if record.get("withdrawn"):
                continue
            write_json(vulns_dir / f"{record['id']}.json", record)
            ids.add(record["id"])
        index[name] = sorted(ids)
        print(f"{name}: {len(ids)} enregistrement(s)")
    meta = {
        "extracted_on": extracted_on,
        "source": SOURCE,
        "license": "CC-BY-4.0 (voir ATTRIBUTION.md)",
        "packages": index,
    }
    write_json(out / "index.json", meta)
    return meta


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--date", default=date.today().isoformat(), help="date de l'extrait")
    parser.add_argument("--package", action="append", help="paquet à ajouter à la liste")
    args = parser.parse_args(argv)
    packages = sorted({*template_packages(), *map(normalize, args.package or [])})
    update(packages, args.date)
    return 0


if __name__ == "__main__":
    sys.exit(main())
