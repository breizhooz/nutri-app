import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.repositories.result_repository import ResultRepository
from app.schemas.crawl_result import CrawlResultResponse, CrawlResultUpdate

router = APIRouter()

_STUB_USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")


@router.get("", response_model=list[CrawlResultResponse])
async def list_pending_results(session: AsyncSession = Depends(get_session)):
    repo = ResultRepository(session)
    return await repo.list_pending()


@router.get("/{result_id}", response_model=CrawlResultResponse)
async def get_result(result_id: uuid.UUID, session: AsyncSession = Depends(get_session)):
    repo = ResultRepository(session)
    result = await repo.get_by_id(result_id)
    if not result:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="crawl_result.not_found")
    return result


@router.patch("/{result_id}", response_model=CrawlResultResponse)
async def update_result(
    result_id: uuid.UUID,
    data: CrawlResultUpdate,
    session: AsyncSession = Depends(get_session),
):
    repo = ResultRepository(session)
    result = await repo.get_by_id(result_id)
    if not result:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="crawl_result.not_found")
    return await repo.update(result, data)


@router.patch("/{result_id}/validate", response_model=CrawlResultResponse)
async def validate_result(result_id: uuid.UUID, session: AsyncSession = Depends(get_session)):
    repo = ResultRepository(session)
    result = await repo.get_by_id(result_id)
    if not result:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="crawl_result.not_found")
    # TODO Phase 5 : appeler recipe_mapper puis POST vers service-recipe
    return await repo.validate(result, validated_by=_STUB_USER_ID)


@router.patch("/{result_id}/reject", response_model=CrawlResultResponse)
async def reject_result(result_id: uuid.UUID, session: AsyncSession = Depends(get_session)):
    repo = ResultRepository(session)
    result = await repo.get_by_id(result_id)
    if not result:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="crawl_result.not_found")
    return await repo.reject(result)