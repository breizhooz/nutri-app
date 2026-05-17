import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user_id
from app.db.session import get_session
from app.i18n.loader import t
from app.models.enums import CrawlType
from app.repositories.source_repository import SourceRepository
from app.schemas.crawl_source import CrawlSourceCreate, CrawlSourceResponse, CrawlSourceUpdate
from tasks.instagram import crawl_instagram
from tasks.web import crawl_url

router = APIRouter()


@router.post("", response_model=CrawlSourceResponse, status_code=status.HTTP_201_CREATED)
async def create_source(
    data: CrawlSourceCreate,
    session: AsyncSession = Depends(get_session),
    current_user_id: uuid.UUID = Depends(get_current_user_id),
):
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
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=t.get("crawl_source.not_found"))
    if source.user_id != current_user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=t.get("errors.forbidden"))
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
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=t.get("crawl_source.not_found"))
    if source.user_id != current_user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=t.get("errors.forbidden"))
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
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=t.get("crawl_source.not_found"))
    if source.user_id != current_user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=t.get("errors.forbidden"))
    await repo.delete(source)


@router.post("/{source_id}/crawl", status_code=status.HTTP_202_ACCEPTED)
async def trigger_crawl(
    source_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    current_user_id: uuid.UUID = Depends(get_current_user_id),
):
    repo = SourceRepository(session)
    source = await repo.get_by_id(source_id)
    if not source:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=t.get("crawl_source.not_found"))
    if source.user_id != current_user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=t.get("errors.forbidden"))

    if source.type == CrawlType.WEB:
        task = crawl_url.delay(str(source.id), source.url)
    elif source.type == CrawlType.INSTAGRAM:
        task = crawl_instagram.delay(str(source.id), source.url)
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=t.get("errors.crawl_type_not_supported"),
        )

    return {"detail": t.get("crawl_source.crawl_queued"), "source_id": str(source_id), "task_id": task.id}
