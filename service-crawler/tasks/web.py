import asyncio
import logging
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from celery_app import celery_app
from app.core.config import settings
from app.models.enums import CrawlType, CrawlStatus
from app.repositories.result_repository import ResultRepository
from app.repositories.source_repository import SourceRepository
from app.services.web_service import WebService

logger = logging.getLogger(__name__)


def _make_session_factory():
    engine = create_async_engine(settings.DATABASE_URL)
    return sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


@celery_app.task(bind=True, max_retries=3, default_retry_delay=60)
def crawl_url(self, source_id: str | None, url: str):
    asyncio.run(_do_crawl(self, source_id, url))


async def _do_crawl(task, source_id: str | None, url: str) -> None:
    user_id = None
    crawled = False

    factory = _make_session_factory()
    async with factory() as session:
        result_repo = ResultRepository(session)
        source_repo = SourceRepository(session)

        if await result_repo.url_exists(url):
            logger.info("Skipping already-crawled URL: %s", url)
            return

        source = None
        if source_id:
            source = await source_repo.get_by_id(UUID(source_id))
            if source:
                user_id = source.user_id

        try:
            data = await WebService().fetch(url)
        except Exception as exc:
            logger.error("Fetch failed for %s: %s", url, exc)
            raise task.retry(exc=exc)

        await result_repo.create({
            "source_id": UUID(source_id) if source_id else None,
            "user_id": user_id,
            "type": CrawlType.WEB,
            "url_origin": url,
            "title": data.get("title", ""),
            "raw_content": data.get("raw_content", ""),
            "images": data.get("images", []),
            "video_url": data.get("video_url"),
            "status": CrawlStatus.WAITING,
        })
        crawled = True

        if source:
            await source_repo.mark_crawled(source)

    if crawled and user_id:
        from tasks.notifications import send_crawl_notification
        send_crawl_notification.delay(
            str(user_id),
            CrawlType.WEB.value,
            1,
            url,
        )