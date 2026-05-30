import asyncio
import hashlib
import logging
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.models.enums import CrawlType
from app.repositories.result_repository import ResultRepository
from app.services.notification_client import NotificationClient
from celery_app import celery_app

logger = logging.getLogger(__name__)


def _make_session_factory():
    engine = create_async_engine(settings.DATABASE_URL)
    return sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


def build_origin(raw_text: str) -> str:
    """Synthetic, deterministic origin so re-uploading the same image dedupes."""
    digest = hashlib.sha256(raw_text.encode()).hexdigest()
    return f"ocr://{digest}"


@celery_app.task(bind=True, max_retries=3, default_retry_delay=60)
def process_ocr_recipe(self, user_id: str, raw_text: str, title: str):
    """Persiste une pré-recette issue d'un OCR (statut EN_ATTENTE) et notifie.

    L'image a déjà été traitée et supprimée côté requête HTTP : cette tâche ne
    manipule que le texte brut, calquée sur le cycle de vie d'Instagram.
    """
    asyncio.run(_do_process(self, user_id, raw_text, title))


async def _do_process(task, user_id_str: str, raw_text: str, title: str) -> None:
    user_id = UUID(user_id_str)
    url_origin = build_origin(raw_text)

    factory = _make_session_factory()
    async with factory() as session:
        result_repo = ResultRepository(session)

        if await result_repo.user_link_exists(url_origin, user_id):
            logger.info("OCR déjà indexé pour cet utilisateur, ignoré : %s", url_origin)
            return

        try:
            result, _ = await result_repo.get_or_create_result(
                {
                    "type": CrawlType.OCR,
                    "url_origin": url_origin,
                    "title": title,
                    "raw_content": raw_text,
                    "images": [],
                    "video_url": None,
                    "published_at": None,
                }
            )
            await result_repo.create_user_link(
                result_id=result.id,
                user_id=user_id,
                source_id=None,
            )
        except Exception as exc:
            logger.error("Échec de la persistance OCR pour %s : %s", user_id, exc)
            raise task.retry(exc=exc)

        logger.info("Pré-recette OCR créée pour %s : %s", user_id, title)

    await NotificationClient().notify_crawl_done(
        str(user_id), CrawlType.OCR.value, 1, "OCR"
    )
