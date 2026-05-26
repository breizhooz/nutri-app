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
from app.schemas.hydration import (
    HydratedIngredient,
    RecipeCommitRequest,
    RecipeHydrated,
)

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from app.services.groq_recipe_extractor import GroqRecipeExtractor
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
            crawl_type=params.crawl_type,
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
            await ResultService._call_mapper(link.result, mapper, user_id=str(user_id))
        return CrawlResultResponse.from_link(link)

    async def hydrate_result(
        self,
        result_id: uuid.UUID,
        user_id: uuid.UUID,
        extractor: "GroqRecipeExtractor",
    ) -> RecipeHydrated:
        link = await self._repository.get_user_link(result_id, user_id)
        if link is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=t.get("crawl_result.not_found"),
            )
        ResultService._assert_hydratable(link)
        extracted = await extractor.extract(link.result.raw_content or "")
        return RecipeHydrated(
            title=extracted.title,
            description=extracted.description,
            instructions=extracted.instructions,
            servings=extracted.servings,
            prep_time_minutes=extracted.prep_time_minutes,
            cook_time_minutes=extracted.cook_time_minutes,
            ingredients=[
                HydratedIngredient(
                    name=i["name"], quantity=i["quantity"], unit=i["unit"]
                )
                for i in extracted.ingredients
            ],
            groq_tokens_used=extracted.tokens_used,
            from_cache=extracted.from_cache,
        )

    async def commit_result(
        self,
        result_id: uuid.UUID,
        user_id: uuid.UUID,
        validated_by: uuid.UUID,
        data: RecipeCommitRequest,
        mapper: "RecipeMapper",
    ) -> CrawlResultResponse:
        link = await self._repository.get_user_link(result_id, user_id)
        if link is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=t.get("crawl_result.not_found"),
            )
        ResultService._assert_validatable(link)
        await ResultService._call_commit(
            link.result, data, mapper, user_id=str(user_id)
        )
        link = await self._repository.validate_user_link(
            link, validated_by=validated_by
        )
        return CrawlResultResponse.from_link(link)

    async def reset_result(
        self, result_id: uuid.UUID, user_id: uuid.UUID
    ) -> CrawlResultResponse:
        link = await self._repository.get_user_link(result_id, user_id)
        if link is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=t.get("crawl_result.not_found"),
            )
        ResultService._assert_resettable(link)
        link = await self._repository.reset_to_waiting(link)
        return CrawlResultResponse.from_link(link)

    # ── static guards ──────────────────────────────────────────────────────────

    @staticmethod
    async def _call_mapper(
        result: CrawlResult, mapper: "RecipeMapper", user_id: str | None = None
    ) -> None:
        try:
            await mapper.map_and_send(result, user_id=user_id)
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
    async def _call_commit(
        result: CrawlResult,
        data: RecipeCommitRequest,
        mapper: "RecipeMapper",
        user_id: str | None = None,
    ) -> None:
        try:
            await mapper.commit_from_hydrated(result, data, user_id=user_id)
        except httpx.RequestError as exc:
            logger.warning(
                "service-recipe unreachable during commit for result %s: %s",
                result.id,
                exc,
            )
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="service-recipe indisponible",
            ) from exc
        except httpx.HTTPStatusError as exc:
            logger.warning(
                "service-recipe rejected commit for result %s (HTTP %s): %s",
                result.id,
                exc.response.status_code,
                exc.response.text[:200],
            )
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="service-recipe a refusé la recette",
            ) from exc

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

    @staticmethod
    def _assert_hydratable(link: CrawlResultUser) -> None:
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

    @staticmethod
    def _assert_resettable(link: CrawlResultUser) -> None:
        if link.status == CrawlStatus.VALID:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=t.get("crawl_result.errors.already_validated"),
            )
        if link.status == CrawlStatus.WAITING:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=t.get("crawl_result.errors.already_waiting"),
            )
