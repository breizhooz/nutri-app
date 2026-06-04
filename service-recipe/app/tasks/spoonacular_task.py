import asyncio
import logging

from celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(name="app.tasks.spoonacular_task.fetch_daily_recipes")
def fetch_daily_recipes(count: int | None = None) -> dict:
    """Tâche quotidienne : récupère 1 à 5 recettes Spoonacular et les met en cache.

    ``count`` permet de forcer un nombre (sinon ``settings.SPOONACULAR_DAILY_COUNT``).
    Best-effort : sans clé Spoonacular ou en cas d'erreur API, aucune recette n'est
    récupérée et la tâche se termine proprement (rapport à zéro).
    """

    async def _run() -> dict:
        from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
        from sqlalchemy.pool import NullPool

        from app.core.config import settings
        from app.repositories.spoonacular_cache_repository import (
            SpoonacularCacheRepository,
        )
        from app.services.spoonacular_cache_service import SpoonacularCacheService

        n = count if count is not None else settings.SPOONACULAR_DAILY_COUNT

        engine = create_async_engine(settings.DATABASE_URL, poolclass=NullPool)
        try:
            async with AsyncSession(engine, expire_on_commit=False) as session:
                repository = SpoonacularCacheRepository(session)
                service = SpoonacularCacheService(repository)
                report = await service.fetch_and_cache(n)
        finally:
            await engine.dispose()

        return {
            "fetched": report.fetched,
            "created": report.created,
            "updated": report.updated,
        }

    result = asyncio.run(_run())
    logger.info("Fetch Spoonacular quotidien terminé : %s", result)
    return result
