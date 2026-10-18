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
_RESERVED = re.compile(r"^(con|prn|aux|nul|conin\$|conout\$|com[0-9¹²³]|lpt[0-9¹²³])(\..*)?$")
"""Noms de périphérique réservés par Windows, avec ou sans extension."""
_NOT_PORTABLE = re.compile(r'[\x00-\x1f"<>|]')
"""Caractères interdits dans un nom sous Windows (hors `*` et `?`, motifs des globs)."""


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
    if portable and _NOT_PORTABLE.search(path):
        raise SandboxPathError(path, "il contient un caractère interdit sous Windows")
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
        parent = (
            root.resolve()
            if len(pure.parts) == 1
            else confine(root, pure.parent.as_posix(), portable=False)
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


# --- Commandes de fichiers du terminal (story 2.5) -------------------------------------------
# Toutes passent par `confine` : aucun chemin du terminal n'atteint le disque sans lui.


class SandboxFileError(AppError):
    """Opération de fichier impossible dans l'espace (absent, déjà là, dossier non vide…)."""

    def __init__(self, cause: str, action: str = "Vérifiez le nom avec « ls ».") -> None:
        super().__init__(cause, action)


def _is_link(entry: Path) -> bool:
    """Lien symbolique ou jonction Windows : jamais suivi par une commande de fichier."""
    return entry.is_symlink() or entry.is_junction()


def _entry(root: Path, path: str, *, portable: bool = True) -> Path:
    """Entrée désignée par `path` sans suivre un lien final : un lien se supprime ou se
    déplace lui-même (jamais sa cible, qui peut sortir de l'espace)."""
    pure = check_relative(path, portable=portable)
    base = root.resolve()
    if len(pure.parts) == 1:
        return base / pure.name
    return confine(root, pure.parent.as_posix(), portable=portable) / pure.name


def list_dir(root: Path, path: str = ".", *, hidden: bool = False) -> list[tuple[str, bool]]:
    """Entrées `(nom, est_dossier)` triées d'un dossier de l'espace ; `.git` n'y figure jamais."""
    base = root.resolve() if path in ("", ".") else confine(root, path, portable=False)
    if not base.is_dir():
        raise SandboxFileError(f"« {path} » n'est pas un dossier.")
    entries = []
    for child in sorted(base.iterdir(), key=lambda p: p.name.lower()):
        if _is_git_dir(child.name) or (not hidden and child.name.startswith(".")):
            continue
        entries.append((child.name, child.is_dir() and not _is_link(child)))
    return entries


def kind_of(root: Path, path: str) -> str:
    """`file`, `dir`, `symlink` ou `missing` pour l'entrée `path` (sans suivre un lien final)."""
    entry = _entry(root, path, portable=False)
    # Une jonction Windows compte comme un lien : `rm`/`mv` agissent sur elle, `cp` la refuse.
    if _is_link(entry):
        return "symlink"
    if entry.is_dir():
        return "dir"
    return "file" if entry.exists() else "missing"


READ_LIMIT = 256 * 1024
"""Octets au plus lus par `cat` : au-delà, la sortie du terminal est tronquée."""


def read_text(root: Path, path: str, *, limit: int = READ_LIMIT) -> tuple[str, bool]:
    """Texte (UTF-8, erreurs remplacées) des `limit` premiers octets d'un fichier de l'espace,
    et vrai s'il en reste au-delà."""
    kind = kind_of(root, path)
    if kind == "missing":
        raise SandboxFileError(f"« {path} » n'existe pas.")
    if kind == "dir":
        raise SandboxFileError(f"« {path} » est un dossier, pas un fichier.")
    target = confine(root, path, portable=False)
    if not target.is_file():
        raise SandboxFileError(f"« {path} » n'a pas pu être lu.")
    with target.open("rb") as handle:
        data = handle.read(limit + 1)
    return data[:limit].decode("utf-8", errors="replace"), len(data) > limit


def append_text(root: Path, path: str, text: str) -> Path:
    """Ajoute `text` (UTF-8, LF) à la fin de `path`, créé au besoin, sans relire le fichier."""
    target = confine(root, path)
    if target.is_dir():
        raise SandboxFileError(f"« {path} » est un dossier.")
    data = to_lf(text).encode("utf-8")
    if target.exists():
        with target.open("ab") as handle:
            handle.write(data)
    else:
        require_parent(root, path)
        _atomic_write(target, data)
    return target


def require_parent(root: Path, path: str) -> None:
    """Refuse d'écrire dans un dossier absent, comme un shell (pas de création en silence)."""
    parent = PurePosixPath(path).parent
    if parent.parts and kind_of(root, parent.as_posix()) != "dir":
        raise SandboxFileError(
            f"Le dossier « {parent.as_posix()} » n'existe pas.", "Créez-le avec « mkdir »."
        )


def touch(root: Path, path: str) -> Path:
    """Crée un fichier vide, ou met à jour la date d'un fichier existant."""
    target = confine(root, path)
    if target.exists():
        os.utime(target)
    else:
        require_parent(root, path)
        _atomic_write(target, b"")
    return target


def make_directory(root: Path, path: str, *, parents: bool = False) -> Path:
    target = confine(root, path)
    if target.exists():
        if parents and target.is_dir():
            return target
        raise SandboxFileError(f"« {path} » existe déjà.", "Choisissez un autre nom.")
    if not parents and not target.parent.is_dir():
        raise SandboxFileError(
            f"Le dossier parent de « {path} » n'existe pas.", "Ajoutez l'option -p pour le créer."
        )
    target.mkdir(parents=parents)
    return target


def remove_path(root: Path, path: str, *, recursive: bool = False) -> None:
    """Supprime un fichier, un lien (lui-même) ou, avec `recursive`, un dossier."""
    entry = _entry(root, path)
    kind = kind_of(root, path)
    if kind == "missing":
        raise SandboxFileError(f"« {path} » n'existe pas.")
    if kind == "dir":
        if not recursive:
            raise SandboxFileError(
                f"« {path} » est un dossier.", "Ajoutez l'option -r pour le supprimer."
            )
        remove_tree(entry)
        return
    try:
        entry.unlink()
    except PermissionError:
        os.chmod(entry, stat.S_IWRITE)
        entry.unlink()


def _destination(root: Path, source: str, dest: str) -> Path:
    """Cible de `mv`/`cp` : un dossier existant reçoit la source sous son nom."""
    target = confine(root, dest)
    if target.is_dir():
        name = PurePosixPath(source).name
        target = confine(root, f"{PurePosixPath(dest).as_posix()}/{name}")
    if not target.parent.is_dir():
        raise SandboxFileError(f"Le dossier de destination « {dest} » n'existe pas.")
    return target


def _inside(candidate: Path, parent: Path) -> bool:
    return candidate == parent or candidate.is_relative_to(parent)


def move_path(root: Path, source: str, dest: str) -> None:
    src = _entry(root, source)
    if kind_of(root, source) == "missing":
        raise SandboxFileError(f"« {source} » n'existe pas.")
    target = _destination(root, source, dest)
    if src.is_dir() and _inside(target, src):
        raise SandboxFileError(f"« {source} » ne peut pas être déplacé dans lui-même.")
    if target.is_dir() and not target.is_symlink():
        raise SandboxFileError(f"« {dest} » est un dossier existant.")
    os.replace(src, target)


def copy_path(root: Path, source: str, dest: str, *, recursive: bool = False) -> None:
    src = _entry(root, source)
    kind = kind_of(root, source)
    if kind == "missing":
        raise SandboxFileError(f"« {source} » n'existe pas.")
    target = _destination(root, source, dest)
    if kind == "dir":
        if not recursive:
            raise SandboxFileError(
                f"« {source} » est un dossier.", "Ajoutez l'option -r pour le copier."
            )
        if _inside(target, src):
            raise SandboxFileError(f"« {source} » ne peut pas être copié dans lui-même.")
        if target.exists():
            raise SandboxFileError(f"« {dest} » existe déjà.")
        junction = _find_junction(src)
        if junction is not None:
            raise SandboxFileError(
                f"« {source} » contient une jonction Windows ({junction}), qui ne se copie pas.",
                "Supprimez la jonction avec « rm », ou copiez les fichiers un par un.",
            )
        shutil.copytree(src, target, symlinks=True, ignore=_skip_git_dirs)
        return
    if kind == "symlink":
        # Un lien est copié par sa cible, qui doit rester dans l'espace.
        src = confine(root, source, portable=False)
        if src.is_dir():
            raise SandboxFileError(f"« {source} » est un lien vers un dossier.")
    if target.is_dir():
        raise SandboxFileError(f"« {dest} » est un dossier existant.")
    _atomic_write(target, src.read_bytes())


def _find_junction(src: Path) -> str | None:
    """Première jonction sous `src` : `copytree` la copierait comme un dossier réel, donc avec
    le contenu de sa cible, peut-être hors de l'espace (`os.walk` ne la suit pas)."""
    for directory, dirs, _files in os.walk(src):
        for name in dirs:
            if os.path.isjunction(os.path.join(directory, name)):
                return Path(directory, name).relative_to(src).as_posix()
    return None


def _skip_git_dirs(_directory: str, names: list[str]) -> set[str]:
    """`cp -r` ne recopie pas de dossier interne de git (dépôt imbriqué)."""
    return {name for name in names if _is_git_dir(name)}


def _glob_regex(part: str) -> re.Pattern[str]:
    body = "".join(".*" if c == "*" else "." if c == "?" else re.escape(c) for c in part)
    return re.compile(body + r"\Z", re.DOTALL)


def expand_glob(root: Path, pattern: str) -> list[str]:
    """Chemins de l'espace qui correspondent à `pattern` (`*` et `?`, segment par segment).

    Les noms qui commencent par un point ne sont pris que par un motif qui commence aussi
    par un point ; `.git` n'est jamais pris. Sans `*` ni `?`, le motif est rendu tel quel
    (la commande dira alors si le chemin existe).
    """
    if "*" not in pattern and "?" not in pattern:
        return [pattern]
    pure = check_relative(pattern, portable=False)
    found = [""]
    for part in pure.parts:
        nxt: list[str] = []
        for prefix in found:
            if "*" in part or "?" in part:
                try:
                    names = list_dir(root, prefix.rstrip("/") or ".", hidden=part.startswith("."))
                except AppError:
                    continue
                regex = _glob_regex(part)
                nxt.extend(f"{prefix}{n}" for n, _ in names if regex.match(n))
            else:
                nxt.append(f"{prefix}{part}")
        found = [f"{p}/" for p in nxt]
    return sorted(p.rstrip("/") for p in found if kind_of(root, p.rstrip("/")) != "missing")
