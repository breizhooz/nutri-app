"""Tâche Celery de purge de rétention (RGPD art. 5.1.e, Phase 4) — service-nutrition.

Planifiée via le ``beat_schedule`` de ``celery_app`` (beat déjà actif :
celery-beat-nutrition). Ouvre une session dédiée et délègue à ``retention_service``.
"""

import asyncio
import logging

from celery_app import celery_app

from app.core.config import settings
from app.services import retention_service

logger = logging.getLogger(__name__)


def _make_engine():
    from sqlalchemy.ext.asyncio import create_async_engine
    from sqlalchemy.pool import NullPool

    return create_async_engine(settings.DATABASE_URL, poolclass=NullPool)


@celery_app.task(name="retention.purge_old_macro_errors")
def purge_old_macro_errors() -> int:
    """Purge quotidienne des macro_errors au-delà de la rétention."""
    return asyncio.run(_run())


async def _run() -> int:
    from sqlalchemy.ext.asyncio import async_sessionmaker

    engine = _make_engine()
    try:
        factory = async_sessionmaker(engine, expire_on_commit=False)
        async with factory() as session:
            return await retention_service.purge_old_macro_errors(
                session, settings.MACRO_ERROR_RETENTION_DAYS
            )
    finally:
        await engine.dispose()
