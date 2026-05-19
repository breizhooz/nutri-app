import asyncio
import logging

from celery import Celery

from app.core.config import settings

celery_app = Celery(
    "nutrition_tasks",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
)

celery_app.conf.timezone = "Europe/Paris"
celery_app.conf.beat_schedule = {
    "import-ciqual-monthly": {
        "task": "app.tasks.nutrition_tasks.import_ciqual",
        "schedule": 2_592_000,  # 30 jours
    },
    "enrich-off-daily": {
        "task": "app.tasks.nutrition_tasks.enrich_from_off",
        "schedule": 86_400,
    },
}

logger = logging.getLogger(__name__)


@celery_app.task(name="app.tasks.nutrition_tasks.import_ciqual")
def import_ciqual() -> dict:
    """
    Télécharge le ZIP Ciqual depuis l'ANSES, extrait le CSV,
    puis upserte tous les aliments en base. Autonome, sans intervention admin.
    """
    from app.db.session import get_engine
    from app.repositories.nutrition_item_repository import NutritionItemRepository
    from app.services.ciqual_downloader import CiqualDownloader
    from app.services.ciqual_importer import CiqualImporter
    from sqlalchemy.ext.asyncio import AsyncSession

    async def _run() -> int:
        downloader = CiqualDownloader()
        csv_path = await downloader.download()
        logger.info("CSV Ciqual téléchargé : %s", csv_path)

        engine = get_engine()
        async with AsyncSession(engine) as session:
            repo = NutritionItemRepository(session)
            importer = CiqualImporter(repo)
            count = await importer.import_all(csv_path)
            await session.commit()
            return count

    count = asyncio.run(_run())
    logger.info("Import Ciqual terminé : %d items upsertés", count)
    return {"imported": count}


@celery_app.task(name="app.tasks.nutrition_tasks.enrich_from_off")
def enrich_from_off(batch_size: int = 50) -> dict:
    """Enrichit les NutritionItems sans données OFF via l'API Open Food Facts."""
    from app.db.session import get_engine
    from app.models.nutrition_item import NutritionItem, NutritionSource
    from app.repositories.nutrition_item_repository import NutritionItemRepository
    from app.services.open_food_facts_client import OpenFoodFactsClient
    from sqlalchemy import select
    from sqlalchemy.ext.asyncio import AsyncSession

    async def _run() -> int:
        engine = get_engine()
        client = OpenFoodFactsClient()
        enriched = 0

        async with AsyncSession(engine) as session:
            stmt = (
                select(NutritionItem)
                .where(NutritionItem.off_enriched.is_(False))
                .where(NutritionItem.source != NutritionSource.open_food_facts)
                .limit(batch_size)
            )
            result = await session.execute(stmt)
            items: list[NutritionItem] = list(result.scalars().all())

            for item in items:
                product = await client.search(item.nom_fr)
                if product is None:
                    item.off_enriched = True
                    continue

                if item.calories is None and product.calories is not None:
                    item.calories = product.calories
                if item.proteines is None and product.proteines is not None:
                    item.proteines = product.proteines
                if item.glucides is None and product.glucides is not None:
                    item.glucides = product.glucides
                if item.lipides is None and product.lipides is not None:
                    item.lipides = product.lipides
                if item.fibres is None and product.fibres is not None:
                    item.fibres = product.fibres

                item.off_id = product.off_id
                item.off_enriched = True
                enriched += 1

            await session.commit()
        return enriched

    count = asyncio.run(_run())
    logger.info("Enrichissement OFF terminé : %d items", count)
    return {"enriched": count}


@celery_app.task(name="app.tasks.nutrition_tasks.reindex_elasticsearch")
def reindex_elasticsearch() -> dict:
    """Réindexe tous les NutritionItems dans Elasticsearch."""
    from app.db.session import get_engine
    from app.services.lookup_service import LookupService
    from sqlalchemy import select
    from sqlalchemy.ext.asyncio import AsyncSession
    from app.models.nutrition_item import NutritionItem

    async def _run() -> int:
        engine = get_engine()
        async with AsyncSession(engine) as session:
            result = await session.execute(select(NutritionItem))
            items = list(result.scalars().all())
            lookup = LookupService()
            await lookup.bulk_index(items)
            return len(items)

    count = asyncio.run(_run())
    logger.info("Réindexation Elasticsearch terminée : %d items", count)
    return {"indexed": count}