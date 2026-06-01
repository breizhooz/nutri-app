import logging
import re
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone

import instaloader

from app.core.config import settings

logger = logging.getLogger(__name__)

# Reconnaît un lien de post/reel/tv Instagram et capture le shortcode.
_IG_POST_RE = re.compile(
    r"instagram\.com/(?:p|reel|tv)/([A-Za-z0-9_-]+)", re.IGNORECASE
)


@dataclass
class InstagramPost:
    shortcode: str
    url: str
    title: str
    caption: str
    images: list[str] = field(default_factory=list)
    video_url: str | None = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class InstagramService:
    POST_URL = "https://www.instagram.com/p/{shortcode}/"

    def __init__(self, loader: instaloader.Instaloader | None = None):
        self._loader = loader or self._make_authenticated_loader()

    @classmethod
    def _make_authenticated_loader(cls) -> instaloader.Instaloader:
        loader = instaloader.Instaloader(
            download_pictures=False,
            download_videos=False,
            download_video_thumbnails=False,
            download_geotags=False,
            download_comments=False,
            save_metadata=False,
            compress_json=False,
            quiet=True,
            max_connection_attempts=1,
        )
        if settings.INSTAGRAM_USERNAME:
            cls._ensure_session(
                loader,
                settings.INSTAGRAM_USERNAME,
                settings.INSTAGRAM_PASSWORD,
                settings.INSTAGRAM_SESSION_FILE,
            )
        return loader

    @staticmethod
    def _ensure_session(
        loader: instaloader.Instaloader,
        username: str,
        password: str,
        session_file: str,
    ) -> None:
        try:
            loader.load_session_from_file(username, session_file)
            InstagramService._ensure_ds_user_id(loader)
            loader.test_login()
            return
        except FileNotFoundError:
            pass
        except instaloader.exceptions.LoginRequiredException:
            logger.warning("Instagram session expired, re-authenticating")

        loader.login(user=username, passwd=password)
        loader.save_session_to_file(session_file)

    @staticmethod
    def _ensure_ds_user_id(loader: instaloader.Instaloader) -> None:
        """Réinjecte le cookie ``ds_user_id`` s'il est absent de la session.

        Les sessions importées depuis un simple ``sessionid`` n'ont pas toujours
        ``ds_user_id``. Or Instagram renvoie **403 Forbidden** sur ``graphql/query``
        (récupération des posts) quand ce cookie manque, alors même que le login
        est valide. L'id utilisateur est le préfixe du ``sessionid``
        (``<ds_user_id>%3A<token>...``), on le reconstitue donc à la volée.
        """
        jar = loader.context._session.cookies
        cookies = jar.get_dict()
        if cookies.get("ds_user_id"):
            return
        sessionid = cookies.get("sessionid", "")
        uid = sessionid.split("%3A")[0].split(":")[0]
        if uid.isdigit():
            jar.set("ds_user_id", uid, domain=".instagram.com")

    @staticmethod
    def normalize_account(account: str) -> str:
        return account.lstrip("@")

    @staticmethod
    def shortcode_from_url(url: str) -> str | None:
        """Renvoie le shortcode si ``url`` est un lien de post/reel/tv Instagram."""
        match = _IG_POST_RE.search(url or "")
        return match.group(1) if match else None

    def _profile(self, username: str) -> instaloader.Profile:
        """Résout le profil via l'API GraphQL d'instaloader (session authentifiée)."""
        return instaloader.Profile.from_username(self._loader.context, username)

    def fetch_post(self, shortcode: str) -> InstagramPost:
        """Récupère UN seul post par son shortcode (import par lien, 1 requête)."""
        post = instaloader.Post.from_shortcode(self._loader.context, shortcode)
        return self._normalize_post(post)

    def fetch_posts(
        self,
        account: str,
        max_posts: int | None = None,
        page_delay: float = 0.0,
        page_size: int = 50,
    ) -> list[InstagramPost]:
        """Récupère les posts du compte via la pagination GraphQL complète.

        ``Profile.get_posts()`` parcourt tout le profil (curseur ``end_cursor`` /
        ``has_next_page``) — il n'y a plus de plafond ~100 de l'ancien endpoint
        ``feed/user``. ``max_posts`` borne optionnellement la collecte ; ``page_delay``
        ajoute une tempo toutes les ``page_size`` posts pour lisser les requêtes
        (anti-blocage).
        """
        profile = self._profile(self.normalize_account(account))
        posts: list[InstagramPost] = []
        for post in profile.get_posts():
            if max_posts is not None and len(posts) >= max_posts:
                break
            posts.append(self._normalize_post(post))
            self._throttle(len(posts), page_delay, page_size)
        return posts

    def fetch_new_posts(
        self,
        account: str,
        since: datetime,
        page_delay: float = 0.0,
        page_size: int = 50,
    ) -> list[InstagramPost]:
        """Posts plus récents que ``since`` (les posts sont parcourus du + récent au + ancien)."""
        profile = self._profile(self.normalize_account(account))
        since_ts = since.timestamp()
        posts: list[InstagramPost] = []
        for post in profile.get_posts():
            if self._post_timestamp(post) <= since_ts:
                break
            posts.append(self._normalize_post(post))
            self._throttle(len(posts), page_delay, page_size)
        return posts

    @staticmethod
    def _throttle(collected: int, page_delay: float, page_size: int) -> None:
        """Tempo anti-blocage toutes les ``page_size`` posts collectés."""
        if page_delay > 0 and page_size > 0 and collected % page_size == 0:
            time.sleep(page_delay)

    @staticmethod
    def _post_timestamp(post) -> float:
        dt = post.date_utc
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.timestamp()

    @classmethod
    def _normalize_post(cls, post) -> InstagramPost:
        """Convertit un ``instaloader.Post`` (GraphQL) en :class:`InstagramPost`."""
        caption_text = post.caption or ""

        images: list[str] = []
        video_url: str | None = None

        if post.typename == "GraphSidecar":
            for node in post.get_sidecar_nodes():
                if node.display_url:
                    images.append(node.display_url)
                if node.is_video and video_url is None:
                    video_url = node.video_url
        else:
            if post.url:
                images.append(post.url)
            if post.is_video:
                video_url = post.video_url

        first_line = caption_text.split("\n")[0][:100]
        title = first_line if first_line else f"Post {post.shortcode}"

        return InstagramPost(
            shortcode=post.shortcode,
            url=cls.POST_URL.format(shortcode=post.shortcode),
            title=title,
            caption=caption_text,
            images=images[:20],
            video_url=video_url,
            timestamp=cls._aware_utc(post.date_utc),
        )

    @staticmethod
    def _aware_utc(dt: datetime) -> datetime:
        return dt if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)
