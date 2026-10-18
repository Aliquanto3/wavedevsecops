"""Fichiers d'un espace de travail : chemins confinés, écritures LF et atomiques (AD-3, AD-5).

Seul `wsfs` lit ou écrit un fichier d'un bac à sable pour le compte de l'apprenant, du
terminal, de la vue Code ou du setup (règles de dépendance du spine). Il n'importe que
`config` et `contracts`, et ne lance aucun processus.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import stat
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any

from wavedevsecops.contracts import AppError

GIT_DIR_NAMES = frozenset({".git"})
_SHORT_GIT = re.compile(r"^git~\d+$")
"""Nom court 8.3 de `.git` sous Windows (`GIT~1`)."""
_RESERVED = re.compile(r"^(con|prn|aux|nul|com[0-9]|lpt[0-9])(\..*)?$")
"""Noms de périphérique réservés par Windows, avec ou sans extension."""


def _is_git_dir(part: str) -> bool:
    """`.git` tel que Windows le comprend : casse, points et espaces finaux, nom court."""
    name = part.rstrip(". ").lower()
    return name in GIT_DIR_NAMES or bool(_SHORT_GIT.match(name))


class SandboxPathError(AppError):
    """Chemin refusé : absolu, qui sort de l'espace, ou dans `.git/`."""

    def __init__(self, path: str, why: str) -> None:
        super().__init__(
            f"Le chemin « {path} » est refusé : {why}.",
            "Utilisez un chemin relatif au dépôt, en notation posix (par exemple src/app.py).",
        )
        self.path = path


SNAPSHOT_ENTRIES = ("repo", "origin.git", "github.json", "hooks")
"""Entrées d'un espace copiées par un instantané et remplacées par une restauration (AD-6)."""


@dataclass(frozen=True)
class Layout:
    """Disposition d'un espace `<data>/workspaces/<parcours>/<scenario_id>.<mode>/` (AD-5)."""

    root: Path

    @classmethod
    def for_scenario(cls, workspaces: Path, track: str, scenario_id: str, mode: str) -> Layout:
        return cls(workspaces / track / f"{scenario_id}.{mode}")

    @property
    def track(self) -> str:
        """Parcours de l'espace (`llm` ou `no_ai`) : le dossier qui contient `root`."""
        return self.root.parent.name

    @property
    def repo(self) -> Path:
        return self.root / "repo"

    @property
    def origin(self) -> Path:
        return self.root / "origin.git"

    @property
    def hooks(self) -> Path:
        return self.root / "hooks"

    @property
    def run_json(self) -> Path:
        return self.root / "run.json"

    @property
    def github_json(self) -> Path:
        return self.root / "github.json"

    @property
    def snapshots(self) -> Path:
        return self.root / "snapshots"

    def entries(self) -> tuple[Path, ...]:
        """Chemins couverts par un instantané (AD-6), dans l'ordre de `SNAPSHOT_ENTRIES`."""
        return tuple(self.root / name for name in SNAPSHOT_ENTRIES)

    @property
    def ci(self) -> Path:
        return self.root / "ci"

    @property
    def cache(self) -> Path:
        return self.root / "cache"


def check_relative(path: str, *, portable: bool = True) -> PurePosixPath:
    """Valide un chemin relatif posix sans `..`, hors de `.git/`.

    `portable` (écritures) refuse aussi `\\` et `:`, les noms réservés de Windows (`NUL`,
    `con.txt`) et les noms finis par un point ou une espace. Une lecture les admet : un
    fichier créé ainsi sous Linux doit rester lisible pour l'empreinte.
    """
    if not path or not path.strip():
        raise SandboxPathError(path, "il est vide")
    if "\0" in path:
        raise SandboxPathError(path, "il contient un caractère nul")
    if portable and ("\\" in path or ":" in path):
        raise SandboxPathError(path, "il contient « \\ » ou « : »")
    pure = PurePosixPath(path)
    if pure.is_absolute():
        raise SandboxPathError(path, "il est absolu")
    if any(part == ".." for part in pure.parts):
        raise SandboxPathError(path, "il remonte hors du dépôt (« .. »)")
    if any(_is_git_dir(part) for part in pure.parts):
        raise SandboxPathError(path, "il désigne le dossier interne de git")
    if not pure.parts or pure.parts == (".",):
        raise SandboxPathError(path, "il ne désigne aucun fichier")
    if portable and any(
        _RESERVED.match(part.lower()) or part.endswith((".", " ")) for part in pure.parts
    ):
        raise SandboxPathError(path, "il contient un nom réservé ou non portable sous Windows")
    return pure


def confine(root: Path, path: str, *, portable: bool = True) -> Path:
    """Chemin absolu de `path` sous `root`, après résolution des liens (refus s'il en sort)."""
    pure = check_relative(path, portable=portable)
    base = root.resolve()
    target = (base / Path(*pure.parts)).resolve()
    if target != base and not target.is_relative_to(base):
        raise SandboxPathError(path, "il sort de l'espace de travail")
    # Après résolution (liens, noms courts, points finaux) : jamais dans `.git/`.
    if any(_is_git_dir(part) for part in target.relative_to(base).parts):
        raise SandboxPathError(path, "il désigne le dossier interne de git")
    return target


def to_lf(text: str) -> str:
    """Fins de ligne en LF (AD-3)."""
    return text.replace("\r\n", "\n").replace("\r", "\n")


REPLACE_ATTEMPTS = 3
"""Essais de `os.replace` : sous Windows, un lecteur qui tient la cible le refuse un instant."""
REPLACE_PAUSE_S = 0.05


