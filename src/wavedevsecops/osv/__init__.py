"""Point OSV local : répond à `POST /osv/v1/query` depuis l'extrait figé de `content/osv/` (AD-11).

pip-audit est lancé pour de vrai, pointé sur ce point (`--vulnerability-service osv --osv-url`).
L'extrait (`index.json` + `vulns/<id>.json`, enregistrements OSV copiés tels quels) est lu une
fois, en mémoire : une requête ne touche ni le disque, ni un verrou, ni une file, et ne sort
jamais sur le réseau. Le module n'importe rien du projet.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

ECOSYSTEM = "PyPI"
MAX_BODY_BYTES = 64 * 1024
INDEX_FILE = "index.json"
VULNS_DIR = "vulns"

_VERSION = re.compile(
    r"""^\s*v?
    (?:(?P<epoch>\d+)!)?
    (?P<release>\d+(?:\.\d+)*)
    (?:[-_.]?(?P<pre_l>alpha|a|beta|b|preview|pre|c|rc)[-_.]?(?P<pre_n>\d+)?)?
    (?:(?:-(?P<post_n1>\d+))|(?:[-_.]?(?P<post_l>post|rev|r)[-_.]?(?P<post_n2>\d+)?))?
    (?:[-_.]?(?P<dev_l>dev)[-_.]?(?P<dev_n>\d+)?)?
    (?:\+(?P<local>[a-z0-9]+(?:[-_.][a-z0-9]+)*))?\s*$""",
    re.VERBOSE | re.IGNORECASE,
)
_PRE = {"alpha": "a", "a": "a", "beta": "b", "b": "b", "preview": "rc", "pre": "rc", "c": "rc"}
_DEV_ONLY, _FINAL = (0, "", 0), (2, "", 0)


def normalize(name: str) -> str:
    """Nom de paquet normalisé (PEP 503)."""
    return re.sub(r"[-_.]+", "-", name).lower()


def version_key(text: str) -> tuple | None:
    """Clé d'ordre PEP 440 d'une version (partie locale comprise), ou `None` si illisible."""
    m = _VERSION.match(text)
    if m is None:
        return None
    release = [int(part) for part in m["release"].split(".")]
    while len(release) > 1 and release[-1] == 0:
        release.pop()
    pre_label = m["pre_l"].lower() if m["pre_l"] else None
    pre_label = _PRE.get(pre_label, pre_label) if pre_label else None
    pre = (pre_label, int(m["pre_n"] or 0)) if pre_label else None
    post_n = m["post_n1"] or (m["post_n2"] if m["post_l"] else None)
    post = int(post_n) if post_n is not None else (0 if m["post_l"] else None)
    dev = int(m["dev_n"] or 0) if m["dev_l"] else None
    if pre is None and post is None and dev is not None:
        pre_key: tuple = _DEV_ONLY  # « 1.0.dev1 » précède « 1.0a1 »
    elif pre is None:
        pre_key = _FINAL
    else:
        pre_key = (1, *pre)
    return (
        int(m["epoch"] or 0),
        tuple(release),
        pre_key,
        -1 if post is None else post,
        10**9 if dev is None else dev,
        _local_key(m["local"]),
    )


def _local_key(local: str | None) -> tuple:
    """Partie locale : absente avant présente ; segment numérique après alphanumérique."""
    if not local:
        return ()
    parts = re.split(r"[-_.]", local.lower())
    return tuple((1, int(p), "") if p.isdigit() else (0, 0, p) for p in parts)


def _in_range(key: tuple, events: list[dict]) -> bool:
    """Évalue les évènements d'une plage OSV (`introduced`, `fixed`, `last_affected`).

    Un évènement illisible rend la version affectée (échec fermé : un faux négatif est le
    pire cas pour un outil de sécurité).
    """
    parsed: list[tuple[tuple, str, str]] = []
    for event in events:
        for kind in ("introduced", "fixed", "last_affected"):
            if kind in event:
                raw = str(event[kind])
                ev_key = (0, (0,), _DEV_ONLY, -1, 0, ()) if raw == "0" else version_key(raw)
                if ev_key is None:
                    return True
                parsed.append((ev_key, kind, raw))
    parsed.sort(key=lambda item: item[0])
    affected = False
    for ev_key, kind, _raw in parsed:
        if kind == "introduced":
            if key >= ev_key:
                affected = True
        elif kind == "fixed":
            if key >= ev_key:
                affected = False
        elif key > ev_key:  # last_affected
            affected = False
    return affected


def _is_affected(record: dict, name: str, version: str | None) -> bool:
    key = version_key(version) if version is not None else None
    for entry in record.get("affected", []):
        package = entry.get("package", {})
        if package.get("ecosystem") != ECOSYSTEM or normalize(package.get("name", "")) != name:
            continue
        if version is None or version in entry.get("versions", []):
            return True
        if key is None:
            # Version demandée illisible : affectée dès qu'une plage existe (échec fermé).
            if entry.get("ranges"):
                return True
            continue
        if any(version_key(str(v)) == key for v in entry.get("versions", [])):
            return True
        for rng in entry.get("ranges", []):
            if rng.get("type") in ("ECOSYSTEM", "SEMVER") and _in_range(key, rng["events"]):
                return True
    return False


@dataclass(frozen=True)
class Extract:
    """L'extrait OSV chargé en mémoire. Immuable : lisible sans verrou par tous les threads."""

    extracted_on: str = ""
    source: str = ""
    packages: dict[str, tuple[str, ...]] = field(default_factory=dict)
    records: dict[str, dict] = field(default_factory=dict)

    @property
    def available(self) -> bool:
        return bool(self.extracted_on)

    def query(self, name: str, version: str | None) -> list[dict]:
        """Enregistrements du paquet touchant `version` (tous, si `version` est absente)."""
        wanted = normalize(name)
        found = (self.records[i] for i in self.packages.get(wanted, ()) if i in self.records)
        return [record for record in found if _is_affected(record, wanted, version)]


