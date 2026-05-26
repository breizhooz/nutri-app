import uuid
from datetime import datetime, timezone

from sqlalchemy import func, nullslast, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.crawl_result import CrawlResult
from app.models.crawl_result_user import CrawlResultUser
from app.models.enums import CrawlStatus
from app.schemas.crawl_result import CrawlResultUpdate


class ResultRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    # ── Contenu (CrawlResult) ──────────────────────────────────────────────────

    async def get_result_by_id(self, result_id: uuid.UUID) -> CrawlResult | None:
        row = await self.session.execute(
            select(CrawlResult).where(CrawlResult.id == result_id)
        )
        return row.scalar_one_or_none()

    async def get_or_create_result(self, data: dict) -> tuple[CrawlResult, bool]:
        """Retourne (result, created). Created=True si nouveau, False si URL déjà connue."""
        row = await self.session.execute(
            select(CrawlResult).where(CrawlResult.url_origin == data["url_origin"])
        )
        existing = row.scalar_one_or_none()
        if existing is not None:
            return existing, False
        result = CrawlResult(
            type=data["type"],
            url_origin=data["url_origin"],
            title=data.get("title", ""),
            raw_content=data.get("raw_content"),
            images=data.get("images", []),
            video_url=data.get("video_url"),
            published_at=data.get("published_at"),
        )
        self.session.add(result)
        await self.session.flush()
        return result, True

    async def update_result_content(
        self, result: CrawlResult, data: CrawlResultUpdate
    ) -> CrawlResult:
        for field, value in data.model_dump(exclude_none=True).items():
            setattr(result, field, value)
        await self.session.commit()
        await self.session.refresh(result)
        return result

    # ── Lien user (CrawlResultUser) ────────────────────────────────────────────

    async def user_link_exists(self, url_origin: str, user_id: uuid.UUID) -> bool:
        row = await self.session.execute(
            select(CrawlResultUser.id)
            .join(CrawlResult, CrawlResultUser.result_id == CrawlResult.id)
            .where(CrawlResult.url_origin == url_origin)
            .where(CrawlResultUser.user_id == user_id)
        )
        return row.scalar_one_or_none() is not None

    async def create_user_link(
        self,
        result_id: uuid.UUID,
        user_id: uuid.UUID,
        source_id: uuid.UUID | None,
    ) -> CrawlResultUser:
        link = CrawlResultUser(
            result_id=result_id, user_id=user_id, source_id=source_id
        )
        self.session.add(link)
        await self.session.commit()
        await self.session.refresh(link)
        return link

    async def get_user_link(
        self, result_id: uuid.UUID, user_id: uuid.UUID
    ) -> CrawlResultUser | None:
        row = await self.session.execute(
            select(CrawlResultUser)
            .where(CrawlResultUser.result_id == result_id)
            .where(CrawlResultUser.user_id == user_id)
            .options(selectinload(CrawlResultUser.result))
        )
        return row.scalar_one_or_none()

    async def list_by_user(
        self,
        user_id: uuid.UUID,
        status: CrawlStatus | None = None,
        source_id: uuid.UUID | None = None,
        page: int = 1,
        page_size: int = 20,
        sort: str = "desc",
    ) -> tuple[list[CrawlResultUser], int]:
        base = (
            select(CrawlResultUser)
            .where(CrawlResultUser.user_id == user_id)
            .options(selectinload(CrawlResultUser.result))
        )
        if status is not None:
            base = base.where(CrawlResultUser.status == status)
        if source_id is not None:
            base = base.where(CrawlResultUser.source_id == source_id)

        count_row = await self.session.execute(
            select(func.count()).select_from(base.subquery())
        )
        total: int = count_row.scalar_one()

        order_col = nullslast(
            CrawlResult.published_at.desc() if sort == "desc"
            else CrawlResult.published_at.asc()
        )
        offset = (page - 1) * page_size
        data_rows = await self.session.execute(
            base.join(CrawlResult, CrawlResultUser.result_id == CrawlResult.id)
            .order_by(order_col)
            .offset(offset)
            .limit(page_size)
        )
        return list(data_rows.scalars().all()), total

    async def validate_user_link(
        self, link: CrawlResultUser, validated_by: uuid.UUID
    ) -> CrawlResultUser:
        link.status = CrawlStatus.VALID
        link.validate_by = validated_by
        link.validate_date = datetime.now(timezone.utc)
        await self.session.commit()
        await self.session.refresh(link)
        return link

    async def reject_user_link(self, link: CrawlResultUser) -> CrawlResultUser:
        link.status = CrawlStatus.REJECTED
        await self.session.commit()
        await self.session.refresh(link)
        return link
