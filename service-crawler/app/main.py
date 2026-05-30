from fastapi import FastAPI
from sqlalchemy import text

from nutri_shared.errors import register_error_handlers

from app.db.session import get_engine
from app.api.routes import sources as sources_routes
from app.api.routes import results as results_routes
from app.api.routes import settings as settings_routes
from app.api.routes import ocr as ocr_routes
from app.api.routes import admin as admin_routes

from nutri_shared.core.logger import configure_logging
from nutri_shared.core.middleware import RequestLoggingMiddleware
from nutri_shared.core.telemetry import setup_telemetry

configure_logging("service-crawler")

app = FastAPI(title="service-crawler", version="0.1.0")

app.add_middleware(RequestLoggingMiddleware)
setup_telemetry("service-crawler", app)

register_error_handlers(app)

app.include_router(
    sources_routes.router, prefix="/api/v1/crawler/sources", tags=["sources"]
)
app.include_router(
    results_routes.router, prefix="/api/v1/crawler/results", tags=["results"]
)
app.include_router(
    settings_routes.router, prefix="/api/v1/crawler/settings", tags=["settings"]
)
app.include_router(ocr_routes.router, prefix="/api/v1/crawler/ocr", tags=["ocr"])
app.include_router(admin_routes.router, prefix="/api/v1/crawler/admin", tags=["admin"])


@app.get("/health")
async def health():
    return {"status": "ok", "service": "service-crawler"}


@app.get("/health/db")
async def health_db():
    try:
        async with get_engine().connect() as conn:
            await conn.execute(text("SELECT 1"))
        db_status = "ok"
    except Exception as e:
        db_status = f"error: {e}"
    return {"status": "ok", "service": "service-crawler", "database": db_status}