def load_extract(directory: Path) -> Extract:
    """Charge `directory/index.json` et `directory/vulns/*.json`. Extrait vide si absent."""
    try:
        meta = json.loads((directory / INDEX_FILE).read_text(encoding="utf-8"))
        packages = {normalize(n): tuple(ids) for n, ids in meta["packages"].items()}
        records: dict[str, dict] = {}
        for ids in packages.values():
            for vuln_id in ids:
                if vuln_id not in records:
                    path = directory / VULNS_DIR / f"{vuln_id}.json"
                    records[vuln_id] = json.loads(path.read_text(encoding="utf-8"))
        return Extract(str(meta["extracted_on"]), str(meta.get("source", "")), packages, records)
    except OSError, ValueError, KeyError, TypeError, AttributeError:
        return Extract()


def answer(extract: Extract, body: bytes) -> tuple[int, dict]:
    """Réponse (statut, JSON) à un corps `POST /v1/query` : `{"vulns": [...]}` ou `{}`."""
    if not extract.available:
        return 503, {"code": 14, "message": "Base de vulnérabilités locale absente."}
    try:
        query = json.loads(body)
    except ValueError, RecursionError:
        return 400, {"code": 3, "message": "Corps de requête invalide : JSON attendu."}
    package = query.get("package") if isinstance(query, dict) else None
    version = query.get("version") if isinstance(query, dict) else None
    if not isinstance(package, dict) or not (version is None or isinstance(version, str)):
        return 400, {"code": 3, "message": "Requête invalide : `package` et `version` attendus."}
    name, ecosystem = package.get("name"), package.get("ecosystem")
    purl = package.get("purl")
    if isinstance(purl, str) and (m := re.match(r"^pkg:pypi/([^@?#]+)(?:@([^?#]+))?", purl, re.I)):
        name, ecosystem = m[1], ECOSYSTEM
        version = version or m[2]
    if not isinstance(name, str) or not name or not isinstance(ecosystem, str):
        return 400, {"code": 3, "message": "Requête invalide : nom et écosystème attendus."}
    if ecosystem.lower() != ECOSYSTEM.lower():
        return 200, {}
    vulns = extract.query(name, version or None)
    return 200, {"vulns": vulns} if vulns else {}
