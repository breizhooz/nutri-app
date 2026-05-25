import logging
import uuid
from typing import TYPE_CHECKING

import httpx
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

logger = logging.getLogger(__name__)


if TYPE_CHECKING:
    from app.services.recipe_mapper import RecipeMapper


class ResultService:
    def __init__(self, repository: ResultRepository) -> None:
        self._repository = repository

    async def list_results(
        self, params: CrawlResultListParams
    ) -> PaginatedCrawlResultResponse:
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

    async def update_result(
        self, result_id: uuid.UUID, data: CrawlResultUpdate
    ) -> CrawlResult:
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
        self,
        result_id: uuid.UUID,
        validated_by: uuid.UUID,
        mapper: "RecipeMapper | None" = None,
    ) -> CrawlResult:
        result = await self._repository.get_by_id(result_id)
        if result is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=t.get("crawl_result.not_found"),
            )
        ResultService._assert_validatable(result)
        # Commit the state change first — validation is an editorial decision
        # independent of downstream recipe creation.
        validated = await self._repository.validate(result, validated_by=validated_by)
        # Best-effort: propagate to service-recipe. Failure is logged but does not
        # roll back the validation — the result remains VALID.
        if mapper is not None:
            await ResultService._call_mapper(validated, mapper)
        return validated

    # ── static guards ─────────────────────────────────────────────────────────

    @staticmethod
    async def _call_mapper(result: CrawlResult, mapper: "RecipeMapper") -> None:
        """Forward to service-recipe. Logs on failure; does not abort validation."""
        try:
            await mapper.map_and_send(result)
        except httpx.RequestError as exc:
            logger.warning(
                "service-recipe unreachable for result %s: %s", result.id, exc
            )
        except httpx.HTTPStatusError as exc:
            logger.warning(
                "service-recipe rejected result %s (HTTP %s): %s",
                result.id,
                exc.response.status_code,
                exc.response.text[:200],
            )

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
