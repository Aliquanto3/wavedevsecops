"""Commande `wavedevsecops` : instance unique, serveur local, navigateur ou fenêtre (AD-19/20)."""

from __future__ import annotations

import argparse
import contextlib
import json
import logging
import logging.handlers
import os
import secrets
import socket
import sys
import threading
import time
import webbrowser
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import uvicorn

from wavedevsecops import diagnostic
from wavedevsecops.config import Settings, get_settings
from wavedevsecops.contracts import AppError, DiagnosticCheck
from wavedevsecops.progress import ensure_progress
from wavedevsecops.web import create_app, shutdown_app

HOST = "127.0.0.1"
LOCK_NAME = "app.lock"
LOG_RELATIVE = Path("logs") / "app.log"
START_TIMEOUT_S = 15.0

Opener = Callable[[str], object]


def url_for(port: int, token: str) -> str:
    return f"http://{HOST}:{port}/?t={token}"


def _alive(port: int) -> bool:
    """Vrai si quelque chose écoute sur `127.0.0.1:<port>` (boucle locale seulement)."""
    try:
        with socket.create_connection((HOST, port), timeout=1.0):
            return True
    except OSError:
        return False


def read_running_instance(data_dir: Path) -> str | None:
    """URL de l'instance déjà lancée d'après `app.lock`, ou `None` (aucune écriture).

    Un verrou dont le port n'écoute plus (arrêt brutal) est considéré périmé.
    """
    try:
        info = json.loads((data_dir / LOCK_NAME).read_text(encoding="utf-8"))
        port, token = int(info["port"]), str(info["token"])
    except (OSError, ValueError, KeyError, TypeError):
        return None
    return url_for(port, token) if _alive(port) else None


def _take_lock(data_dir: Path, port: int, token: str) -> Path:
    """Crée `app.lock` de façon exclusive et atomique, contenu déjà écrit.

    Un verrou périmé est écarté par renommage atomique : un seul lancement peut le déplacer,
    et s'il a déplacé le verrou tout neuf d'un concurrent, il le remet en place.
    `FileExistsError` si une instance vivante détient le verrou.
    """
    lock = data_dir / LOCK_NAME
    tmp = data_dir / f"{LOCK_NAME}.{os.getpid()}.tmp"
    stale = data_dir / f"{LOCK_NAME}.{os.getpid()}.stale"
    tmp.write_text(json.dumps({"pid": os.getpid(), "port": port, "token": token}), "utf-8")
    try:
        for _ in range(3):
            try:
                os.link(tmp, lock)
                return lock
            except FileExistsError:
                pass
            try:
                seen = lock.read_bytes()
            except FileNotFoundError:
                continue
            if read_running_instance(data_dir) is not None:
                raise FileExistsError(str(lock))
            try:
                os.replace(lock, stale)
            except FileNotFoundError:
                continue  # un concurrent l'a déjà écarté
            if stale.read_bytes() != seen:  # verrou neuf d'un concurrent : on le rend
                with contextlib.suppress(FileExistsError):
                    os.link(stale, lock)
                raise FileExistsError(str(lock))
        raise FileExistsError(str(lock))
    finally:
        tmp.unlink(missing_ok=True)
        stale.unlink(missing_ok=True)


def setup_logging(data_dir: Path, settings: Settings) -> logging.Handler:
    """Journal en rotation dans `<data>/logs/app.log` ; aucun contenu de fichier d'apprenant."""
    path = data_dir / LOG_RELATIVE
    path.parent.mkdir(parents=True, exist_ok=True)
    handler = logging.handlers.RotatingFileHandler(
        path,
        maxBytes=settings.log_max_bytes,
        backupCount=settings.log_backup_count,
        encoding="utf-8",
    )
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
    for name in ("wavedevsecops", "uvicorn"):
        logger = logging.getLogger(name)
        logger.setLevel(logging.INFO)
        logger.addHandler(handler)
    return handler


class _Server(uvicorn.Server):
    """Serveur lancé dans un fil : pas de gestionnaires de signaux."""

    def install_signal_handlers(self) -> None:  # noqa: D401
        return None


@dataclass
class Instance:
    """Une instance en cours : serveur uvicorn dans un fil, verrou et journal."""

    data_dir: Path
    port: int
    token: str
    server: _Server
    thread: threading.Thread
    lock: Path
    log_handler: logging.Handler
    sock: socket.socket

    @property
    def url(self) -> str:
        return url_for(self.port, self.token)

    def stop(self) -> None:
        shutdown_app(self.server.config.app)  # ferme les flux SSE, sinon uvicorn les attend
        self.server.should_exit = True
        self.thread.join(timeout=10)
        self.sock.close()
        self.lock.unlink(missing_ok=True)
        for name in ("wavedevsecops", "uvicorn"):
            logging.getLogger(name).removeHandler(self.log_handler)
        self.log_handler.close()


