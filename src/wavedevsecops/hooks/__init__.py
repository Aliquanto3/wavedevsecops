"""Point d'entrée des hooks git de l'espace (AD-9) : `python -m wavedevsecops.hooks <nom> ...`.

Chaque hook posé par l'op `install_hooks` est un script `#!/bin/sh` d'une ligne qui appelle ce
point d'entrée. Un seul dossier `hooks/` sert `repo/` et `origin.git/` : le point d'entrée
distingue le dépôt appelant par son dossier de travail (git lance un hook depuis la racine du
dépôt, ou depuis le dépôt nu), `pre-receive` n'agit que dans `origin.git/` et `pre-commit`
(story 7.3) que dans `repo/`.

Contrat (stories 3.5, 5.7, 7.3) :

- code 0 : git continue ; autre code : git refuse et affiche la sortie d'erreur (`remote:` pour
  un hook côté `origin`) ;
- le refus s'écrit en français sur la sortie d'erreur ;
- un hook ne modifie jamais l'état : il lit `github.json` par `github_sim` et rien d'autre ;
- `github.json` illisible : la protection n'est pas appliquée (l'apprenant peut travailler),
  avec un avertissement en français ; toute autre erreur du hook refuse le push avec un texte
  en français qui renvoie au diagnostic (AD-9), jamais une trace Python.

Le script porte le chemin de l'interpréteur de l'application (`sys.executable`). Si ce chemin
change (environnement recréé ailleurs), `refresh` réécrit les scripts posés : le terminal
l'appelle avant chaque `git push`. L'empreinte (AD-6) lit `canonical_script`, sans ce chemin,
pour rester la même d'un poste à l'autre (empreintes de référence d'AD-18).
"""

from __future__ import annotations

import json
import re
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import TextIO

from wavedevsecops import github_sim, wsfs
from wavedevsecops.config import Settings
from wavedevsecops.wsfs import Layout

HOOK_NAMES = ("pre-receive", "pre-commit")
"""Hooks que l'op `install_hooks` sait poser ; un hook de plus s'ajoute ici et dans `HANDLERS`."""

BRANCH_PREFIX = "refs/heads/"
EXIT_REFUSED = 1

_SH_SPECIAL = re.compile(r'([\\"$`])')
_INTERPRETER = re.compile(rb'^exec ".*" -m wavedevsecops\.hooks ', re.MULTILINE)


def _sh_quote(text: str) -> str:
    """`text` entre guillemets doubles sh, avec `\\`, `"`, `$` et l'accent grave échappés."""
    return '"' + _SH_SPECIAL.sub(r"\\\1", text) + '"'


def hook_script(name: str, python: Path) -> str:
    """Script d'une ligne (LF) du hook `name` : chemins posix entre guillemets, sans bash."""
    if name not in HOOK_NAMES:
        raise ValueError(f"hook inconnu : « {name} »")
    interpreter = _sh_quote(python.as_posix())
    return f'#!/bin/sh\nexec {interpreter} -m wavedevsecops.hooks {name} "$@"\n'


def canonical_script(data: bytes) -> bytes:
    """Contenu d'un fichier de `hooks/` sans le chemin de l'interpréteur (empreinte, AD-6)."""
    return _INTERPRETER.sub(b'exec "<python>" -m wavedevsecops.hooks ', data)


def refresh(hooks_dir: Path, python: Path | None = None) -> list[str]:
    """Réécrit les hooks posés dont l'interpréteur n'est plus celui de l'application ; rend
    leurs noms. Un hook absent n'est pas posé (seule l'op `install_hooks` le fait)."""
    python = python or Path(sys.executable)
    rewritten = []
    for name in HOOK_NAMES:
        expected = hook_script(name, python)
        current = wsfs.read_bytes(hooks_dir, name)
        if current is not None and current != expected.encode("utf-8"):
            wsfs.write_executable(hooks_dir, name, expected)
            rewritten.append(name)
    return rewritten


def refusal_text(branch: str) -> str:
    return (
        f"La branche « {branch} » est protégée : un push direct est refusé.\n"
        "Poussez une autre branche, puis ouvrez une pull request.\n"
    )


