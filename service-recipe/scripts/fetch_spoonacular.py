"""Récupère immédiatement N recettes Spoonacular et les met en cache.

Pratique pour tester sans attendre la tâche quotidienne (Celery beat).

Usage : python -m scripts.fetch_spoonacular [N]
        (N entre 1 et 5 ; défaut = SPOONACULAR_DAILY_COUNT)

Prérequis : SPOONACULAR_API_KEY et DATABASE_URL renseignés (conf/.env / env).
"""

import asyncio
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

os.environ.setdefault("ELASTICSEARCH_URL", "http://elasticsearch:9200")
os.environ.setdefault("ELASTICSEARCH_INDEX_RECIPES", "recipes")
os.environ.setdefault("JWT_SECRET", "fetch-secret")


async def _run(count: int | None) -> None:
    from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
    from sqlalchemy.pool import NullPool

    from app.core.config import settings
    from app.repositories.spoonacular_cache_repository import (
        SpoonacularCacheRepository,
    )
    from app.services.spoonacular_cache_service import SpoonacularCacheService

    n = count if count is not None else settings.SPOONACULAR_DAILY_COUNT
    if not settings.SPOONACULAR_API_KEY:
        print(
            "SPOONACULAR_API_KEY absent : le fetch sera un no-op. "
            "Renseignez-le dans conf/.env."
        )

    engine = create_async_engine(settings.DATABASE_URL, poolclass=NullPool)
    try:
        async with AsyncSession(engine, expire_on_commit=False) as session:
            repository = SpoonacularCacheRepository(session)
            service = SpoonacularCacheService(repository)
            report = await service.fetch_and_cache(n)
            total = await repository.count()
    finally:
        await engine.dispose()

    print(
        f"{report.fetched} recette(s) récupérée(s) : "
        f"{report.created} créée(s), {report.updated} mise(s) à jour. "
        f"Cache : {total} recette(s) au total."
    )


if __name__ == "__main__":
    arg = None
    if len(sys.argv) > 1:
        try:
            arg = int(sys.argv[1])
        except ValueError:
            print("N doit être un entier entre 1 et 5.")
            raise SystemExit(1)
    asyncio.run(_run(arg))
