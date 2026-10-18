"""Application FastAPI : jeton de lancement, cookie de session, `Host` et `Origin` (AD-19).

Aucune réponse ne porte d'en-tête CORS : aucun `CORSMiddleware`, et les refus n'en ajoutent pas.
"""

from __future__ import annotations

import secrets

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, PlainTextResponse, RedirectResponse, Response

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
_INDEX = (
    "<!doctype html><html lang=\"fr\"><meta charset=\"utf-8\">"
    "<title>WaveDevSecOps</title><h1>WaveDevSecOps</h1>"
    "<p>Le serveur local fonctionne. L'interface arrive avec les prochaines étapes.</p></html>"
)


def _same(a: str, b: str) -> bool:
    return secrets.compare_digest(a.encode("utf-8"), b.encode("utf-8"))


def create_app(*, port: int, token: str) -> FastAPI:
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
        if request.method == "POST" and request.headers.get("origin") != f"http://{host}":
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

    @app.get("/", response_class=HTMLResponse)
    async def index() -> str:
        return _INDEX

    return app
