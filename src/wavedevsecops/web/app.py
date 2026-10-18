"""Application FastAPI : jeton de lancement, cookie de session, `Host` et `Origin` (AD-19).

Aucune réponse ne porte d'en-tête CORS : aucun `CORSMiddleware`, et les refus n'en ajoutent pas.
"""

from __future__ import annotations

import secrets
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

from wavedevsecops.web.shell import CURRENT_MILESTONE, delivered_surfaces

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


def create_app(*, port: int, token: str, milestone: str = CURRENT_MILESTONE) -> FastAPI:
    """Construit l'application pour une instance : `port` et `token` fixés au lancement."""
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
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
            # Point public, en lecture seule : POST sans cookie ni contrôle d'origine.
            if request.method != "POST":
                return refuse(405, "Ce point n'accepte que la méthode POST.")
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

    for surface in surfaces:
        app.add_api_route(surface.path, shell_page, methods=["GET"], include_in_schema=False)

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
                "surfaces": [
                    {"key": s.key, "label": s.label, "path": s.path, "subtitle": s.subtitle}
                    for s in surfaces
                ],
            }
        )

    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

    return app
