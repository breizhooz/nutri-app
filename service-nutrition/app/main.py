from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy import select, func

from app.api.routes import admin, calculate, macro_errors, nutrition_items, stats
from app.core.config import settings
from app.db.session import get_engine
from app.i18n.middleware import LocaleMiddleware
from app.models.nutrition_item import NutritionItem, NutritionSource

logger = logging.getLogger(__name__)


async def _bootstrap_ciqual() -> None:
    """
    Au démarrage : si aucun aliment Ciqual n'est en base,
    déclenche le téléchargement + import en tâche de fond.
    La tâche Celery est autonome, elle ne bloque pas le démarrage.
    """
    try:
        from sqlalchemy.ext.asyncio import AsyncSession

        engine = get_engine()
        async with AsyncSession(engine) as session:
            result = await session.execute(
                select(func.count()).where(
                    NutritionItem.source == NutritionSource.ciqual
                )
            )
            count = result.scalar_one()

        if count == 0:
            logger.info("Aucune donnée Ciqual en base — déclenchement de l'import initial.")
            from app.tasks.nutrition_task import import_ciqual
            import_ciqual.delay()
        else:
            logger.info("Données Ciqual présentes (%d items) — import ignoré.", count)

    except Exception:
        logger.exception("Erreur lors du bootstrap Ciqual — le service démarre quand même.")


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

    app.add_middleware(LocaleMiddleware)

    app.include_router(calculate.router, prefix="/api/v1/calculate")
    app.include_router(nutrition_items.router, prefix="/api/v1/nutrition-items")
    app.include_router(macro_errors.router, prefix="/api/v1")
    app.include_router(stats.router, prefix="/api/v1")
    app.include_router(admin.router, prefix="/api/v1")

    @app.get("/health")
    async def health():
        return {"status": "ok"}

    return app


app = create_app()