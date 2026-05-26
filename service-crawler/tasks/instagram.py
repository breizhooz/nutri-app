import asyncio
import logging
from uuid import UUID

import instaloader
import requests

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.models.enums import CrawlStatus, CrawlType
from app.repositories.result_repository import ResultRepository
from app.repositories.source_repository import SourceRepository
from app.services.instagram_service import InstagramService
from celery_app import celery_app
from app.services.notification_client import NotificationClient

logger = logging.getLogger(__name__)


def _make_session_factory():
    engine = create_async_engine(settings.DATABASE_URL)
    return sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


@celery_app.task(bind=True, max_retries=3, default_retry_delay=3600)
def crawl_instagram(self, source_id: str, account: str):
    """Crawl un compte Instagram et stocke les nouveaux posts EN_ATTENTE."""
    asyncio.run(_do_crawl(self, source_id, account))


async def _do_crawl(task, source_id: str, account: str) -> None:
    new_count = 0
    user_id = None

    factory = _make_session_factory()
    async with factory() as session:
        result_repo = ResultRepository(session)
        source_repo = SourceRepository(session)

        source = await source_repo.get_by_id(UUID(source_id))
        if not source:
            logger.warning("Source %s introuvable, crawl Instagram annulé", source_id)
            return

        user_id = source.user_id
        since = source.last_crawl

        try:
            service = InstagramService()
            posts = (
                service.fetch_new_posts(account, since)
                if since is not None
                else service.fetch_posts(account)
            )
        except instaloader.exceptions.TooManyRequestsException as exc:
            logger.warning(
                "Instagram rate limit atteint pour %s, retry dans 60 min", account
            )
            raise task.retry(exc=exc, countdown=3600)
        except requests.exceptions.HTTPError as exc:
            logger.warning(
                "Instagram HTTP %s pour %s, retry dans 60 min",
                exc.response.status_code if exc.response is not None else "?",
                account,
            )
            raise task.retry(exc=exc, countdown=3600)
        except Exception as exc:
            logger.error("Échec du crawl Instagram pour %s : %s", account, exc)
            raise task.retry(exc=exc, countdown=3600)

        for post in posts:
            if await result_repo.user_link_exists(post.url, user_id):
                logger.debug("Post déjà indexé pour cet utilisateur, ignoré : %s", post.url)
                continue

            result, _ = await result_repo.get_or_create_result(
                {
                    "type": CrawlType.INSTAGRAM,
                    "url_origin": post.url,
                    "title": post.title,
                    "raw_content": post.caption,
                    "images": post.images,
                    "video_url": post.video_url,
                    "published_at": post.timestamp,
                }
            )
            await result_repo.create_user_link(
                result_id=result.id,
                user_id=user_id,
                source_id=UUID(source_id),
            )
            new_count += 1

        await source_repo.mark_crawled(source)
        logger.info(
            "Crawl Instagram terminé pour %s : %d nouveaux posts",
            account,
            new_count,
        )

    if new_count > 0 and user_id:
        await NotificationClient().notify_crawl_done(
            str(user_id), CrawlType.INSTAGRAM.value, new_count, account
        )
