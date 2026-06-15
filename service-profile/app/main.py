"""Point d'entrée FastAPI du service-profile."""

import logging

from fastapi import FastAPI
from sqlalchemy import text
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from nutri_shared.errors import register_error_handlers

from app.api.routes import blobs, internal
from app.db.session import get_engine
from app.i18n.loader import t

from nutri_shared.core.logger import configure_logging
from nutri_shared.core.middleware import RequestLoggingMiddleware
from nutri_shared.core.telemetry import setup_telemetry

logger = logging.getLogger(__name__)
configure_logging("service-profile")


class LocaleMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: object) -> Response:
        raw = request.headers.get("Accept-Language", "fr")
        locale = raw.split(",")[0].split("-")[0].lower()
        request.state.locale = locale if locale in ("fr", "en") else "fr"
        return await call_next(request)


app = FastAPI(title="service-profile", version="0.1.0")
app.add_middleware(LocaleMiddleware)
app.add_middleware(RequestLoggingMiddleware)
app.state.translate = t.get

register_error_handlers(app)
setup_telemetry("service-profile", app)

# E2E zero-knowledge (Phase 5) : service-profile n'expose plus que le coffre de
# blobs chiffrés opaques + les endpoints internes RGPD (effacement/export). Toute
# la santé en clair (profil, médical, préférences, suivi, calculs) a migré côté
# client dans le coffre chiffré. Cf. docs/rgpd/plan_dpo.md.
app.include_router(blobs.router, prefix="/api/v1/profiles", tags=["blobs"])
app.include_router(internal.router, prefix="/api/v1/internal", tags=["internal"])


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "service-profile"}


@app.get("/health/db")
async def health_db() -> dict[str, str]:
    try:
        async with get_engine().connect() as conn:
            await conn.execute(text("SELECT 1"))
        db_status = "ok"
    except Exception as exc:
        logger.error("Healthcheck DB échoué : %s", exc)
        db_status = f"error: {exc}"
    return {"status": "ok", "service": "service-profile", "database": db_status}
