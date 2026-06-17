"""Routes admin du crawler — supervision de la file Celery & session Instagram.

Réservé aux administrateurs (claim ``user_admin``).
"""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.concurrency import run_in_threadpool

from app.core.deps import require_admin
from app.schemas.instagram import (
    InstagramSessionInfo,
    InstagramSessionResult,
    InstagramSessionUpdate,
)
from app.schemas.queue import QueueSnapshot, TaskStatus
from app.services.instagram_session_service import (
    InstagramSessionError,
    InstagramSessionService,
)
from app.services.queue_service import QueueService

router = APIRouter()


class QueueServiceFactory:
    @staticmethod
    def inject() -> QueueService:
        return QueueService()


class InstagramSessionServiceFactory:
    @staticmethod
    def inject() -> InstagramSessionService:
        return InstagramSessionService()


@router.get("/queue", response_model=QueueSnapshot)
async def get_queue(
    _: dict[str, Any] = Depends(require_admin),
    service: QueueService = Depends(QueueServiceFactory.inject),
) -> QueueSnapshot:
    """Instantané de la file d'attente Celery (tâches actives / planifiées / réservées)."""
    # inspect() est bloquant → exécution hors de l'event loop.
    return await run_in_threadpool(service.snapshot)


@router.get("/tasks/{task_id}", response_model=TaskStatus)
async def get_task_status(
    task_id: str,
    _: dict[str, Any] = Depends(require_admin),
    service: QueueService = Depends(QueueServiceFactory.inject),
) -> TaskStatus:
    """Diagnostic d'une tâche Celery par son id : état, erreur et date du dernier échec."""
    # L'accès au result backend est bloquant → hors event loop.
    return await run_in_threadpool(service.task_status, task_id)


@router.get("/instagram/session", response_model=InstagramSessionInfo)
async def get_instagram_session(
    _: dict[str, Any] = Depends(require_admin),
    service: InstagramSessionService = Depends(InstagramSessionServiceFactory.inject),
) -> InstagramSessionInfo:
    """État de la session Instagram enregistrée (compte + date, sans le cookie). Admin-only."""
    return await run_in_threadpool(service.session_info)


@router.post("/instagram/session", response_model=InstagramSessionResult)
async def update_instagram_session(
    payload: InstagramSessionUpdate,
    _: dict[str, Any] = Depends(require_admin),
    service: InstagramSessionService = Depends(InstagramSessionServiceFactory.inject),
) -> InstagramSessionResult:
    """Installe un nouveau cookie ``sessionid`` Instagram et le valide. Admin-only."""
    try:
        # test_login() + écriture fichier sont bloquants → hors event loop.
        username = await run_in_threadpool(
            service.update_session, payload.session_id, payload.username
        )
    except InstagramSessionError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    return InstagramSessionResult(username=username)
