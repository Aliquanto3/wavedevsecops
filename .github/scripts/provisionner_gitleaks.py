"""Pose gitleaks (archive officielle, somme vérifiée par `checksums.txt`) dans `tools/gitleaks/`.

Équivalent, pour la CI des tests (story 7.3), de ce que font les installeurs (story 7.1) : le
test du vrai hook pre-commit lance le vrai gitleaks de `WDS_EXERCISE_DATA`. Seule étape réseau ;
les tests tournent ensuite hors ligne.

Usage : python provisionner_gitleaks.py <dossier de données>
"""

from __future__ import annotations

import hashlib
import io
import platform
import sys
import tarfile
import tomllib
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def main(data: Path) -> int:
    registry = tomllib.loads((ROOT / "tools.toml").read_text(encoding="utf-8"))
    version = next(t["provisioned_version"] for t in registry["tool"] if t["id"] == "gitleaks")
    windows = sys.platform == "win32"
    system = "windows" if windows else "darwin" if sys.platform == "darwin" else "linux"
    arch = "arm64" if platform.machine().lower() in {"arm64", "aarch64"} else "x64"
    name = f"gitleaks_{version}_{system}_{arch}." + ("zip" if windows else "tar.gz")
    base = f"https://github.com/gitleaks/gitleaks/releases/download/v{version}"
    archive = urllib.request.urlopen(f"{base}/{name}", timeout=120).read()  # noqa: S310
    sums = urllib.request.urlopen(f"{base}/gitleaks_{version}_checksums.txt", timeout=120).read()  # noqa: S310
    expected = next(
        line.split()[0] for line in sums.decode().splitlines() if line.endswith(f" {name}")
    )
    if hashlib.sha256(archive).hexdigest() != expected:
        print(f"Somme fausse pour {name}", file=sys.stderr)
        return 1
    target = data / "tools" / "gitleaks"
    target.mkdir(parents=True, exist_ok=True)
    exe = "gitleaks.exe" if windows else "gitleaks"
    if windows:
        content = zipfile.ZipFile(io.BytesIO(archive)).read(exe)
    else:
        with tarfile.open(fileobj=io.BytesIO(archive), mode="r:gz") as tar:
            member = tar.extractfile(exe)
            assert member is not None
            content = member.read()
    (target / exe).write_bytes(content)
    (target / exe).chmod(0o755)
    print(f"gitleaks {version} posé dans {target}")
    return 0


if __name__ == "__main__":
    sys.exit(main(Path(sys.argv[1])))
