import asyncio
import logging
from uuid import UUID

from instaloader.exceptions import (
    ConnectionException,
    LoginRequiredException,
    QueryReturnedBadRequestException,
    QueryReturnedForbiddenException,
    TooManyRequestsException,
)

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

# Anti-blocage : ces erreurs traduisent un rate-limit / soft-block / session morte
# (401/403/429, login requis). Re-essayer ne fait que prolonger le blocage → on
# n'auto-retry PAS ; l'admin rafraîchit le sessionid puis relance manuellement.
_BLOCKING_EXCEPTIONS = (
    TooManyRequestsException,
    LoginRequiredException,
    QueryReturnedForbiddenException,
    QueryReturnedBadRequestException,
)
# get_posts() remonte souvent le blocage comme un ConnectionException générique
# (« … 403 Forbidden … ») → on classe aussi par marqueur dans le message.
_BLOCK_MARKERS = ("401", "403", "429", "Please wait", "checkpoint", "login_required")
# Erreur réseau transitoire (timeout, coupure) : un seul retry, backoff long.
_TRANSIENT_RETRY_DELAY = 6 * 3600  # 6 h


def _is_block(exc: Exception) -> bool:
    """True si l'erreur traduit un rate-limit / soft-block / session morte."""
    if isinstance(exc, _BLOCKING_EXCEPTIONS):
        return True
    msg = str(exc)
    return any(marker in msg for marker in _BLOCK_MARKERS)


# Marqueurs « session morte / validation requise » → l'utilisateur doit rafraîchir
# le token.
_SESSION_MARKERS = ("login_required", "checkpoint", "challenge", "401", "LoginRequired")
# Marqueurs « vrai rate-limit » (trop de requêtes) → attendre suffit.
_RATE_LIMIT_MARKERS = ("429", "Too Many Requests", "Please wait", "wait a few minutes")


def _classify_block(exc: Exception) -> tuple[str, str]:
    """(code, message lisible) pour un blocage Instagram, à remonter à l'user.

    Quatre cas distincts pour que le message colle à la réalité — ne pas afficher
    « réessaie dans quelques heures » sur une erreur qui ne se résout pas en
    attendant (ex. un 403 d'accès) :
      - ``session_expired`` : session morte / validation requise → rafraîchir le token ;
      - ``rate_limited`` : trop de requêtes → attendre ;
      - ``access_forbidden`` : 403, Instagram refuse l'accès → réessayer / rafraîchir ;
      - ``blocked`` : repli pour un blocage indéterminé.
    """
    msg = str(exc)
    if isinstance(exc, LoginRequiredException) or any(
        m in msg for m in _SESSION_MARKERS
    ):
        return (
            "session_expired",
            "Ta session Instagram a expiré ou demande une validation. "
            "Rafraîchis le token Instagram, puis relance l'import.",
        )
    if isinstance(exc, TooManyRequestsException) or any(
        m in msg for m in _RATE_LIMIT_MARKERS
    ):
        return (
            "rate_limited",
            "Instagram limite temporairement les imports (trop de requêtes). "
            "Réessaie dans quelques heures — inutile de relancer tout de suite.",
        )
    if isinstance(exc, QueryReturnedForbiddenException) or "403" in msg:
        return (
            "access_forbidden",
            "Instagram a refusé l'accès à ce contenu (403). Réessaie plus tard ; "
            "si le problème persiste, rafraîchis le token Instagram via l'admin.",
        )
    return (
        "blocked",
        "L'import Instagram a été bloqué pour une raison indéterminée. Réessaie "
        "plus tard ; si ça persiste, rafraîchis le token Instagram.",
    )


def _handle_fetch_error(task, exc: Exception, label: str) -> None:
    """Politique anti-blocage commune.

    - Blocage (rate-limit/403/401/429/session morte) → log + AUCUN retry (le
      caller s'arrête en retournant).
    - Sinon → 1 retry avec backoff long (lève ``Retry``).
    """
    if _is_block(exc):
        logger.warning(
            "Instagram a bloqué/limité l'accès (%s : %s) — aucun retry automatique. "
            "Attendez quelques heures, rafraîchissez le sessionid via l'admin, "
            "puis relancez manuellement.",
            label,
            type(exc).__name__,
        )
        return
    if isinstance(exc, ConnectionException):
        logger.warning(
            "Erreur réseau Instagram (%s) : %s — 1 retry dans %dh",
            label,
            exc,
            _TRANSIENT_RETRY_DELAY // 3600,
        )
    else:
        logger.error("Échec du crawl Instagram (%s) : %s", label, exc)
    raise task.retry(exc=exc, countdown=_TRANSIENT_RETRY_DELAY)


def _make_session_factory():
    engine = create_async_engine(settings.DATABASE_URL)
    return sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


