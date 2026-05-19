import asyncio
import logging

from celery_app import celery

logger = logging.getLogger(__name__)


@celery.task(name="tasks.ciqual_import.run", bind=True, max_retries=3)
def run(self):
    """Import mensuel du CSV Ciqual en base + index Elasticsearch."""
    asyncio.run(_run_async())


async def _run_async():
    from app.core.config import settings
    from app.db.session import _session_factory
    from app.services.ciqual_importer import CiqualImporter

    async with _session_factory()() as session:
        importer = CiqualImporter(session)
        created, skipped = await importer.import_csv(settings.CIQUAL_CACHE_PATH)
        logger.info("Ciqual import done: created=%d skipped=%d", created, skipped)