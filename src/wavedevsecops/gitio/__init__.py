"""Appels git : sonde de la langue de git (AD-3).

Story 1.4 : seule la sonde de locale vit ici. Les deux contextes d'appel (apprenant et
interne) et l'environnement hermétique arrivent avec les stories du terminal et du moteur.
"""

from __future__ import annotations

import tempfile
from dataclasses import dataclass
from pathlib import Path

from wavedevsecops import procs
from wavedevsecops.config import Settings, get_settings, inherited_environment

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
        if not k.lower().endswith("_proxy") and not k.upper().startswith(("LC_", "LANG"))
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
