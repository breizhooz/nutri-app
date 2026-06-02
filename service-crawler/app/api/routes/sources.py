import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.concurrency import run_in_threadpool
from pydantic import AnyHttpUrl, BaseModel, field_validator
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import (
    CrawlPermission,
    UniqLinkPermission,
    get_current_user_id,
    get_token_payload,
)
from app.db.session import get_session
from app.i18n.loader import t
from app.models.enums import CrawlType
from app.repositories.source_repository import SourceRepository
from app.schemas.crawl_source import (
    CrawlSourceCreate,
    CrawlSourceResponse,
    CrawlSourceUpdate,
)
from app.schemas.queue import TaskStatus
from app.services.instagram_service import InstagramService
from app.services.queue_service import QueueService
from tasks.instagram import crawl_instagram, crawl_instagram_post
from tasks.web import crawl_url


def _queue_service() -> QueueService:
    return QueueService()


class OneshotCrawlRequest(BaseModel):
    url: str

    @field_validator("url")
    @classmethod
    def validate_url(cls, v: str) -> str:
        try:
            AnyHttpUrl(v)
        except Exception:
            raise ValueError("i18n:validation.url_invalid")
        return v


router = APIRouter()


@router.post("/oneshot", status_code=status.HTTP_202_ACCEPTED)
async def oneshot_crawl(
    data: OneshotCrawlRequest,
    payload: dict = Depends(get_token_payload),
):
    """Import one-shot d'un lien unique : post Instagram OU page web.

    Le type est déduit de l'URL et soumis au droit ``uniq_link`` correspondant.
    """
    user_id = str(payload["sub"])
    shortcode = InstagramService.shortcode_from_url(data.url)
    if shortcode is not None:
        UniqLinkPermission.ensure(payload, "instagram")
        task = crawl_instagram_post.delay(shortcode, user_id)
        return {
            "detail": "Import lancé",
            "url": data.url,
            "type": "instagram",
            "task_id": task.id,
        }

    UniqLinkPermission.ensure(payload, "web")
    task = crawl_url.delay(source_id=None, url=data.url, user_id=user_id)
    return {
        "detail": "Import lancé",
        "url": data.url,
        "type": "web",
        "task_id": task.id,
    }


@router.get("/oneshot/{task_id}", response_model=TaskStatus)
async def oneshot_status(
    task_id: str,
    _: uuid.UUID = Depends(get_current_user_id),
    service: QueueService = Depends(_queue_service),
) -> TaskStatus:
    """Statut d'un import oneshot lancé par l'utilisateur (polling côté front).

    Sur succès, ``result`` porte l'état métier : ``{"status": "done"}`` ou, en cas
    de blocage Instagram, ``{"status": "blocked", "message": "…"}`` à afficher.
    """
    # Accès au result backend Celery = bloquant → hors event loop.
    return await run_in_threadpool(service.task_status, task_id)


@router.post(
    "", response_model=CrawlSourceResponse, status_code=status.HTTP_201_CREATED
)
async def create_source(
    data: CrawlSourceCreate,
    session: AsyncSession = Depends(get_session),
    current_user_id: uuid.UUID = Depends(get_current_user_id),
    payload: dict = Depends(get_token_payload),
):
    CrawlPermission.ensure(payload, data.type.value)
    repo = SourceRepository(session)
    source = await repo.create(user_id=current_user_id, data=data)
    if source.type == CrawlType.INSTAGRAM:
        crawl_instagram.delay(str(source.id), source.url)
    return source


@router.get("", response_model=list[CrawlSourceResponse])
async def list_sources(
    session: AsyncSession = Depends(get_session),
    current_user_id: uuid.UUID = Depends(get_current_user_id),
):
    repo = SourceRepository(session)
    return await repo.list_by_user(user_id=current_user_id)


@router.get("/{source_id}", response_model=CrawlSourceResponse)
async def get_source(
    source_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    current_user_id: uuid.UUID = Depends(get_current_user_id),
):
    repo = SourceRepository(session)
    source = await repo.get_by_id(source_id)
    if not source:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=t.get("crawl_source.not_found"),
        )
    if source.user_id != current_user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail=t.get("errors.forbidden")
        )
    return source


@router.patch("/{source_id}", response_model=CrawlSourceResponse)
async def update_source(
    source_id: uuid.UUID,
    data: CrawlSourceUpdate,
    session: AsyncSession = Depends(get_session),
    current_user_id: uuid.UUID = Depends(get_current_user_id),
):
    repo = SourceRepository(session)
    source = await repo.get_by_id(source_id)
    if not source:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=t.get("crawl_source.not_found"),
        )
    if source.user_id != current_user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail=t.get("errors.forbidden")
        )
    return await repo.update(source, data)


@router.delete("/{source_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_source(
    source_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    current_user_id: uuid.UUID = Depends(get_current_user_id),
):
    repo = SourceRepository(session)
    source = await repo.get_by_id(source_id)
    if not source:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=t.get("crawl_source.not_found"),
        )
    if source.user_id != current_user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail=t.get("errors.forbidden")
        )
    await repo.delete(source)


@router.post("/{source_id}/crawl", status_code=status.HTTP_202_ACCEPTED)
async def trigger_crawl(
    source_id: uuid.UUID,
    full: bool = Query(
        False,
        description="Instagram : ignore last_crawl pour re-parcourir tout l'historique.",
    ),
    session: AsyncSession = Depends(get_session),
    current_user_id: uuid.UUID = Depends(get_current_user_id),
    payload: dict = Depends(get_token_payload),
):
    repo = SourceRepository(session)
    source = await repo.get_by_id(source_id)
    if not source:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=t.get("crawl_source.not_found"),
        )
    if source.user_id != current_user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail=t.get("errors.forbidden")
        )

    if source.type == CrawlType.WEB:
        CrawlPermission.ensure(payload, "web")
        task = crawl_url.delay(str(source.id), source.url)
    elif source.type == CrawlType.INSTAGRAM:
        CrawlPermission.ensure(payload, "instagram")
        task = crawl_instagram.delay(str(source.id), source.url, force_full=full)
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=t.get("errors.crawl_type_not_supported"),
        )

    return {
        "detail": t.get("crawl_source.crawl_queued"),
        "source_id": str(source_id),
        "task_id": task.id,
    }