UNREADABLE_STATE_TEXT = (
    "Avertissement : l'état du GitHub simulé de cet espace est illisible ; "
    "la protection des branches n'est pas appliquée à ce push.\n"
)
HOOK_FAILED_TEXT = (
    "Le hook « {name} » a échoué ({error}) : le push est refusé par prudence.\n"
    "Ouvrez le diagnostic, ou recommencez le scénario pour reconstruire l'espace.\n"
)


def origin_layout(cwd: Path) -> Layout | None:
    """Espace dont `cwd` est le dépôt nu `origin.git/`, ou `None` si `cwd` est un autre dépôt
    (`repo/` : un dossier `.git`, pas de `HEAD` à sa racine)."""
    if (cwd / ".git").exists() or not (cwd / "HEAD").is_file() or not (cwd / "objects").is_dir():
        return None
    return Layout(cwd.parent)


def pre_receive(cwd: Path, stdin: TextIO, stderr: TextIO) -> int:
    """Refuse toute mise à jour d'une branche protégée contre le push direct.

    `stdin` porte une ligne `<ancien> <nouveau> <ref>` par ref poussée."""
    layout = origin_layout(cwd)
    if layout is None:
        return 0
    try:
        state = github_sim.load(layout)
    except github_sim.GithubSimError:
        stderr.write(UNREADABLE_STATE_TEXT)
        return 0
    blocked = {p.branch for p in state.protections if p.block_direct_push}
    refused: list[str] = []
    for line in stdin.read().splitlines():
        parts = line.split()
        if len(parts) != 3 or not parts[2].startswith(BRANCH_PREFIX):
            continue
        branch = parts[2].removeprefix(BRANCH_PREFIX)
        if branch in blocked and branch not in refused:
            refused.append(branch)
    for branch in refused:
        stderr.write(refusal_text(branch))
    return EXIT_REFUSED if refused else 0


PRE_COMMIT_CONFIG = ".pre-commit-config.yaml"
REFUSAL_FILE = "hook-pre-commit.json"
"""Trace du dernier refus du hook `pre-commit`, écrite dans `cache/` : le terminal la lit pour
expliquer le refus sans analyser la sortie de git (AD-2)."""
GITLEAKS_ARGS = ("git", "--pre-commit", "--staged", "--no-banner")
"""Arguments de gitleaks du `.pre-commit-config.yaml` du gabarit, repris pour l'exécution
machine qui donne les fichier:ligne du refus (AD-10)."""

MISSING_TOOL_TEXT = (
    "Le hook « pre-commit » ne peut pas tourner : {tool} est indisponible ({reason}).\n"
    "Le commit n'a pas été créé. Ouvrez le diagnostic pour voir l'état des outils.\n"
)


@dataclass(frozen=True)
class Refusal:
    """Refus du hook `pre-commit` : l'outil en cause et, pour gitleaks, les secrets trouvés."""

    tool: str
    """`gitleaks` (un secret a été trouvé) ou `pre-commit` (un autre hook a échoué)."""
    lines: dict[str, list[int]]
    """Fichier (posix, relatif à `repo/`) -> lignes des secrets ; vide hors gitleaks."""


def clear_refusal(layout: Layout) -> None:
    """Efface la trace du dernier refus (avant chaque `git commit` du terminal)."""
    (layout.cache / REFUSAL_FILE).unlink(missing_ok=True)


def read_refusal(layout: Layout) -> Refusal | None:
    """Refus laissé par le hook depuis le dernier `clear_refusal`, ou `None`."""
    raw = wsfs.read_bytes(layout.cache, REFUSAL_FILE)
    if raw is None:
        return None
    try:
        data = json.loads(raw.decode("utf-8"))
        lines = {str(k): [int(n) for n in v] for k, v in data["lines"].items()}
        return Refusal(str(data["tool"]), lines)
    except (ValueError, KeyError, TypeError, AttributeError):
        return None


def pre_commit_installed(hooks_dir: Path) -> bool:
    """Vrai si le hook `pre-commit` de l'application est posé dans `hooks/`."""
    raw = wsfs.read_bytes(hooks_dir, "pre-commit")
    return raw is not None and b" -m wavedevsecops.hooks pre-commit" in raw