@celery_app.task(bind=True, max_retries=1, default_retry_delay=_TRANSIENT_RETRY_DELAY)
def crawl_instagram(self, source_id: str, account: str, force_full: bool = False):
    """Crawl un compte Instagram et stocke les nouveaux posts EN_ATTENTE.

    ``force_full`` ignore ``last_crawl`` pour re-parcourir tout l'historique
    (rattrapage des comptes existants).
    """
    asyncio.run(_do_crawl(self, source_id, account, force_full))


async def _do_crawl(
    task, source_id: str, account: str, force_full: bool = False
) -> None:
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
        # Crawl complet (force_full) → on repart de zéro ; sinon incrémental.
        since = None if force_full else source.last_crawl

        try:
            service = InstagramService()
            if since is not None:
                posts = service.fetch_new_posts(
                    account,
                    since,
                    page_delay=settings.INSTAGRAM_PAGE_DELAY_SECONDS,
                    page_size=settings.INSTAGRAM_PAGE_SIZE,
                    post_delay=settings.INSTAGRAM_POST_DELAY_SECONDS,
                    jitter_ratio=settings.INSTAGRAM_JITTER_RATIO,
                )
            else:
                posts = service.fetch_posts(
                    account,
                    max_posts=settings.INSTAGRAM_MAX_POSTS_PER_RUN or None,
                    page_delay=settings.INSTAGRAM_PAGE_DELAY_SECONDS,
                    page_size=settings.INSTAGRAM_PAGE_SIZE,
                    post_delay=settings.INSTAGRAM_POST_DELAY_SECONDS,
                    jitter_ratio=settings.INSTAGRAM_JITTER_RATIO,
                )
        except Exception as exc:
            _handle_fetch_error(task, exc, account)
            return

        for post in posts:
            if await result_repo.user_link_exists(post.url, user_id):
                logger.debug(
                    "Post déjà indexé pour cet utilisateur, ignoré : %s", post.url
                )
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


@celery_app.task(bind=True, max_retries=1, default_retry_delay=_TRANSIENT_RETRY_DELAY)
def crawl_instagram_post(self, shortcode: str, user_id: str):
    """Import d'UN seul post Instagram par son shortcode (oneshot par lien).

    1 requête seulement → risque de blocage quasi nul, contrairement au crawl
    de compte entier. Même politique anti-blocage que ``crawl_instagram``.

    Renvoie un dict d'état (``status`` ∈ done|blocked|error, + ``reason``/``message``)
    stocké par Celery → consultable par l'utilisateur via le polling de la tâche.
    """
    return asyncio.run(_do_crawl_post(self, shortcode, user_id))


async def _do_crawl_post(task, shortcode: str, user_id_str: str) -> dict:
    user_id = UUID(user_id_str)
    canonical_url = InstagramService.POST_URL.format(shortcode=shortcode)

    factory = _make_session_factory()
    async with factory() as session:
        result_repo = ResultRepository(session)

        # Déjà importé pour cet user → on ré-ouvre depuis le CACHE (aucun appel
        # Instagram) : le post repasse en attente de validation.
        existing = await result_repo.get_user_link_by_url(canonical_url, user_id)
        if existing is not None:
            if existing.status != CrawlStatus.WAITING:
                await result_repo.reset_to_waiting(existing)
                logger.info(
                    "Post déjà importé → ré-ouvert depuis le cache : %s", canonical_url
                )
                # Le post repasse « en attente de validation » → on notifie comme
                # un import (post renseigné), même sans nouvel appel Instagram.
                await NotificationClient().notify_crawl_done(
                    str(user_id), CrawlType.INSTAGRAM.value, 1, "Instagram"
                )
            else:
                logger.info("Post déjà en attente de validation : %s", canonical_url)
            return {"status": "done", "detail": "cached", "url": canonical_url}

        try:
            post = InstagramService().fetch_post(shortcode)
        except Exception as exc:
            if _is_block(exc):
                reason, message = _classify_block(exc)
                logger.warning(
                    "Instagram bloqué (post %s : %s) → %s",
                    shortcode,
                    type(exc).__name__,
                    reason,
                )
                await NotificationClient().notify_crawl_error(user_id_str, message)
                return {
                    "status": "blocked",
                    "reason": reason,
                    "message": message,
                    "url": canonical_url,
                }
            # Erreur non bloquante (réseau, autre) → politique de retry existante.
            _handle_fetch_error(task, exc, f"post {shortcode}")
            return {"status": "error", "url": canonical_url}

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
            result_id=result.id, user_id=user_id, source_id=None
        )
        logger.info("Post Instagram importé : %s", post.url)

    await NotificationClient().notify_crawl_done(
        str(user_id), CrawlType.INSTAGRAM.value, 1, "Instagram"
    )
    return {"status": "done", "new_count": 1, "url": canonical_url}
