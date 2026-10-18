"""Exécution facultative du code d'exercice du parcours LLM (AD-13, FR-17).

Seul composant autorisé à demander un processus qui peut sortir sur le réseau : il lance
`python -m <point d'entrée>` dans `cache/venv/`, sans la garde réseau (`WDS_NETGUARD`) et avec
les variables de proxy de l'apprenant rétablies. Le processus passe par `toolrun.spawn_module`
(donc `procs.spawn`) : sortie au fil de l'eau, délai, arrêt d'arbre à l'interruption. Il ne
décide de rien : la confirmation, l'instantané préalable et la file d'opérations sont l'affaire
de l'appelant (`web`, `engine`).
"""

from __future__ import annotations

import sys
from collections.abc import Callable

from wavedevsecops import toolrun
from wavedevsecops.config import (
    Settings,
    get_settings,
    inherited_environment,
    read_proxy_environment,
)
from wavedevsecops.wsfs import Layout

INTENT = "run_exercise_code"
"""Nom de l'intention (AD-17) ; aucune étape de scénario ne peut la déclarer."""
ENTRY_POINT = "inventory"
"""Module du gabarit `content/exercise/llm/` lancé par `python -m`."""
DEFAULT_QUESTION = "Quels articles sont sous leur seuil d'alerte ?"
COMMAND = f'python -m {ENTRY_POINT} "{DEFAULT_QUESTION}"'
LOOPBACK = ("127.0.0.1", "localhost")

PASSED_VARIABLES = frozenset(
    {
        # Système : sans `SYSTEMROOT`, Windows refuse d'ouvrir un socket.
        "PATH",
        "PATHEXT",
        "SYSTEMROOT",
        "SYSTEMDRIVE",
        "WINDIR",
        "COMSPEC",
        "TEMP",
        "TMP",
        "TMPDIR",
        "HOME",
        "USERPROFILE",
        "APPDATA",
        "LOCALAPPDATA",
        "LANG",
        "LC_ALL",
        "LC_CTYPE",
        "TZ",
        # Certificats d'un proxy d'entreprise.
        "SSL_CERT_FILE",
        "SSL_CERT_DIR",
        "REQUESTS_CA_BUNDLE",
    }
)
"""Variables de l'apprenant transmises au code d'exercice (casse ignorée), proxy à part.

Le reste (jetons, clés d'API, `PYTHONPATH`…) n'est pas transmis : ce processus peut sortir
sur le réseau (AD-13), il ne reçoit que ce qu'il lui faut pour tourner.
"""


class ExerciseUnavailable(Exception):
    """Le code d'exercice n'a pas pu être lancé (environnement, démarrage du processus)."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


def exercise_environment(
    settings: Settings | None = None, environ: dict[str, str] | None = None
) -> dict[str, str]:
    """Environnement du code d'exercice : le strict nécessaire, sans garde réseau, avec proxy.

    Part de l'environnement des outils (`toolrun.offline_environment`), ne garde des variables
    héritées que `PASSED_VARIABLES`, retire `WDS_NETGUARD` et rétablit les variables de proxy
    de l'apprenant (`environ`, par défaut le processus). La boucle locale reste hors proxy
    (Ollama sur 127.0.0.1).
    """
    settings = settings or get_settings()
    base = {k: v for k, v in inherited_environment().items() if k.upper() in PASSED_VARIABLES}
    env = toolrun.offline_environment(settings, base)
    env.pop(toolrun.NETGUARD_VARIABLE, None)
    for name in [n for n in env if n.upper() in {"HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY"}]:
        del env[name]
    for name in [n for n in env if n.upper() == "NO_PROXY"]:
        del env[name]
    proxies = read_proxy_environment(environ if environ is not None else inherited_environment())
    no_proxy = [e.strip() for e in proxies.get("NO_PROXY", "").split(",") if e.strip()]
    no_proxy += [host for host in LOOPBACK if host not in no_proxy]
    proxies["NO_PROXY"] = ",".join(no_proxy)
    env.update(proxies)
    if sys.platform != "win32":
        # Les clients lisent aussi la forme en minuscules ; sous Windows, la casse est ignorée.
        env.update({name.lower(): value for name, value in proxies.items()})
    return env


def start_exercise(
    layout: Layout,
    settings: Settings | None = None,
    *,
    question: str = DEFAULT_QUESTION,
    environ: dict[str, str] | None = None,
    on_sync: Callable[[toolrun.Handle], None] | None = None,
) -> toolrun.Handle:
    """Lance le point d'entrée dans `cache/venv/` de l'espace, cwd `repo/`, et rend son `Handle`.

    Si l'environnement n'existe pas encore, il est créé hors ligne depuis le `uv.lock` du dépôt.
    `on_sync` reçoit le `Handle` de `uv sync` (création du venv) pour le rendre interruptible.
    Lève `ExerciseUnavailable` si rien n'a pu être lancé.
    """
    settings = settings or get_settings()
    venv = toolrun.venv_dir(layout.root)
    if toolrun.venv_python(venv) is None:
        synced = toolrun.sync_environment(layout.repo, venv, settings, on_start=on_sync)
        if not synced.ok:
            raise ExerciseUnavailable(synced.error or synced.stderr.strip() or "uv sync a échoué")
    try:
        return toolrun.spawn_module(
            venv,
            ENTRY_POINT,
            [question],
            env=exercise_environment(settings, environ),
            cwd=layout.repo,
            timeout=settings.llm_run_timeout_s,
        )
    except OSError as exc:
        raise ExerciseUnavailable(str(exc) or type(exc).__name__) from exc
