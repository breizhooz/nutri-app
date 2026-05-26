import logging
import uuid
from typing import TYPE_CHECKING

import httpx
from fastapi import HTTPException, status

from app.i18n.loader import t
from app.models.crawl_result import CrawlResult
from app.models.crawl_result_user import CrawlResultUser
from app.models.enums import CrawlStatus
from app.repositories.result_repository import ResultRepository
from app.schemas.crawl_result import (
    CrawlResultListParams,
    CrawlResultResponse,
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
        self, user_id: uuid.UUID, params: CrawlResultListParams
    ) -> PaginatedCrawlResultResponse:
        links, total = await self._repository.list_by_user(
            user_id=user_id,
            status=params.status,
            source_id=params.source_id,
            page=params.page,
            page_size=params.page_size,
            sort=params.sort,
        )
        return PaginatedCrawlResultResponse.build(
            items=[CrawlResultResponse.from_link(lnk) for lnk in links],
            total=total,
            page=params.page,
            page_size=params.page_size,
        )

    async def get_result(
        self, result_id: uuid.UUID, user_id: uuid.UUID
    ) -> CrawlResultResponse:
        link = await self._repository.get_user_link(result_id, user_id)
        if link is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=t.get("crawl_result.not_found"),
            )
        return CrawlResultResponse.from_link(link)

    async def update_result(
        self, result_id: uuid.UUID, user_id: uuid.UUID, data: CrawlResultUpdate
    ) -> CrawlResultResponse:
        link = await self._repository.get_user_link(result_id, user_id)
        if link is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=t.get("crawl_result.not_found"),
            )
        ResultService._assert_editable(link)
        await self._repository.update_result_content(link.result, data)
        return CrawlResultResponse.from_link(link)

    async def reject_result(
        self, result_id: uuid.UUID, user_id: uuid.UUID
    ) -> CrawlResultResponse:
        link = await self._repository.get_user_link(result_id, user_id)
        if link is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=t.get("crawl_result.not_found"),
            )
        ResultService._assert_rejectable(link)
        link = await self._repository.reject_user_link(link)
        return CrawlResultResponse.from_link(link)

    async def validate_result(
        self,
        result_id: uuid.UUID,
        user_id: uuid.UUID,
        validated_by: uuid.UUID,
        mapper: "RecipeMapper | None" = None,
    ) -> CrawlResultResponse:
        link = await self._repository.get_user_link(result_id, user_id)
        if link is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=t.get("crawl_result.not_found"),
            )
        ResultService._assert_validatable(link)
        link = await self._repository.validate_user_link(
            link, validated_by=validated_by
        )
        if mapper is not None:
            await ResultService._call_mapper(link.result, mapper)
        return CrawlResultResponse.from_link(link)

    # ── static guards ──────────────────────────────────────────────────────────

    @staticmethod
    async def _call_mapper(result: CrawlResult, mapper: "RecipeMapper") -> None:
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
    def _assert_editable(link: CrawlResultUser) -> None:
        if link.status != CrawlStatus.WAITING:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=t.get("crawl_result.errors.not_editable"),
            )

    @staticmethod
    def _assert_rejectable(link: CrawlResultUser) -> None:
        if link.status == CrawlStatus.REJECTED:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=t.get("crawl_result.errors.already_rejected"),
            )
        if link.status == CrawlStatus.VALID:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=t.get("crawl_result.errors.already_validated"),
            )

    @staticmethod
    def _assert_validatable(link: CrawlResultUser) -> None:
        if link.status == CrawlStatus.VALID:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=t.get("crawl_result.errors.already_validated"),
            )
        if link.status == CrawlStatus.REJECTED:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=t.get("crawl_result.errors.already_rejected"),
            )
