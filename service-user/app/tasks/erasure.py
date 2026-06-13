"""Tâche Celery d'effacement RGPD (art. 17).

Purge les données d'un compte dans les autres microservices, avec reprise sur
échec partiel : tant que des cibles restent en échec, un nouvel essai est
programmé (backoff Celery) jusqu'à ``max_retries``. Le journal ``erasure_targets``
garde la trace des cibles restantes pour un rejeu ultérieur.
"""

import asyncio
import logging
import uuid

from celery_app import celery_app

from app.db.session import _session_factory
from app.services import erasure_service

logger = logging.getLogger(__name__)


@celery_app.task(
    bind=True,
    name="erasure.process_account",
    max_retries=5,
    default_retry_delay=60,
    acks_late=True,
)
def erase_account_data_task(self, request_id: str) -> None:
    """Exécute l'effacement cross-service pour ``request_id``."""
    still_failed = asyncio.run(_process(request_id))
    if still_failed:
        logger.warning(
            "Effacement incomplet (request=%s) : %s — nouvel essai programmé",
            request_id,
            still_failed,
        )
        raise self.retry(exc=RuntimeError(f"erasure incomplete: {still_failed}"))


async def _process(request_id: str) -> list[str]:
    """Ouvre une session et délègue à l'orchestrateur."""
    factory = _session_factory()
    async with factory() as session:
        return await erasure_service.process_erasure_request(
            session, uuid.UUID(request_id)
        )