def _replace(tmp: str, target: Path) -> None:
    for attempt in range(1, REPLACE_ATTEMPTS + 1):
        try:
            os.replace(tmp, target)
            return
        except PermissionError:
            if os.name != "nt" or attempt == REPLACE_ATTEMPTS:
                raise
            time.sleep(REPLACE_PAUSE_S * attempt)


def _atomic_write(target: Path, data: bytes) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".wds-", suffix=".tmp", dir=target.parent)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
        _replace(tmp, target)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


def write_text(root: Path, path: str, text: str) -> Path:
    """Écrit `text` en UTF-8 et LF dans `root/path`, de façon atomique."""
    target = confine(root, path)
    _atomic_write(target, to_lf(text).encode("utf-8"))
    return target


def read_bytes(root: Path, path: str) -> bytes | None:
    """Contenu de `root/path`, ou `None` s'il n'existe pas ou n'est pas un fichier."""
    target = confine(root, path, portable=False)
    try:
        return target.read_bytes() if target.is_file() else None
    except OSError:
        return None


SYMLINK_PREFIX = b"symlink:"


def read_entry(root: Path, path: str) -> bytes | None:
    """Contenu d'une entrée de l'arbre pour l'empreinte (AD-6), sans jamais suivre un lien.

    Un lien symbolique vaut sa cible écrite (comme git la stocke), même s'il sort de
    l'espace ou vise `.git/` ; une entrée illisible ou hors de l'espace vaut `None`.
    """
    pure = check_relative(path, portable=False)
    try:
        parent = root.resolve() if len(pure.parts) == 1 else confine(
            root, pure.parent.as_posix(), portable=False
        )
    except SandboxPathError:
        return None
    entry = parent / pure.name
    try:
        if entry.is_symlink():
            return SYMLINK_PREFIX + os.fsencode(os.readlink(entry))
    except OSError:
        return None
    try:
        return read_bytes(root, path)
    except SandboxPathError:
        return None


def make_dirs(path: Path) -> None:
    """Crée un dossier de l'espace (et ses parents)."""
    path.mkdir(parents=True, exist_ok=True)


def iter_files(root: Path) -> list[str]:
    """Fichiers réguliers sous `root`, en chemins posix relatifs triés (dossier absent : [])."""
    if not root.is_dir():
        return []
    return sorted(p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file())


def canonical_json(data: Any) -> str:
    """JSON trié, indenté, UTF-8 et LF, terminé par un saut de ligne (convention du spine)."""
    return json.dumps(data, ensure_ascii=False, sort_keys=True, indent=2) + "\n"


def write_json(target: Path, data: Any) -> None:
    """Écrit un fichier de données de l'espace (`run.json`…) de façon atomique."""
    _atomic_write(target, canonical_json(data).encode("utf-8"))


def _clear_readonly(func: Any, path: str, _exc: BaseException) -> None:
    """Les objets git sont en lecture seule sous Windows : on lève le drapeau puis on réessaie."""
    os.chmod(path, stat.S_IWRITE)
    func(path)


def remove_tree(path: Path) -> None:
    """Supprime un espace (ou un de ses dossiers) ; absent : rien à faire."""
    if path.exists():
        shutil.rmtree(path, onexc=_clear_readonly)


def remove_entry(path: Path) -> None:
    """Supprime un fichier ou un dossier de l'espace ; absent : rien à faire."""
    if path.is_dir() and not path.is_symlink():
        remove_tree(path)
    elif os.path.lexists(path):
        try:
            path.unlink()
        except PermissionError:
            os.chmod(path, stat.S_IWRITE)
            path.unlink()


GIT_LOCKS = frozenset({"index.lock", "HEAD.lock"})
"""Verrous de git jamais copiés : un verrou périmé bloquerait le dépôt rétabli (AD-12)."""


def _skip_git_locks(directory: str, names: list[str]) -> set[str]:
    if os.path.basename(directory) in (".git", "origin.git"):
        return GIT_LOCKS.intersection(names)
    return set()


def copy_entries(source: Path, names: tuple[str, ...], target: Path) -> None:
    """Copie dans `target` (créé au besoin) ceux des `names` présents sous `source`.

    Les dossiers sont copiés en entier, liens symboliques compris (jamais suivis), sans les
    verrous de git (`GIT_LOCKS`) de `.git/` et `origin.git/`. Une copie interrompue reste
    partielle : l'appelant la supprime (instantanés, AD-6).
    """
    target.mkdir(parents=True, exist_ok=True)
    for name in names:
        entry = source / name
        if entry.is_dir() and not entry.is_symlink():
            shutil.copytree(entry, target / name, symlinks=True, ignore=_skip_git_locks)
        elif os.path.lexists(entry):
            shutil.copy2(entry, target / name, follow_symlinks=False)


MOVE_ATTEMPTS = 3
"""Essais d'un renommage de restauration : un fichier tenu ouvert (Windows) le refuse."""


def move(
    source: Path,
    target: Path,
    *,
    attempts: int = MOVE_ATTEMPTS,
    pause_s: float = 0.2,
    sleep: Any = time.sleep,
) -> None:
    """Renomme `source` en `target` (même volume), avec `attempts` essais espacés.

    Entre deux essais refusés (`PermissionError`, verrou de fichier sous Windows), la pause
    croît : `pause_s`, puis `2 × pause_s`… Le dernier refus est levé. `target` ne doit pas
    exister : un renommage ne remplace jamais une entrée.
    """
    if os.path.lexists(target):
        raise FileExistsError(f"cible déjà présente : {target}")
    target.parent.mkdir(parents=True, exist_ok=True)
    for attempt in range(1, attempts + 1):
        try:
            os.rename(source, target)
            return
        except PermissionError:
            if attempt >= attempts:
                raise
            sleep(pause_s * attempt)
