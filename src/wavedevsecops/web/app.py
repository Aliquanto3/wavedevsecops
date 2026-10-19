"""Application FastAPI : jeton de lancement, cookie de session, `Host` et `Origin` (AD-19).

Aucune réponse ne porte d'en-tête CORS : aucun `CORSMiddleware`, et les refus n'en ajoutent pas.
"""

from __future__ import annotations

import asyncio
import logging
import secrets
import threading
from collections.abc import Callable
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import (
    FileResponse,
    JSONResponse,
    PlainTextResponse,
    RedirectResponse,
    Response,
)
from fastapi.staticfiles import StaticFiles

from wavedevsecops import diagnostic, osv, terminal
from wavedevsecops.config import Settings, get_settings
from wavedevsecops.contracts import DiagnosticCheck
from wavedevsecops.engine import (
    WorkspaceManager,
    code_intents,
    designation,
    hints,
    pipeline,
    pr_intents,
    restart,
)
from wavedevsecops.web.blockers import blockers_body
from wavedevsecops.web.catalogue import install_catalogue_routes
from wavedevsecops.web.code import install_code_routes
from wavedevsecops.web.exercise import register_exercise_intent
from wavedevsecops.web.explanations import install_explanation_routes
from wavedevsecops.web.glossary import install_glossary_routes
from wavedevsecops.web.shell import CURRENT_MILESTONE, delivered_surfaces, track_options
from wavedevsecops.web.workspaces import install_workspace_routes

SESSION_COOKIE = "wds_session"
PUBLIC_PREFIX = "/osv/"

_HOST_REFUSED = (
    "Requête refusée : l'adresse utilisée n'est pas celle de WaveDevSecOps. "
    "Ouvrez l'adresse affichée dans la console de lancement."
)
_ORIGIN_REFUSED = "Requête refusée : elle ne vient pas de la page de WaveDevSecOps."
_NO_SESSION = (
    "Accès refusé : ouvrez WaveDevSecOps avec l'adresse complète affichée dans la console "
    "de lancement, ou relancez la commande `uv run wavedevsecops`."
)
STATIC_DIR = Path(__file__).resolve().parent / "static"
# Tout vient de l'application elle-même (AD-13) : le navigateur refuse le reste.
CONTENT_SECURITY_POLICY = (
    "default-src 'none'; script-src 'self'; style-src 'self'; font-src 'self'; "
    "img-src 'self' data:; connect-src 'self'; base-uri 'none'; form-action 'self'; "
    "frame-ancestors 'none'"
)


def _same(a: str, b: str) -> bool:
    return secrets.compare_digest(a.encode("utf-8"), b.encode("utf-8"))


SEEN_MARKER = "diagnostic_seen"
"""Fichier de `<data>/` créé quand la page Diagnostic a été servie : fin du premier lancement."""
DiagnosticListener = Callable[[list[DiagnosticCheck], dict], None]


