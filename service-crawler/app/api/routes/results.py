import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.models.enums import CrawlStatus
from app.repositories.result_repository import ResultRepository
from app.schemas.crawl_result import (
    CrawlResultListParams,
    CrawlResultResponse,
    CrawlResultUpdate,
    PaginatedCrawlResultResponse,
)
from app.services.recipe_mapper import RecipeMapper
from app.services.recipe_service_client import RecipeServiceClient
from app.services.result_service import ResultService

router = APIRouter()

# TODO Phase 6: replace with JWT-authenticated user id
_STUB_USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")


class ResultServiceFactory:
    @staticmethod
    def inject(session: AsyncSession = Depends(get_session)) -> ResultService:
        return ResultService(ResultRepository(session))


class RecipeMapperFactory:
    @staticmethod
    def inject() -> RecipeMapper:
        return RecipeMapper(RecipeServiceClient())


@router.get("", response_model=PaginatedCrawlResultResponse)
async def list_results(
    status: CrawlStatus | None = Query(default=CrawlStatus.WAITING),
    source_id: uuid.UUID | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    service: ResultService = Depends(ResultServiceFactory.inject),
) -> PaginatedCrawlResultResponse:
    params = CrawlResultListParams(
        status=status,
        source_id=source_id,
        page=page,
        page_size=page_size,
    )
    return await service.list_results(params)


@router.get("/{result_id}", response_model=CrawlResultResponse)
async def get_result(
    result_id: uuid.UUID,
    service: ResultService = Depends(ResultServiceFactory.inject),
) -> CrawlResultResponse:
    return await service.get_result(result_id)


@router.patch("/{result_id}", response_model=CrawlResultResponse)
async def update_result(
    result_id: uuid.UUID,
    data: CrawlResultUpdate,
    service: ResultService = Depends(ResultServiceFactory.inject),
) -> CrawlResultResponse:
    return await service.update_result(result_id, data)


@router.patch("/{result_id}/validate", response_model=CrawlResultResponse)
async def validate_result(
    result_id: uuid.UUID,
    service: ResultService = Depends(ResultServiceFactory.inject),
    mapper: RecipeMapper = Depends(RecipeMapperFactory.inject),
) -> CrawlResultResponse:
    return await service.validate_result(
        result_id, validated_by=_STUB_USER_ID, mapper=mapper
    )


@router.patch("/{result_id}/reject", response_model=CrawlResultResponse)
async def reject_result(
    result_id: uuid.UUID,
    service: ResultService = Depends(ResultServiceFactory.inject),
) -> CrawlResultResponse:
    return await service.reject_result(result_id)