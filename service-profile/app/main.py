"""Point d'entrée FastAPI du service-profile."""
import logging

from fastapi import FastAPI
from sqlalchemy import text
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.api.routes import medical, preferences, profile, tracker
from app.db.session import get_engine

logger = logging.getLogger(__name__)


class LocaleMiddleware(BaseHTTPMiddleware):
    """Détecte la locale depuis Accept-Language et l'injecte dans request.state."""

    async def dispatch(self, request: Request, call_next: object) -> Response:  # type: ignore[override]
        """Extrait la locale principale du header Accept-Language (défaut : 'fr')."""
        raw = request.headers.get("Accept-Language", "fr")
        locale = raw.split(",")[0].split("-")[0].lower()
        request.state.locale = locale if locale in ("fr", "en") else "fr"
        return await call_next(request)  # type: ignore[arg-type]


app = FastAPI(title="service-profile", version="0.1.0")
app.add_middleware(LocaleMiddleware)

app.include_router(profile.router, prefix="/api/v1/profiles", tags=["profile"])
app.include_router(tracker.router, prefix="/api/v1/profiles", tags=["tracker"])
app.include_router(medical.router, prefix="/api/v1/profiles", tags=["medical"])
app.include_router(preferences.router, prefix="/api/v1/profiles", tags=["preferences"])


@app.get("/health")
async def health() -> dict[str, str]:
    """Retourne le statut de vie du service."""
    return {"status": "ok", "service": "service-profile"}


@app.get("/health/db")
async def health_db() -> dict[str, str]:
    """Vérifie la connectivité à la base de données."""
    try:
        async with get_engine().connect() as conn:
            await conn.execute(text("SELECT 1"))
        db_status = "ok"
    except Exception as exc:
        logger.error("Healthcheck DB échoué : %s", exc)
        db_status = f"error: {exc}"
    return {"status": "ok", "service": "service-profile", "database": db_status}