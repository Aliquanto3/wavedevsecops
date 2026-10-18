"""Appels git : sonde de la langue, deux contextes d'appel, environnement hermétique (AD-3).

`gitio` est le seul module qui lance git (par `procs`). Il pose seul l'environnement
hermétique : `GIT_CONFIG_NOSYSTEM`, `GIT_CONFIG_GLOBAL` vers `<data>/gitconfig`, réglages
forcés par `GIT_CONFIG_COUNT`, aucun prompt, aucun éditeur, aucun proxy, entrée fermée.

- Contexte interne (setup, projections, empreinte) : `LC_ALL=C`, `LANGUAGE` vide.
- Contexte apprenant (commandes tapées) : locale française sondée, sinon anglais.
"""

from __future__ import annotations

import os
import tempfile
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from wavedevsecops import procs
from wavedevsecops.config import Settings, get_settings, inherited_environment
from wavedevsecops.contracts import AppError

FRENCH_LOCALES = ("fr_FR.UTF-8", "fr_FR.utf8")
PROBE_ARGV = ("rev-parse", "--git-dir")
"""Échoue hors dépôt, avec un message traduit : de quoi distinguer français et anglais."""


@dataclass(frozen=True)
class GitLanguage:
    """Langue des messages de git : `fr` si une locale française répond, sinon `en`."""

    lang: str
    locale: str | None = None


def _env(locale: str) -> dict[str, str]:
    env = {
        k: v
        for k, v in inherited_environment().items()
        if not _dropped(k)  # GIT_DIR hérité : la sonde réussirait sans message à comparer
    }
    env.update(
        LC_ALL=locale,
        GIT_TERMINAL_PROMPT="0",
        GIT_CONFIG_NOSYSTEM="1",
        GIT_CONFIG_GLOBAL=str(Path("NUL" if _is_windows() else "/dev/null")),
        GIT_CEILING_DIRECTORIES=str(Path(tempfile.gettempdir()).parent),
    )
    if locale != "C":
        env["LANGUAGE"] = "fr"
    else:
        env["LANGUAGE"] = ""
    return env


def _is_windows() -> bool:
    return procs.IS_WINDOWS


def probe_language(git: Path, settings: Settings | None = None) -> GitLanguage:
    """Sonde `fr_FR.UTF-8`, puis `fr_FR.utf8` : la locale dont le message diffère de `C`.

    Hors dépôt (dossier temporaire vide), `git rev-parse --git-dir` échoue avec un message
    traduit. Si aucune locale française ne change le message, git parle anglais.
    """
    settings = settings or get_settings()
    timeout = settings.probe_timeout_s
    with tempfile.TemporaryDirectory(prefix="wds-probe-") as scratch:
        cwd = Path(scratch)
        reference = procs.run([git, *PROBE_ARGV], env=_env("C"), cwd=cwd, timeout=timeout)
        if reference.error or reference.timed_out or not reference.stderr.strip():
            return GitLanguage("en")
        for locale in FRENCH_LOCALES:
            attempt = procs.run([git, *PROBE_ARGV], env=_env(locale), cwd=cwd, timeout=timeout)
            if attempt.stderr.strip() and attempt.stderr != reference.stderr:
                return GitLanguage("fr", locale)
    return GitLanguage("en")


Context = Literal["internal", "learner"]

LEARNER_NAME = "Camille Durand"
LEARNER_EMAIL = "camille.durand@exemple.test"
"""Identité de l'apprenant : celle de ses commits du setup, reprise par le terminal."""

FORCED_CONFIG: tuple[tuple[str, str], ...] = (
    ("core.autocrlf", "false"),
    ("core.eol", "lf"),
    ("core.filemode", "false"),
    ("core.symlinks", "false"),
    ("core.longpaths", "true"),
    ("core.quotePath", "false"),
    ("core.pager", "cat"),
    ("core.editor", ":"),
    ("sequence.editor", ":"),
    ("init.defaultBranch", "main"),
    ("commit.gpgsign", "false"),
    ("tag.gpgsign", "false"),
    ("core.fsmonitor", "false"),
    ("gc.auto", "0"),
    ("maintenance.auto", "false"),
    ("credential.helper", ""),
    ("core.excludesFile", os.devnull),
    ("core.attributesFile", os.devnull),
)
"""Réglages qui priment sur toute config de dépôt (AD-3) ; `core.hooksPath` s'y ajoute.

`core.excludesFile` et `core.attributesFile` valent par défaut `$XDG_CONFIG_HOME/git/ignore`
et `.../attributes` (ou `~/.config/git/...`), lus même avec `GIT_CONFIG_GLOBAL` : on les
neutralise, sinon un ignore global du poste change l'index, les commits et l'empreinte.
"""


