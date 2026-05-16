import uuid

from fastapi import HTTPException, status

from app.i18n.loader import t
from app.models.crawl_result import CrawlResult
from app.models.enums import CrawlStatus
from app.repositories.result_repository import ResultRepository
from app.schemas.crawl_result import (
    CrawlResultListParams,
    CrawlResultUpdate,
    PaginatedCrawlResultResponse,
)


class ResultService:
    def __init__(self, repository: ResultRepository) -> None:
        self._repository = repository

    async def list_results(self, params: CrawlResultListParams) -> PaginatedCrawlResultResponse:
        items, total = await self._repository.list_by_filters(
            status=params.status,
            source_id=params.source_id,
            page=params.page,
            page_size=params.page_size,
        )
        return PaginatedCrawlResultResponse.build(
            items=items,
            total=total,
            page=params.page,
            page_size=params.page_size,
        )

    async def get_result(self, result_id: uuid.UUID) -> CrawlResult:
        result = await self._repository.get_by_id(result_id)
        if result is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=t.get("crawl_result.not_found"),
            )
        return result

    async def update_result(self, result_id: uuid.UUID, data: CrawlResultUpdate) -> CrawlResult:
        result = await self._repository.get_by_id(result_id)
        if result is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=t.get("crawl_result.not_found"),
            )
        ResultService._assert_editable(result)
        return await self._repository.update(result, data)

    async def reject_result(self, result_id: uuid.UUID) -> CrawlResult:
        result = await self._repository.get_by_id(result_id)
        if result is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=t.get("crawl_result.not_found"),
            )
        ResultService._assert_rejectable(result)
        return await self._repository.reject(result)

    async def validate_result(
        self, result_id: uuid.UUID, validated_by: uuid.UUID
    ) -> CrawlResult:
        result = await self._repository.get_by_id(result_id)
        if result is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=t.get("crawl_result.not_found"),
            )
        ResultService._assert_validatable(result)
        return await self._repository.validate(result, validated_by=validated_by)

    @staticmethod
    def _assert_editable(result: CrawlResult) -> None:
        if result.status != CrawlStatus.WAITING:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=t.get("crawl_result.errors.not_editable"),
            )

    @staticmethod
    def _assert_rejectable(result: CrawlResult) -> None:
        if result.status == CrawlStatus.REJECTED:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=t.get("crawl_result.errors.already_rejected"),
            )
        if result.status == CrawlStatus.VALID:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=t.get("crawl_result.errors.already_validated"),
            )

    @staticmethod
    def _assert_validatable(result: CrawlResult) -> None:
        if result.status == CrawlStatus.VALID:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=t.get("crawl_result.errors.already_validated"),
            )
        if result.status == CrawlStatus.REJECTED:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=t.get("crawl_result.errors.already_rejected"),
            )