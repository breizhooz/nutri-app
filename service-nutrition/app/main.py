from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy import text

from nutri_shared.errors import register_error_handlers

from app.api.routes import (
    admin,
    calculate,
    macro_errors,
    nutrition_items,
    stats,
    lookup,
)
from app.core.config import settings
from app.i18n.middleware import LocaleMiddleware

from nutri_shared.core.logger import configure_logging
from nutri_shared.core.middleware import RequestLoggingMiddleware
from nutri_shared.core.telemetry import setup_telemetry

logger = logging.getLogger(__name__)

configure_logging("service-nutrition")


async def _bootstrap_ciqual() -> None:
    try:
        from app.core.config import settings
        from app.models.ciqual_archive import CiqualArchive
        from app.db.session import get_engine
        from sqlalchemy import select
        from sqlalchemy.ext.asyncio import AsyncSession

        filename = settings.CIQUAL_DOWNLOAD_URL.split("/")[-1]
        engine = get_engine()
        async with AsyncSession(engine) as session:
            result = await session.execute(
                select(CiqualArchive).where(CiqualArchive.filename == filename)
            )
            already_done = result.scalar_one_or_none() is not None

        if not already_done:
            logger.info("Archive '%s' non importée — déclenchement import.", filename)
            from app.tasks.nutrition_task import import_ciqual

            import_ciqual.delay()
        else:
            logger.info("Archive '%s' déjà importée — rien à faire.", filename)
    except Exception:
        logger.exception("Erreur bootstrap Ciqual — le service démarre quand même.")


@asynccontextmanager
async def lifespan(app: FastAPI):
    await _bootstrap_ciqual()
    yield


def create_app() -> FastAPI:
    app = FastAPI(
        title="Service Nutrition",
        version="1.0.0",
        debug=settings.DEBUG,
        lifespan=lifespan,
    )
    app.add_middleware(RequestLoggingMiddleware)

    app.add_middleware(LocaleMiddleware)
    register_error_handlers(app)
    setup_telemetry("service-nutrition", app)

    app.include_router(lookup.router, prefix="/api/v1/nutrition-items")
    app.include_router(calculate.router, prefix="/api/v1/calculate")
    app.include_router(nutrition_items.router, prefix="/api/v1/nutrition-items")
    app.include_router(macro_errors.router, prefix="/api/v1")
    app.include_router(stats.router, prefix="/api/v1")
    app.include_router(admin.router, prefix="/api/v1")

    @app.get("/health")
    async def health():
        return {"status": "ok", "service": "service-nutrition"}

    @app.get("/health/db")
    async def health_db():
        try:
            from app.db.session import get_engine

            async with get_engine().connect() as conn:
                await conn.execute(text("SELECT 1"))
            db_status = "ok"
        except Exception as e:
            db_status = f"error: {e}"
        return {"status": "ok", "service": "service-nutrition", "database": db_status}

    return app


app = create_app()
