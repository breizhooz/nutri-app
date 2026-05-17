"""Tâche Celery — notifications push déclenchées post-crawl."""
import asyncio
import logging
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.repositories.push_repository import PushRepository
from app.services.notification_service import NotificationService
from celery_app import celery_app

logger = logging.getLogger(__name__)


def _make_session_factory():
    engine = create_async_engine(settings.DATABASE_URL)
    return sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


@celery_app.task(bind=True, max_retries=3, default_retry_delay=60)
def send_crawl_notification(
    self,
    user_id: str,
    source_type: str,
    new_count: int,
    source_label: str = "",
) -> None:
    """Notifie l'utilisateur que le scheduler a inséré des éléments en attente de validation."""
    asyncio.run(_do_notify(self, user_id, source_type, new_count, source_label))


async def _do_notify(
    task,
    user_id: str,
    source_type: str,
    new_count: int,
    source_label: str,
) -> None:
    if not settings.VAPID_PRIVATE_KEY:
        logger.warning("VAPID_PRIVATE_KEY absent — notifications push désactivées")
        return

    factory = _make_session_factory()
    async with factory() as session:
        subscriptions = await PushRepository(session).get_by_user_id(UUID(user_id))

    if not subscriptions:
        logger.debug("Aucun abonnement push pour user=%s", user_id)
        return

    service = NotificationService(
        vapid_private_key=settings.VAPID_PRIVATE_KEY,
        vapid_claims_email=settings.VAPID_CLAIMS_EMAIL,
        expo_api_url=settings.EXPO_PUSH_API_URL,
    )
    payload = NotificationService.build_payload(source_type, new_count, source_label)
    result = await service.dispatch(subscriptions, payload)
    logger.info(
        "Notifications post-crawl (user=%s) : %d envoyées, %d échouées",
        user_id,
        result.sent,
        result.failed,
    )