"""Analyses statiques du code de `src/` : règles de dépendance (AD-1) et hors ligne (AD-13).

Fonctions pures, testées aussi sur des exemples synthétiques pour qu'un contrôle qui ne
trouve rien sur le dépôt prouve quand même qu'il sait trouver.
"""

from __future__ import annotations

import ast
import ipaddress
import re
from collections.abc import Callable, Iterator
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parent.parent
PACKAGE = "wavedevsecops"
SRC = ROOT / "src" / PACKAGE
STATIC = SRC / "web" / "static"

LEAVES = frozenset({"contracts", "events", "config"})
PROCS_CALLERS = frozenset({"procs", "gitio", "toolrun"})
# Liste d'AD-13, plus les voies de contournement directes (`_socket`, clients stdlib, urllib3).
NETWORK_MODULES = (
    "socket",
    "_socket",
    "http.client",
    "urllib.request",
    "httpx",
    "requests",
    "aiohttp",
    "ssl",
    "urllib3",
    "ftplib",
    "smtplib",
    "poplib",
    "imaplib",
    "xmlrpc.client",
)
# Seule l'écoute locale est permise à `web` et `cli` : ils peuvent importer `socket`, rien d'autre.
LISTENING_COMPONENTS = frozenset({"web", "cli"})
LISTENING_MODULES = frozenset({"socket"})
NETWORK_COMPONENT = "llmrun"
# Modules, ou noms importés par `from x import y`, qui créent des processus.
SUBPROCESS_MODULES = (
    "subprocess",
    "multiprocessing",
    "pty",
    "asyncio.subprocess",
    "asyncio.create_subprocess_exec",
    "asyncio.create_subprocess_shell",
    "concurrent.futures.process",
    "concurrent.futures.ProcessPoolExecutor",
)
ENV_ATTRIBUTES = frozenset({"environ", "environb", "getenv", "getenvb", "putenv", "unsetenv"})
# Fonctions de `os` et `asyncio` qui créent des processus (appelées par attribut).
PROCESS_ATTRIBUTES = {
    "os": ("system", "popen", "spawn", "exec", "fork", "posix_spawn", "startfile"),
    "asyncio": ("create_subprocess_exec", "create_subprocess_shell"),
}


def iter_modules(src: Path = SRC, package: str = PACKAGE) -> Iterator[tuple[str, Path]]:
    """Donne `(nom de module, chemin)` pour chaque fichier `.py` du paquet."""
    for path in sorted(src.rglob("*.py")):
        parts = list(path.relative_to(src).with_suffix("").parts)
        if parts[-1] == "__init__":
            parts.pop()
        yield ".".join([package, *parts]), path


def component(module: str) -> str:
    """`wavedevsecops.web.app` -> `web` ; le paquet racine -> chaîne vide."""
    parts = module.split(".")
    return parts[1] if len(parts) > 1 else ""


def imported_modules(path: Path, module: str) -> set[str]:
    """Noms absolus des modules importés, imports relatifs résolus.

    Pour `from a import b`, on retient `a` et `a.b` (b peut être un sous-module).
    """
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    is_package = path.name == "__init__.py"
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                base_parts = module.split(".")
                if not is_package:
                    base_parts = base_parts[:-1]
                base_parts = base_parts[: len(base_parts) - (node.level - 1)]
                if node.module:
                    base_parts.append(node.module)
                base = ".".join(base_parts)
            else:
                base = node.module or ""
            names.add(base)
            names.update(f"{base}.{alias.name}" for alias in node.names if alias.name != "*")
    return {name for name in names if name}


def _matches(name: str, targets: tuple[str, ...] | frozenset[str]) -> str | None:
    for target in targets:
        if name == target or name.startswith(target + "."):
            return target
    return None


def _attribute_uses(
    tree: ast.AST, module: str, accept: Callable[[str], bool]
) -> Iterator[tuple[int, str]]:
    """`(ligne, nom)` de chaque `module.nom` ou `from module import nom` retenu par `accept`.

    Suit les alias (`import os as o`).
    """
    aliases = {module}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == module and alias.asname:
                    aliases.add(alias.asname)
        elif isinstance(node, ast.ImportFrom) and node.module == module and not node.level:
            for alias in node.names:
                if accept(alias.name):
                    yield node.lineno, alias.name
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Attribute)
            and isinstance(node.value, ast.Name)
            and node.value.id in aliases
            and accept(node.attr)
        ):
            yield node.lineno, node.attr