def _dropped(name: str) -> bool:
    """Variables héritées retirées : git, locale, proxy, éditeur et pager du poste."""
    upper = name.upper()
    return (
        upper.startswith(("GIT_", "LC_"))
        or upper in {"LANG", "LANGUAGE", "EDITOR", "VISUAL", "PAGER", "LESS"}
        or upper.endswith("_PROXY")
    )


def hermetic_environment(
    *,
    gitconfig: Path,
    hooks_dir: Path,
    context: Context = "internal",
    locale: str | None = None,
    ceiling: Path | None = None,
    extra: Mapping[str, str] | None = None,
) -> dict[str, str]:
    """Environnement de git selon AD-3, pour le contexte interne ou apprenant.

    `extra` ajoute des variables propres à un appel (dates et identités du setup).
    """
    env = {k: v for k, v in inherited_environment().items() if not _dropped(k)}
    forced = (*FORCED_CONFIG, ("core.hooksPath", hooks_dir.as_posix()))
    env["GIT_CONFIG_COUNT"] = str(len(forced))
    for index, (key, value) in enumerate(forced):
        env[f"GIT_CONFIG_KEY_{index}"] = key
        env[f"GIT_CONFIG_VALUE_{index}"] = value
    env.update(
        GIT_CONFIG_NOSYSTEM="1",
        GIT_CONFIG_GLOBAL=str(gitconfig),
        GIT_TERMINAL_PROMPT="0",
        GIT_MERGE_AUTOEDIT="no",
        GIT_PAGER="cat",
        GIT_EDITOR=":",
        GIT_SEQUENCE_EDITOR=":",
    )
    if ceiling is not None:
        env["GIT_CEILING_DIRECTORIES"] = str(ceiling)
    if context == "learner" and locale:
        env.update(LANG=locale, LC_ALL=locale, LANGUAGE="fr")
    else:
        env.update(LC_ALL="C", LANGUAGE="")
    if extra:
        env.update(extra)
    return env


class GitError(AppError):
    """Commande git interne en échec : le setup ou une lecture n'a pas abouti."""

    def __init__(self, args: Sequence[str], result: procs.ProcResult) -> None:
        if result.error:
            why = f"git n'a pas pu être lancé ({result.error})"
        elif result.timed_out:
            why = "git n'a pas répondu à temps"
        else:
            why = f"git a répondu par le code {result.returncode}"
        super().__init__(
            f"La commande interne « git {' '.join(args)} » a échoué : {why}.",
            "Ouvrez le diagnostic pour vérifier l'installation de git.",
        )
        self.result = result
        self.detail = result.stderr.strip()


@dataclass(frozen=True)
class Git:
    """Git d'un espace de travail : exécutable résolu, `gitconfig` et `hooks/` de l'espace."""

    executable: Path
    gitconfig: Path
    hooks_dir: Path
    ceiling: Path | None = None
    timeout: float = 30.0
    locale: str | None = None
    """Locale française sondée (`probe_language`) pour le contexte apprenant."""
    learner_gitconfig: Path | None = None
    """`GIT_CONFIG_GLOBAL` du contexte apprenant (`learner_gitconfig`) : identité par défaut."""

    @classmethod
    def for_workspace(
        cls, executable: Path, workspace: Path, settings: Settings | None = None
    ) -> Git:
        """Git d'un espace : `hooks/` de l'espace, recherche de dépôt bornée à l'espace."""
        settings = settings or get_settings()
        return cls(
            executable=executable,
            gitconfig=settings.gitconfig_path(),
            hooks_dir=workspace / "hooks",
            ceiling=workspace,
            timeout=settings.git_timeout_s,
        )

    def env(
        self, context: Context = "internal", extra: Mapping[str, str] | None = None
    ) -> dict[str, str]:
        gitconfig = self.gitconfig
        if context == "learner" and self.learner_gitconfig is not None:
            gitconfig = self.learner_gitconfig
        return hermetic_environment(
            gitconfig=gitconfig,
            hooks_dir=self.hooks_dir,
            context=context,
            locale=self.locale,
            ceiling=self.ceiling,
            extra=extra,
        )

    def run(
        self,
        *args: str,
        cwd: Path,
        context: Context = "internal",
        extra_env: Mapping[str, str] | None = None,
    ) -> procs.ProcResult:
        """Lance `git args` dans `cwd` ; jamais d'exception pour un échec ordinaire."""
        return procs.run(
            [self.executable, *args],
            env=self.env(context, extra_env),
            cwd=cwd,
            timeout=self.timeout,
        )

    def internal(self, *args: str, cwd: Path, extra_env: Mapping[str, str] | None = None) -> str:
        """Commande interne (`LC_ALL=C`) qui doit réussir : sa sortie, sinon `GitError`."""
        result = self.run(*args, cwd=cwd, extra_env=extra_env)
        if not result.ok:
            raise GitError(args, result)
        return result.stdout


