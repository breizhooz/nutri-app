import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user_id
from app.db.session import get_session
from app.models.enums import CrawlStatus
from app.repositories.result_repository import ResultRepository
from app.schemas.crawl_result import (
    CrawlResultListParams,
    CrawlResultResponse,
    CrawlResultUpdate,
    PaginatedCrawlResultResponse,
)
from app.schemas.hydration import RecipeCommitRequest, RecipeHydrated
from app.services.groq_recipe_extractor import GroqRecipeExtractor
from app.services.recipe_mapper import RecipeMapper
from app.services.recipe_service_client import RecipeServiceClient
from app.services.result_service import ResultService

router = APIRouter()


class ResultServiceFactory:
    @staticmethod
    def inject(session: AsyncSession = Depends(get_session)) -> ResultService:
        return ResultService(ResultRepository(session))


class RecipeMapperFactory:
    @staticmethod
    def inject() -> RecipeMapper:
        return RecipeMapper(RecipeServiceClient())


class GroqExtractorFactory:
    @staticmethod
    def inject() -> GroqRecipeExtractor:
        return GroqRecipeExtractor()


@router.get("", response_model=PaginatedCrawlResultResponse)
async def list_results(
    status: CrawlStatus | None = Query(default=CrawlStatus.WAITING),
    source_id: uuid.UUID | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    sort: str = Query(default="desc", pattern="^(asc|desc)$"),
    service: ResultService = Depends(ResultServiceFactory.inject),
    current_user_id: uuid.UUID = Depends(get_current_user_id),
) -> PaginatedCrawlResultResponse:
    params = CrawlResultListParams(
        status=status,
        source_id=source_id,
        page=page,
        page_size=page_size,
        sort=sort,
    )
    return await service.list_results(user_id=current_user_id, params=params)


@router.get("/{result_id}", response_model=CrawlResultResponse)
async def get_result(
    result_id: uuid.UUID,
    service: ResultService = Depends(ResultServiceFactory.inject),
    current_user_id: uuid.UUID = Depends(get_current_user_id),
) -> CrawlResultResponse:
    return await service.get_result(result_id=result_id, user_id=current_user_id)


@router.patch("/{result_id}", response_model=CrawlResultResponse)
async def update_result(
    result_id: uuid.UUID,
    data: CrawlResultUpdate,
    service: ResultService = Depends(ResultServiceFactory.inject),
    current_user_id: uuid.UUID = Depends(get_current_user_id),
) -> CrawlResultResponse:
    return await service.update_result(
        result_id=result_id, user_id=current_user_id, data=data
    )


@router.patch("/{result_id}/validate", response_model=CrawlResultResponse)
async def validate_result(
    result_id: uuid.UUID,
    service: ResultService = Depends(ResultServiceFactory.inject),
    mapper: RecipeMapper = Depends(RecipeMapperFactory.inject),
    current_user_id: uuid.UUID = Depends(get_current_user_id),
) -> CrawlResultResponse:
    return await service.validate_result(
        result_id=result_id,
        user_id=current_user_id,
        validated_by=current_user_id,
        mapper=mapper,
    )


@router.post("/{result_id}/hydrate", response_model=RecipeHydrated)
async def hydrate_result(
    result_id: uuid.UUID,
    service: ResultService = Depends(ResultServiceFactory.inject),
    extractor: GroqRecipeExtractor = Depends(GroqExtractorFactory.inject),
    current_user_id: uuid.UUID = Depends(get_current_user_id),
) -> RecipeHydrated:
    return await service.hydrate_result(
        result_id=result_id,
        user_id=current_user_id,
        extractor=extractor,
    )


@router.post("/{result_id}/commit", response_model=CrawlResultResponse)
async def commit_result(
    result_id: uuid.UUID,
    data: RecipeCommitRequest,
    service: ResultService = Depends(ResultServiceFactory.inject),
    mapper: RecipeMapper = Depends(RecipeMapperFactory.inject),
    current_user_id: uuid.UUID = Depends(get_current_user_id),
) -> CrawlResultResponse:
    return await service.commit_result(
        result_id=result_id,
        user_id=current_user_id,
        validated_by=current_user_id,
        data=data,
        mapper=mapper,
    )


@router.patch("/{result_id}/reject", response_model=CrawlResultResponse)
async def reject_result(
    result_id: uuid.UUID,
    service: ResultService = Depends(ResultServiceFactory.inject),
    current_user_id: uuid.UUID = Depends(get_current_user_id),
) -> CrawlResultResponse:
    return await service.reject_result(result_id=result_id, user_id=current_user_id)