def create_app(
    *,
    port: int,
    token: str,
    milestone: str = CURRENT_MILESTONE,
    settings: Settings | None = None,
    on_diagnostic: DiagnosticListener | None = None,
    workspaces: WorkspaceManager | None = None,
) -> FastAPI:
    """Construit l'application pour une instance : `port` et `token` fixés au lancement.

    `on_diagnostic(checks, texts)` est appelé après chaque diagnostic (la console de lancement).
    `workspaces` : registre des espaces (par défaut, un `WorkspaceManager` neuf : un `boot_id`
    par lancement) ; `shutdown_app` l'arrête.
    """
    settings = settings or get_settings()
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
    run_lock = threading.Lock()
    last_report: dict[str, dict] = {}
    session = secrets.token_urlsafe(32)
    allowed_hosts = {f"127.0.0.1:{port}", f"localhost:{port}"}

    def refuse(status: int, text: str) -> Response:
        return PlainTextResponse(text, status_code=status)

    @app.middleware("http")
    async def protect(request: Request, call_next):
        host = request.headers.get("host", "").lower()
        if host not in allowed_hosts:
            return refuse(403, _HOST_REFUSED)
        path = request.url.path
        if path.startswith(PUBLIC_PREFIX):
            # Point public, en lecture seule : POST sans cookie. pip-audit n'envoie pas
            # d'`Origin` ; un navigateur en envoie un sur tout POST d'une autre page : refusé.
            if request.method != "POST":
                return refuse(405, "Ce point n'accepte que la méthode POST.")
            origin = request.headers.get("origin")
            if origin is not None and origin != f"http://{host}":
                return refuse(403, _ORIGIN_REFUSED)
            return await call_next(request)
        unsafe = request.method not in ("GET", "HEAD", "OPTIONS")
        if unsafe and request.headers.get("origin") != f"http://{host}":
            return refuse(403, _ORIGIN_REFUSED)
        if path == "/" and request.method == "GET":
            offered = request.query_params.get("t")
            if offered is not None and _same(offered, token):
                response = RedirectResponse("/", status_code=303)
                response.set_cookie(
                    SESSION_COOKIE, session, httponly=True, samesite="strict", path="/"
                )
                return response
        cookie = request.cookies.get(SESSION_COOKIE, "")
        if not _same(cookie, session):
            return refuse(401, _NO_SESSION)
        return await call_next(request)

    @app.middleware("http")
    async def harden(request: Request, call_next):
        response = await call_next(request)
        response.headers["Content-Security-Policy"] = CONTENT_SECURITY_POLICY
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        if request.url.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store"
        return response

    surfaces = delivered_surfaces(milestone)

    async def shell_page() -> Response:
        return FileResponse(STATIC_DIR / "index.html", media_type="text/html; charset=utf-8")

    marker = settings.resolved_data_dir() / SEEN_MARKER
    seen = {"now": False}  # vu pendant cette instance, même si le marqueur n'a pu s'écrire

    async def home_page() -> Response:
        # Premier lancement : le diagnostic s'ouvre d'office ; ensuite, l'accueil.
        if not seen["now"] and not marker.exists():
            return RedirectResponse("/diagnostic", status_code=303)
        return await shell_page()

    async def diagnostic_page() -> Response:
        seen["now"] = True
        try:
            marker.parent.mkdir(parents=True, exist_ok=True)
            marker.touch()
        except OSError:
            logging.getLogger("wavedevsecops").warning("Marqueur de premier lancement non écrit")
        return await shell_page()

    special = {"/": home_page, "/diagnostic": diagnostic_page}
    for surface in surfaces:
        handler = special.get(surface.path, shell_page)
        app.add_api_route(surface.path, handler, methods=["GET"], include_in_schema=False)

    @app.get("/api/diagnostic")
    async def diagnostic_state() -> JSONResponse:
        """Plan (lignes « En cours », textes) et dernier rapport s'il existe (AD-2, AD-16)."""
        body = diagnostic.plan(settings)
        body["report"] = last_report.get("report")
        return JSONResponse(body)

    @app.post("/api/diagnostic/run")
    async def diagnostic_run() -> JSONResponse:
        """Relance toutes les sondes et renvoie le rapport ; le même texte va à la console."""

        def work() -> dict:
            with run_lock:
                texts = diagnostic.load_texts(settings)
                checks = diagnostic.run_diagnostic(settings)
                report = diagnostic.build_report(checks, texts)
                last_report["report"] = report
                if on_diagnostic is not None:
                    try:
                        on_diagnostic(checks, texts)
                    except Exception:  # noqa: BLE001 - la console ne fait pas échouer la page
                        logging.getLogger("wavedevsecops").exception("Console du diagnostic")
                return report

        try:
            return JSONResponse(await asyncio.to_thread(work))
        except Exception:  # noqa: BLE001 - jamais de trace Python montrée à l'apprenant
            logging.getLogger("wavedevsecops").exception("Diagnostic en échec")
            texts = diagnostic.load_texts(settings)
            return JSONResponse({"error_text": texts["ui"]["failed"]}, status_code=500)

    @app.get("/api/health")
    async def health() -> dict[str, str]:
        """Point de vie sous cookie : le front l'interroge pour savoir si l'application répond."""
        return {"status": "ok"}

    @app.get("/api/shell")
    async def shell() -> JSONResponse:
        """Surfaces livrées par le jalon courant, dans l'ordre de l'en-tête (AD-2)."""
        return JSONResponse(
            {
                "milestone": milestone,
                "tracks": track_options(),
                "surfaces": [
                    {"key": s.key, "label": s.label, "path": s.path, "subtitle": s.subtitle}
                    for s in surfaces
                ],
            }
        )

    terminal.register_intents()
    pr_intents.register_intents()
    designation.register_intents()
    code_intents.register_intents()
    hints.register_intents()
    restart.register_intents()
    pipeline.register_intents()
    if pr_intents.refresh_after_command not in terminal.AFTER_COMMAND_HOOKS:
        terminal.AFTER_COMMAND_HOOKS.append(pr_intents.refresh_after_command)
    register_exercise_intent()
    workspaces = workspaces or WorkspaceManager(
        settings,
        osv_url=settings.osv_url(port),
        blockers=lambda scenario: blockers_body(scenario, settings),
    )
    app.state.workspaces = workspaces
    install_workspace_routes(app, workspaces)
    install_code_routes(app, workspaces)
    install_catalogue_routes(app, workspaces, settings)
    install_explanation_routes(app, settings)
    install_glossary_routes(app, settings)
    app.add_api_route(
        "/espace/{workspace_id}", shell_page, methods=["GET"], include_in_schema=False
    )

    osv_extract = osv.load_extract(settings.osv_path())

    @app.post("/osv/v1/query")
    async def osv_query(request: Request) -> JSONResponse:
        """Point OSV local (AD-11) : en mémoire, sans verrou ni file, sans cookie (AD-19)."""
        too_big = JSONResponse({"code": 3, "message": "Requête trop volumineuse."}, 413)
        try:
            announced = int(request.headers.get("content-length", "0"))
        except ValueError:
            announced = 0
        if announced > osv.MAX_BODY_BYTES:
            return too_big
        # Lecture par morceaux, coupée au-delà de la limite (corps sans `Content-Length`).
        body = bytearray()
        async for chunk in request.stream():
            body += chunk
            if len(body) > osv.MAX_BODY_BYTES:
                return too_big
        status, payload = osv.answer(osv_extract, bytes(body))
        return JSONResponse(payload, status_code=status)

    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

    return app


def shutdown_app(app: object) -> None:
    """Endort les espaces de l'application : files et surveillants arrêtés, flux SSE fermés."""
    state = getattr(app, "state", None)
    workspaces = getattr(state, "workspaces", None)
    if isinstance(workspaces, WorkspaceManager):
        workspaces.close()