def repo_layout(cwd: Path) -> Layout | None:
    """Espace dont `cwd` est le dépôt de travail `repo/` (un dossier `.git`), sinon `None`."""
    if cwd.name != "repo" or not (cwd / ".git").exists():
        return None
    return Layout(cwd.parent)


def pre_commit(cwd: Path, stdin: TextIO, stderr: TextIO) -> int:
    """Lance le vrai `pre-commit run` sur le `.pre-commit-config.yaml` du dépôt (AD-9).

    Les outils viennent de `toolrun` (registre, environnement hors ligne, `PRE_COMMIT_HOME` dans
    `cache/`). Un outil manquant refuse le commit avec un renvoi au diagnostic. Après un échec,
    la trace du refus (`REFUSAL_FILE`) dit si gitleaks a trouvé un secret, et où."""
    layout = repo_layout(cwd)
    config = cwd / PRE_COMMIT_CONFIG
    if layout is None or not config.is_file():
        return 0
    # Importé ici : `pre-receive` (appelé à chaque push) n'a pas besoin de `toolrun`.
    from wavedevsecops import toolrun
    from wavedevsecops.toolrun import findings

    settings = Settings(data_dir=layout.root.parents[2])
    venv = toolrun.venv_dir(layout.root)
    uses_gitleaks = "gitleaks" in config.read_text(encoding="utf-8", errors="replace")
    clear_refusal(layout)
    for tool in ("pre-commit", *(("gitleaks",) if uses_gitleaks else ())):
        status = toolrun.resolve(tool, settings, venv=venv)
        if not status.ok:
            stderr.write(MISSING_TOOL_TEXT.format(tool=tool, reason=status.reason or status.state))
            return EXIT_REFUSED
    try:
        handle = toolrun.spawn_tool(
            "pre-commit",
            ["run", "--color", "never"],
            cwd=cwd,
            venv=venv,
            timeout=settings.tool_timeout_s,
            settings=settings,
        )
    except (toolrun.ToolUnavailable, OSError) as exc:
        stderr.write(MISSING_TOOL_TEXT.format(tool="pre-commit", reason=str(exc)))
        return EXIT_REFUSED
    result = toolrun.collect(handle)
    stderr.write(result.stdout + result.stderr)
    if result.returncode == 0:
        return 0
    found = findings.Findings()
    if uses_gitleaks:
        # Les fichier:ligne viennent d'une exécution machine de gitleaks sur l'index, jamais
        # du texte (AD-10) ; le code 3 de gitleaks dit « secret trouvé » (comme le pipeline, 7.4).
        found = findings.collect(
            "gitleaks",
            GITLEAKS_ARGS,
            repo=cwd,
            venv=venv,
            cache=layout.cache,
            settings=settings,
            timeout=settings.tool_timeout_s,
        )
    lines = {path: sorted(rows) for path, rows in found.lines.items()}
    refusal = {"tool": "gitleaks" if lines else "pre-commit", "lines": lines}
    layout.cache.mkdir(parents=True, exist_ok=True)
    wsfs.write_text(layout.cache, REFUSAL_FILE, json.dumps(refusal))
    return EXIT_REFUSED


HANDLERS: dict[str, Callable[[Path, TextIO, TextIO], int]] = {
    "pre-receive": pre_receive,
    "pre-commit": pre_commit,
}


def main(argv: list[str], stdin: TextIO | None = None, stderr: TextIO | None = None) -> int:
    """Exécute le hook nommé par `argv[0]` ; un hook inconnu ne fait rien (code 0)."""
    handler = HANDLERS.get(argv[0]) if argv else None
    if handler is None:
        return 0
    err = stderr or sys.stderr
    try:
        return handler(Path.cwd(), stdin or sys.stdin, err)
    except Exception as exc:  # noqa: BLE001 - jamais de trace Python dans la sortie de git
        err.write(HOOK_FAILED_TEXT.format(name=argv[0], error=type(exc).__name__))
        return EXIT_REFUSED
