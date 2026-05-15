import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.i18n.loader import t
from app.repositories.source_repository import SourceRepository
from app.schemas.crawl_source import CrawlSourceCreate, CrawlSourceResponse, CrawlSourceUpdate

router = APIRouter()

# TODO Phase 3 : remplacer par l'auth JWT
_STUB_USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")


@router.post("", response_model=CrawlSourceResponse, status_code=status.HTTP_201_CREATED)
async def create_source(
    data: CrawlSourceCreate,
    session: AsyncSession = Depends(get_session),
):
    repo = SourceRepository(session)
    return await repo.create(user_id=_STUB_USER_ID, data=data)


@router.get("", response_model=list[CrawlSourceResponse])
async def list_sources(session: AsyncSession = Depends(get_session)):
    repo = SourceRepository(session)
    return await repo.list_by_user(user_id=_STUB_USER_ID)


@router.get("/{source_id}", response_model=CrawlSourceResponse)
async def get_source(source_id: uuid.UUID, session: AsyncSession = Depends(get_session)):
    repo = SourceRepository(session)
    source = await repo.get_by_id(source_id)
    if not source:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=t.get("crawl_source.not_found"))
    return source


@router.patch("/{source_id}", response_model=CrawlSourceResponse)
async def update_source(
    source_id: uuid.UUID,
    data: CrawlSourceUpdate,
    session: AsyncSession = Depends(get_session),
):
    repo = SourceRepository(session)
    source = await repo.get_by_id(source_id)
    if not source:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=t.get("crawl_source.not_found"))
    return await repo.update(source, data)


@router.delete("/{source_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_source(source_id: uuid.UUID, session: AsyncSession = Depends(get_session)):
    repo = SourceRepository(session)
    source = await repo.get_by_id(source_id)
    if not source:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=t.get("crawl_source.not_found"))
    await repo.delete(source)


@router.post("/{source_id}/crawl", status_code=status.HTTP_202_ACCEPTED)
async def trigger_crawl(source_id: uuid.UUID, session: AsyncSession = Depends(get_session)):
    repo = SourceRepository(session)
    source = await repo.get_by_id(source_id)
    if not source:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=t.get("crawl_source.not_found"))
    # TODO Phase 3 : envoyer la tâche Celery selon source.type
    return {"detail": t.get("crawl_source.crawl_queued"), "source_id": str(source_id)}