def _split_z(output: str) -> list[str]:
    return [item for item in output.split("\0") if item]


def head_record(git: Git, repo: Path) -> str:
    """`HEAD -> refs/heads/x` (symbolique) ou `HEAD <sha>` (détaché)."""
    symbolic = git.run("symbolic-ref", "-q", "HEAD", cwd=repo)
    if symbolic.ok:
        return f"HEAD -> {symbolic.stdout.strip()}"
    return "HEAD " + git.internal("rev-parse", "HEAD", cwd=repo).strip()


def refs(git: Git, repo: Path) -> list[tuple[str, str]]:
    """Refs du dépôt et leurs cibles, triées."""
    out = git.internal("for-each-ref", "--format=%(refname)%09%(objectname)", cwd=repo)
    pairs = [line.split("\t", 1) for line in out.splitlines() if line]
    return sorted((name, target) for name, target in pairs)


def reachable_objects(git: Git, repo: Path) -> list[str]:
    """Objets accessibles depuis les refs et le reflog (identifiants triés)."""
    out = git.internal("rev-list", "--objects", "--all", "--reflog", cwd=repo)
    return sorted({line.split(" ", 1)[0] for line in out.splitlines() if line})


def index_entries(git: Git, repo: Path) -> list[str]:
    """Entrées de l'index : `mode oid étage chemin`, triées."""
    out = git.internal("ls-files", "-s", "-z", cwd=repo)
    return sorted(entry.replace("\t", " ", 1) for entry in _split_z(out))


def worktree_paths(git: Git, repo: Path) -> list[str]:
    """Chemins suivis ou non ignorés de l'arbre de travail (posix, triés, sans doublon)."""
    out = git.internal("ls-files", "-z", "--cached", "--others", "--exclude-standard", cwd=repo)
    return sorted(set(_split_z(out)))


def stash_list(git: Git, repo: Path) -> list[str]:
    """Commits du stash, du plus récent au plus ancien (l'ordre compte)."""
    out = git.internal("stash", "list", "--format=%H", cwd=repo)
    return [line for line in out.splitlines() if line]


_LANGUAGES: dict[Path, GitLanguage] = {}


def learner_language(executable: Path, settings: Settings | None = None) -> GitLanguage:
    """Langue de git pour le contexte apprenant, sondée une fois par exécutable (AD-3)."""
    found = _LANGUAGES.get(executable)
    if found is None:
        found = _LANGUAGES[executable] = probe_language(executable, settings)
    return found


def learner_gitconfig(settings: Settings | None = None) -> Path:
    """`<data>/learner.gitconfig` : identité par défaut des commandes tapées (AD-3).

    Portée « globale » propre à l'application (jamais `~/.gitconfig`) : un
    `git config user.name …` tapé dans le terminal (portée du dépôt) la remplace.
    Écrit une fois, de façon atomique ; le contexte interne ne la lit pas.
    """
    settings = settings or get_settings()
    path = settings.resolved_data_dir() / "learner.gitconfig"
    content = f"[user]\n\tname = {LEARNER_NAME}\n\temail = {LEARNER_EMAIL}\n"
    try:
        if path.read_text(encoding="utf-8") == content:
            return path
    except OSError:
        pass
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f"{path.name}.{os.getpid()}.{time.monotonic_ns()}.tmp")
    tmp.write_text(content, encoding="utf-8", newline="\n")
    try:
        os.replace(tmp, path)
    except OSError:
        tmp.unlink(missing_ok=True)
        if not path.exists():
            raise
    return path


def spawn_learner(tool: Git, *args: str, cwd: Path, timeout: float | None = None) -> procs.Handle:
    """Lance `git args` en contexte apprenant, sans attendre : la sortie arrive au fil de l'eau.

    `tool.locale` doit porter la locale française sondée (sinon git parle anglais).
    """
    return procs.spawn(
        [tool.executable, *args],
        env=tool.env("learner"),
        cwd=cwd,
        timeout=tool.timeout if timeout is None else timeout,
    )


def clear_stale_index_lock(repo: Path, *, attempts: int = 5) -> bool:
    """Supprime `.git/index.lock` laissé par une commande arrêtée (AD-12).

    La file est le seul écrivain d'un espace : après l'arrêt de l'arbre, aucun git vivant ne
    peut le tenir. Sous Windows, le fichier peut rester ouvert un instant : on réessaie.
    Rend vrai si un verrou a été supprimé.
    """
    lock = repo / ".git" / "index.lock"
    for attempt in range(attempts):
        try:
            lock.unlink()
            return True
        except FileNotFoundError:
            return False
        except OSError:
            if attempt + 1 < attempts:
                time.sleep(0.1)
    return False
