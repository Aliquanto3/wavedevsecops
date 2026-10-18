"""Régénère `content/fingerprints.json` (AD-18) : empreinte de fin de setup de chaque scénario.

Usage : `uv run python scripts/update_fingerprints.py`

À lancer après l'ajout ou la modification d'un scénario, puis à committer. La CI compare
ces empreintes à celles obtenues sous Windows, macOS et Linux.
"""

from __future__ import annotations

from wavedevsecops.engine import compute_references, load_references, write_references


def main() -> int:
    before = load_references()
    after = compute_references()
    path = write_references(after)
    changed = sorted(k for k in after.keys() | before.keys() if before.get(k) != after.get(k))
    for key in changed:
        print(f"{key} : {before.get(key, '(absente)')} -> {after.get(key, '(retirée)')}")
    print(f"{len(after)} empreinte(s) écrite(s) dans {path} ; {len(changed)} changement(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
