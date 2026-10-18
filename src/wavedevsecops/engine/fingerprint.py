"""Empreinte canonique d'un espace (AD-6) et empreintes de référence (AD-18).

Empreinte : sha256 d'une sérialisation triée de l'état de l'espace :

- refs et cibles de `repo/` et `origin.git/`, HEAD compris (symbolique ou détaché) ;
- objets accessibles depuis les refs et le reflog ;
- entrées de l'index (mode, oid, étage, chemin) ;
- chemin et contenu (sha256) de chaque fichier suivi ou non ignoré de l'arbre de travail
  (un lien symbolique vaut sa cible écrite : il n'est jamais suivi) ;
- liste ordonnée du stash ;
- chemin et contenu de chaque fichier de `hooks/` ;
- `github.json` sérialisé de façon canonique, sans `checks[].output`, durées ni horodatages
  (`github_sim.canonical_digest`, son seul propriétaire).

Les dates de fichier, les fichiers ignorés, `ci/` et `cache/` en sont exclus. « Identique
octet pour octet » veut dire : même empreinte.
"""

from __future__ import annotations

import hashlib
import json
import tempfile
from pathlib import Path

from wavedevsecops import github_sim, gitio, wsfs
from wavedevsecops.config import Settings, get_settings
from wavedevsecops.gitio import Git
from wavedevsecops.wsfs import Layout

FINGERPRINTS_SCHEMA_VERSION = 1
FINGERPRINTS_FILE = "fingerprints.json"


def _digest(data: bytes | None) -> str:
    return "absent" if data is None else hashlib.sha256(data).hexdigest()


def canonical_records(layout: Layout, git: Git) -> list[str]:
    """Lignes triées de la sérialisation canonique (utile pour comparer deux espaces)."""
    records: list[str] = []
    for label, path in (("repo", layout.repo), ("origin", layout.origin)):
        records.append(f"{label} {gitio.head_record(git, path)}")
        records += [f"{label} ref {name} {target}" for name, target in gitio.refs(git, path)]
        records += [f"{label} object {oid}" for oid in gitio.reachable_objects(git, path)]
    records += [f"repo index {entry}" for entry in gitio.index_entries(git, layout.repo)]
    for rel in gitio.worktree_paths(git, layout.repo):
        records.append(f"repo worktree {rel} {_digest(wsfs.read_entry(layout.repo, rel))}")
    for position, sha in enumerate(gitio.stash_list(git, layout.repo)):
        records.append(f"repo stash {position} {sha}")
    for rel in wsfs.iter_files(layout.hooks):
        records.append(f"hooks {rel} {_digest(wsfs.read_entry(layout.hooks, rel))}")
    records.append(f"github {github_sim.canonical_digest(layout) or 'absent'}")
    return sorted(records)


def fingerprint(layout: Layout, git: Git) -> str:
    """Empreinte canonique de l'espace : sha256 hexadécimal."""
    payload = "\n".join(canonical_records(layout, git)) + "\n"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def reference_key(track: str, scenario_key: str) -> str:
    """Clé d'une empreinte de référence : `<parcours>/<scenario_id>.<mode>`."""
    return f"{track}/{scenario_key}"


def references_path(settings: Settings | None = None) -> Path:
    return (settings or get_settings()).content_path() / FINGERPRINTS_FILE


def load_references(settings: Settings | None = None) -> dict[str, str]:
    """Empreintes de référence de `content/fingerprints.json` (fichier absent : {})."""
    path = references_path(settings)
    if not path.is_file():
        return {}
    data = json.loads(path.read_bytes().decode("utf-8"))
    return dict(data.get("fingerprints", {}))


def compute_references(
    settings: Settings | None = None, git_path: Path | None = None
) -> dict[str, str]:
    """Prépare chaque scénario, pour chaque parcours, dans un dossier jetable ; rend les
    empreintes obtenues."""
    from wavedevsecops.engine.workspace import prepare_workspace, resolve_git
    from wavedevsecops.scenarios import load_scenario, scenario_files

    settings = settings or get_settings()
    git_path = git_path or resolve_git(settings)
    found: dict[str, str] = {}
    with tempfile.TemporaryDirectory(prefix="wds-fingerprints-", ignore_cleanup_errors=True) as tmp:
        scratch = settings.model_copy(update={"data_dir": Path(tmp)})
        for path in scenario_files(settings):
            loaded = load_scenario(path, settings)
            for track in loaded.scenario.tracks:
                prepared = prepare_workspace(loaded, track, settings=scratch, git_path=git_path)
                found[reference_key(track, loaded.scenario.key)] = prepared.fingerprint
    return dict(sorted(found.items()))


def write_references(values: dict[str, str], settings: Settings | None = None) -> Path:
    """Écrit `content/fingerprints.json` (JSON trié, LF)."""
    path = references_path(settings)
    wsfs.write_json(
        path,
        {
            "schema_version": FINGERPRINTS_SCHEMA_VERSION,
            "fingerprints": dict(sorted(values.items())),
        },
    )
    return path
