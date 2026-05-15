import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.crawl_result import CrawlResult
from app.models.enums import CrawlStatus
from app.schemas.crawl_result import CrawlResultUpdate


class ResultRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, data: dict) -> CrawlResult:
        result = CrawlResult(**data)
        self.session.add(result)
        await self.session.commit()
        await self.session.refresh(result)
        return result

    async def get_by_id(self, result_id: uuid.UUID) -> CrawlResult | None:
        result = await self.session.execute(
            select(CrawlResult).where(CrawlResult.id == result_id)
        )
        return result.scalar_one_or_none()

    async def list_pending(self) -> list[CrawlResult]:
        result = await self.session.execute(
            select(CrawlResult)
            .where(CrawlResult.status == CrawlStatus.WAITING)
            .order_by(CrawlResult.created_at.desc())
        )
        return list(result.scalars().all())

    async def update(self, crawl_result: CrawlResult, data: CrawlResultUpdate) -> CrawlResult:
        for field, value in data.model_dump(exclude_none=True).items():
            setattr(crawl_result, field, value)
        await self.session.commit()
        await self.session.refresh(crawl_result)
        return crawl_result

    async def validate(self, crawl_result: CrawlResult, validated_by: uuid.UUID) -> CrawlResult:
        crawl_result.status = CrawlStatus.VALID
        crawl_result.validate_by = validated_by
        crawl_result.validate_date = datetime.now(timezone.utc)
        await self.session.commit()
        await self.session.refresh(crawl_result)
        return crawl_result

    async def reject(self, crawl_result: CrawlResult) -> CrawlResult:
        crawl_result.status = CrawlStatus.REJECTED
        await self.session.commit()
        await self.session.refresh(crawl_result)
        return crawl_result

    async def url_exists(self, url: str) -> bool:
        result = await self.session.execute(
            select(CrawlResult.id).where(CrawlResult.url_origin == url)
        )
        return result.scalar_one_or_none() is not None