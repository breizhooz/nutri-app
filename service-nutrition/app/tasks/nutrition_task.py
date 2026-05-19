import asyncio
import logging

from celery_app import celery_app

logger = logging.getLogger(__name__)


def _make_engine():
    from sqlalchemy.ext.asyncio import create_async_engine
    from sqlalchemy.pool import NullPool
    from app.core.config import settings
    return create_async_engine(settings.DATABASE_URL, poolclass=NullPool)


@celery_app.task(name="app.tasks.nutrition_tasks.import_ciqual")
def import_ciqual() -> dict:
    """
    Télécharge le ZIP Ciqual depuis l'ANSES, extrait le CSV,
    puis upserte tous les aliments en base. Autonome, sans intervention admin.
    """
    async def _run() -> int:
        from app.services.ciqual_downloader import CiqualDownloader
        from app.services.ciqual_importer import CiqualImporter
        from sqlalchemy.ext.asyncio import AsyncSession

        downloader = CiqualDownloader()
        extract_dir, sha256, filename = await downloader.download()

        engine = _make_engine()
        try:
            async with AsyncSession(engine) as session:
                importer = CiqualImporter(session)
                if await importer.already_imported(sha256):
                    logger.info("Archive déjà importée (sha256 identique) — import ignoré.")
                    import shutil
                    shutil.rmtree(extract_dir, ignore_errors=True)
                    return 0
                return await importer.import_archive(extract_dir, sha256, filename)
        finally:
            await engine.dispose()

    count = asyncio.run(_run())
    logger.info("Import Ciqual terminé : %d items upsertés", count)
    return {"imported": count}


@celery_app.task(name="app.tasks.nutrition_tasks.enrich_from_off")
def enrich_from_off(batch_size: int = 50) -> dict:
    """Enrichit les NutritionItems sans données OFF via l'API Open Food Facts."""
    async def _run() -> int:
        from app.models.nutrition_item import NutritionItem, NutritionSource
        from app.services.open_food_facts_client import OpenFoodFactsClient
        from sqlalchemy import select
        from sqlalchemy.ext.asyncio import AsyncSession

        engine = _make_engine()
        client = OpenFoodFactsClient()
        enriched = 0

        try:
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
        finally:
            await engine.dispose()
        return enriched

    count = asyncio.run(_run())
    logger.info("Enrichissement OFF terminé : %d items", count)
    return {"enriched": count}


@celery_app.task(name="app.tasks.nutrition_tasks.reindex_elasticsearch")
def reindex_elasticsearch() -> dict:
    """Réindexe tous les NutritionItems dans Elasticsearch."""
    async def _run() -> int:
        from app.models.nutrition_item import NutritionItem
        from app.services.lookup_service import LookupService
        from sqlalchemy import select
        from sqlalchemy.ext.asyncio import AsyncSession

        engine = _make_engine()
        try:
            async with AsyncSession(engine) as session:
                result = await session.execute(select(NutritionItem))
                items = list(result.scalars().all())
                lookup = LookupService()
                await lookup.bulk_index(items)
                return len(items)
        finally:
            await engine.dispose()

    count = asyncio.run(_run())
    logger.info("Réindexation Elasticsearch terminée : %d items", count)
    return {"indexed": count}