def start_instance(settings: Settings, now: datetime | None = None) -> Instance:
    """Prépare les données, choisit un port libre, prend le verrou et démarre le serveur.

    Précondition : aucune instance vivante (voir `read_running_instance`).
    """
    data_dir = settings.resolved_data_dir()
    data_dir.mkdir(parents=True, exist_ok=True)
    # Verrou d'abord : un lancement concurrent qui perd n'écrit ni journal ni progress.json.
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.bind((HOST, 0))  # port libre choisi par le système
        sock.listen(128)
        port = sock.getsockname()[1]
        token = secrets.token_urlsafe(32)
        lock = _take_lock(data_dir, port, token)
    except BaseException:
        sock.close()
        raise
    handler: logging.Handler | None = None
    try:
        handler = setup_logging(data_dir, settings)
        ensure_progress(data_dir, now or datetime.now().astimezone())
        config = uvicorn.Config(
            create_app(
                port=port, token=token, settings=settings, on_diagnostic=_print_diagnostic
            ),
            log_config=None,
            access_log=False,  # l'URL de lancement contient le jeton
            lifespan="off",
        )
        server = _Server(config)
        thread = threading.Thread(target=server.run, kwargs={"sockets": [sock]}, daemon=True)
        thread.start()
        deadline = time.monotonic() + START_TIMEOUT_S
        while not server.started and thread.is_alive() and time.monotonic() < deadline:
            time.sleep(0.02)
        if not server.started:
            server.should_exit = True
            raise AppError(
                "Le serveur local n'a pas démarré.",
                f"Consultez le journal {data_dir / LOG_RELATIVE}, puis relancez la commande.",
            )
    except BaseException:
        sock.close()
        lock.unlink(missing_ok=True)
        if handler is not None:
            for name in ("wavedevsecops", "uvicorn"):
                logging.getLogger(name).removeHandler(handler)
            handler.close()
        raise
    logging.getLogger("wavedevsecops").info("Serveur local démarré sur le port %d", port)
    return Instance(data_dir, port, token, server, thread, lock, handler, sock)


def _print_diagnostic(checks: list[DiagnosticCheck], texts: dict) -> None:
    """Écrit le diagnostic dans la console de lancement (même contenu que la page)."""
    print("\n".join(diagnostic.console_lines(checks, texts)), flush=True)


def _console(url: str, existing: bool) -> None:
    lines = [
        "WaveDevSecOps est déjà lancé : ouverture de l'instance existante."
        if existing
        else "WaveDevSecOps est lancé.",
        f"Adresse locale : {url.split('?')[0]}",
        "Si votre poste passe par un proxy, ajoutez 127.0.0.1 et localhost à la variable "
        "NO_PROXY.",
        "Pour ouvrir l'interface dans une fenêtre dédiée : wavedevsecops --window "
        "(extra « window » à installer).",
    ]
    if not existing:
        lines.append("Pour arrêter : Ctrl+C.")
    print("\n".join(lines), flush=True)


def _run_window(url: str) -> bool:
    """Ouvre l'interface dans pywebview ; `False` si l'extra `window` n'est pas installé."""
    try:
        import webview
    except ImportError:
        return False
    webview.create_window("WaveDevSecOps", url)
    webview.start()
    return True


def _wait(instance: Instance) -> bool:
    """Attend la fin du serveur ; `False` s'il s'est arrêté sans qu'on le lui demande."""
    while instance.thread.is_alive():
        instance.thread.join(timeout=0.5)  # reste interruptible par Ctrl+C
    return bool(instance.server.should_exit)


def _error(cause: str, action: str) -> int:
    print(f"{cause}\n{action}", file=sys.stderr)
    return 1


def main(
    argv: Sequence[str] | None = None,
    *,
    settings: Settings | None = None,
    opener: Opener = webbrowser.open,
) -> int:
    parser = argparse.ArgumentParser(
        prog="wavedevsecops", description="Lance WaveDevSecOps sur un serveur local protégé."
    )
    parser.add_argument(
        "--window",
        action="store_true",
        help="ouvre l'interface dans une fenêtre pywebview au lieu du navigateur",
    )
    args = parser.parse_args(argv)
    settings = settings or get_settings()
    data_dir = settings.resolved_data_dir()

    existing = read_running_instance(data_dir)
    if existing is not None:
        _console(existing, existing=True)
        opener(existing)
        return 0

    try:
        instance = start_instance(settings)
    except AppError as exc:
        return _error(exc.cause_text, exc.action_text)
    except FileExistsError:  # une autre instance a pris le verrou entre-temps
        url = read_running_instance(data_dir)
        if url is None:
            print(
                "Impossible de prendre le verrou de WaveDevSecOps.\n"
                f"Supprimez le fichier {data_dir / LOCK_NAME} puis relancez la commande.",
                file=sys.stderr,
            )
            return 1
        opener(url)
        return 0
    except OSError as exc:  # droits, disque plein, liens physiques non pris en charge…
        return _error(
            f"WaveDevSecOps n'a pas pu écrire dans son dossier de données {data_dir} "
            f"({exc.strerror or exc}).",
            "Vérifiez les droits et la place libre de ce dossier, ou choisissez-en un autre "
            "sur un disque local avec la variable WDS_DATA_DIR, puis relancez la commande.",
        )
    code = 0
    try:
        _console(instance.url, existing=False)
        if args.window:
            if not _run_window(instance.url):
                print(
                    "L'extra « window » n'est pas installé : ouverture dans le navigateur. "
                    "Installez-le avec : uv sync --extra window",
                    file=sys.stderr,
                )
                opener(instance.url)
                code = _stopped_code(instance)
        else:
            opener(instance.url)
            code = _stopped_code(instance)
    except KeyboardInterrupt:
        pass
    finally:
        instance.stop()
    return code


def _stopped_code(instance: Instance) -> int:
    if _wait(instance):
        return 0
    return _error(
        "Le serveur local s'est arrêté de façon inattendue.",
        f"Consultez le journal {instance.data_dir / LOG_RELATIVE}, puis relancez la commande.",
    )
