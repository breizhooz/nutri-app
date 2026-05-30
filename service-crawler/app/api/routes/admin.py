"""Routes admin du crawler — supervision de la file d'attente Celery.

Réservé aux administrateurs (claim ``user_admin``).
"""

from typing import Any

from fastapi import APIRouter, Depends
from fastapi.concurrency import run_in_threadpool

from app.core.deps import require_admin
from app.schemas.queue import QueueSnapshot
from app.services.queue_service import QueueService

router = APIRouter()


class QueueServiceFactory:
    @staticmethod
    def inject() -> QueueService:
        return QueueService()


@router.get("/queue", response_model=QueueSnapshot)
async def get_queue(
    _: dict[str, Any] = Depends(require_admin),
    service: QueueService = Depends(QueueServiceFactory.inject),
) -> QueueSnapshot:
    """Instantané de la file d'attente Celery (tâches actives / planifiées / réservées)."""
    # inspect() est bloquant → exécution hors de l'event loop.
    return await run_in_threadpool(service.snapshot)
