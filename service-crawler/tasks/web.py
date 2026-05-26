import asyncio
import logging
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from celery_app import celery_app
from app.core.config import settings
from app.models.enums import CrawlType
from app.repositories.result_repository import ResultRepository
from app.repositories.source_repository import SourceRepository
from app.services.web_service import WebService
from app.services.notification_client import NotificationClient

logger = logging.getLogger(__name__)


def _make_session_factory():
    engine = create_async_engine(settings.DATABASE_URL)
    return sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


@celery_app.task(bind=True, max_retries=3, default_retry_delay=60)
def crawl_url(self, source_id: str | None, url: str, user_id: str | None = None):
    asyncio.run(_do_crawl(self, source_id, url, user_id))


async def _do_crawl(task, source_id: str | None, url: str, user_id_str: str | None) -> None:
    factory = _make_session_factory()
    async with factory() as session:
        result_repo = ResultRepository(session)
        source_repo = SourceRepository(session)

        # Résoudre l'user_id : depuis le paramètre ou depuis la source
        user_id: UUID | None = None
        if user_id_str:
            user_id = UUID(user_id_str)

        source = None
        if source_id:
            source = await source_repo.get_by_id(UUID(source_id))
            if source and not user_id:
                user_id = source.user_id

        if user_id and await result_repo.user_link_exists(url, user_id):
            logger.info("URL déjà indexée pour cet utilisateur, ignorée : %s", url)
            return

        try:
            data = await WebService().fetch(url)
        except Exception as exc:
            logger.error("Fetch failed for %s: %s", url, exc)
            raise task.retry(exc=exc)

        result, _ = await result_repo.get_or_create_result(
            {
                "type": CrawlType.WEB,
                "url_origin": url,
                "title": data.get("title", ""),
                "raw_content": data.get("raw_content", ""),
                "images": data.get("images", []),
                "video_url": data.get("video_url"),
                "published_at": None,
            }
        )

        await result_repo.create_user_link(
            result_id=result.id,
            user_id=user_id,
            source_id=UUID(source_id) if source_id else None,
        )

        if source:
            await source_repo.mark_crawled(source)

        logger.info("Crawl web terminé pour %s", url)

    if user_id:
        await NotificationClient().notify_crawl_done(
            str(user_id), CrawlType.WEB.value, 1, url
        )
