import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.crawl_source import CrawlSource
from app.models.enums import CrawlType
from app.schemas.crawl_source import CrawlSourceCreate, CrawlSourceUpdate


class SourceRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, user_id: uuid.UUID, data: CrawlSourceCreate) -> CrawlSource:
        source = CrawlSource(user_id=user_id, **data.model_dump())
        self.session.add(source)
        await self.session.commit()
        await self.session.refresh(source)
        return source

    async def get_by_id(self, source_id: uuid.UUID) -> CrawlSource | None:
        result = await self.session.execute(
            select(CrawlSource).where(CrawlSource.id == source_id)
        )
        return result.scalar_one_or_none()

    async def list_by_user(self, user_id: uuid.UUID) -> list[CrawlSource]:
        result = await self.session.execute(
            select(CrawlSource)
            .where(CrawlSource.user_id == user_id)
            .order_by(CrawlSource.created_at.desc())
        )
        return list(result.scalars().all())

    async def update(self, source: CrawlSource, data: CrawlSourceUpdate) -> CrawlSource:
        for field, value in data.model_dump(exclude_none=True).items():
            setattr(source, field, value)
        await self.session.commit()
        await self.session.refresh(source)
        return source

    async def delete(self, source: CrawlSource) -> None:
        await self.session.delete(source)
        await self.session.commit()

    async def mark_crawled(self, source: CrawlSource) -> None:
        source.dernier_crawl = datetime.utcnow()
        await self.session.commit()

    async def list_active_by_type(self, type: CrawlType) -> list[CrawlSource]:
        result = await self.session.execute(
            select(CrawlSource).where(
                CrawlSource.actif == True,  # noqa: E712
                CrawlSource.type == type,
            )
        )
        return list(result.scalars().all())