def process_call_violations(path: Path, module: str) -> list[str]:
    """Appels qui créent un processus (`os.system`, `asyncio.create_subprocess_exec`…)."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    violations = []
    for target, prefixes in PROCESS_ATTRIBUTES.items():
        for lineno, name in _attribute_uses(tree, target, lambda n, p=prefixes: n.startswith(p)):
            violations.append(
                f"{module}:{lineno} appelle {target}.{name} : seul procs crée des processus"
            )
    return violations


def dependency_violations(src: Path = SRC, package: str = PACKAGE) -> list[str]:
    """Règles de dépendance du spine (AD-1)."""
    violations = []
    for module, path in iter_modules(src, package):
        own = component(module)
        if own != "procs":
            violations.extend(process_call_violations(path, module))
        for name in sorted(imported_modules(path, module)):
            if _matches(name, SUBPROCESS_MODULES) and own != "procs":
                violations.append(f"{module} importe {name} : seul procs crée des processus")
            if not _matches(name, (package,)):
                continue
            target = component(name)
            if target == own:
                continue
            if own in LEAVES:
                violations.append(f"{module} (feuille) importe {name}")
            if target == "cli":
                violations.append(f"{module} importe cli")
            if target == "web" and own != "cli":
                violations.append(f"{module} importe web")
            if target == "procs" and own not in PROCS_CALLERS:
                violations.append(f"{module} importe procs : réservé à gitio et toolrun")
    return violations


def network_import_violations(src: Path = SRC, package: str = PACKAGE) -> list[str]:
    """AD-13, contrôle 1 : imports réseau interdits hors `llmrun` et l'écoute de web/cli."""
    violations = []
    for module, path in iter_modules(src, package):
        own = component(module)
        if own == NETWORK_COMPONENT:
            continue
        targets = {_matches(name, NETWORK_MODULES) for name in imported_modules(path, module)}
        for target in sorted(t for t in targets if t is not None):
            if own in LISTENING_COMPONENTS and target in LISTENING_MODULES:
                continue
            violations.append(f"{module} importe {target}")
    return violations


def env_read_violations(src: Path = SRC, package: str = PACKAGE) -> list[str]:
    """Convention « Réglages » : seul `config` lit l'environnement."""
    violations = []
    for module, path in iter_modules(src, package):
        if component(module) == "config":
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for lineno, name in _attribute_uses(tree, "os", ENV_ATTRIBUTES.__contains__):
            violations.append(f"{module}:{lineno} lit os.{name}")
    return violations


URL_PATTERN = re.compile(r"(?:https?|wss?)://[^\s\"'`<>()\\]+", re.IGNORECASE)
BINARY_SUFFIXES = frozenset(
    {".woff2", ".woff", ".ttf", ".otf", ".png", ".jpg", ".jpeg", ".gif", ".ico", ".webp"}
)
LOOPBACK_HOSTS = frozenset({"localhost", "::1"})
# Identifiants d'espaces de noms XML : jamais chargés, nécessaires à `createElementNS`.
XML_NAMESPACES = frozenset(
    {
        "http://www.w3.org/2000/svg",
        "http://www.w3.org/1999/xlink",
        "http://www.w3.org/1999/xhtml",
        "http://www.w3.org/XML/1998/namespace",
    }
)


def is_loopback_url(url: str) -> bool:
    try:
        host = (urlsplit(url).hostname or "").lower()
    except ValueError:
        return False
    if host in LOOPBACK_HOSTS:
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def is_license_text(path: Path, static: Path = STATIC) -> bool:
    """Licence d'une police (`fonts/OFL-*.txt`) : texte juridique cité, jamais chargé ni exécuté.

    Les licences OFL citent des adresses web. L'exclusion est étroite : un `.txt` de licence
    dans `fonts/` seulement, pas un `.js`, un `.css` ou un `.html`, où une URL reste interdite.
    """
    return (
        path.suffix.lower() == ".txt"
        and path.name.startswith("OFL-")
        and path.parent == static / "fonts"
    )


def static_url_violations(static: Path = STATIC) -> list[str]:
    """AD-13, contrôle 2 : aucune URL `http(s)://` ou `ws(s)://` non loopback dans `static/`."""
    if not static.is_dir():
        return []
    violations = []
    for path in sorted(p for p in static.rglob("*") if p.is_file()):
        if path.suffix.lower() in BINARY_SUFFIXES or is_license_text(path, static):
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        for match in URL_PATTERN.finditer(text):
            url = match.group(0).rstrip(".,;:")
            if url in XML_NAMESPACES or is_loopback_url(url):
                continue
            line = text.count("\n", 0, match.start()) + 1
            violations.append(f"{path.relative_to(static).as_posix()}:{line} {url}")
    return violations


def misplaced_static_dirs(src: Path = SRC, static: Path = STATIC) -> list[str]:
    """Dossiers `static` hors de `STATIC` : le contrôle 2 ne les verrait pas."""
    return [
        p.relative_to(src).as_posix()
        for p in sorted(src.rglob("static"))
        if p.is_dir() and p.resolve() != static.resolve()
    ]
