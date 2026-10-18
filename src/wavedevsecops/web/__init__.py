"""Application web locale (FastAPI) et sa protection (AD-19)."""

from wavedevsecops.web.app import SESSION_COOKIE, create_app, shutdown_app

__all__ = ["SESSION_COOKIE", "create_app", "shutdown_app"]
