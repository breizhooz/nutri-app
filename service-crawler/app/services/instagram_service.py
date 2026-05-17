import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone

import instaloader

logger = logging.getLogger(__name__)

INSTAGRAM_POST_URL = "https://www.instagram.com/p/{shortcode}/"


@dataclass
class InstagramPost:
    """Représentation normalisée d'un post Instagram."""
    shortcode: str
    url: str
    title: str
    caption: str
    images: list[str] = field(default_factory=list)
    video_url: str | None = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class InstagramService:
    """Extraction de posts Instagram via Instaloader."""

    def __init__(self, loader: instaloader.Instaloader | None = None):
        self._loader = loader or instaloader.Instaloader(
            download_pictures=False,
            download_videos=False,
            download_video_thumbnails=False,
            download_geotags=False,
            download_comments=False,
            save_metadata=False,
            compress_json=False,
            quiet=True,
        )

    @staticmethod
    def normalize_account(account: str) -> str:
        """Retire le préfixe @ si présent."""
        return account.lstrip("@")

    def fetch_posts(self, account: str) -> list[InstagramPost]:
        """
        Récupère tous les posts d'un compte public Instagram.

        Raises:
            instaloader.exceptions.ProfileNotExistsException: compte introuvable.
            instaloader.exceptions.PrivateProfileNotFollowedException: compte privé.
        """
        username = self.normalize_account(account)
        profile = instaloader.Profile.from_username(self._loader.context, username)
        return [self._normalize_post(post) for post in profile.get_posts()]

    def fetch_new_posts(self, account: str, since: datetime) -> list[InstagramPost]:
        """
        Récupère uniquement les posts publiés après `since`.

        Instaloader retourne les posts du plus récent au plus ancien ;
        on s'arrête dès qu'on dépasse la date limite.
        """
        username = self.normalize_account(account)
        profile = instaloader.Profile.from_username(self._loader.context, username)
        # Instaloader expose des dates UTC naïves
        since_naive = since.replace(tzinfo=None)
        posts: list[InstagramPost] = []
        for post in profile.get_posts():
            if post.date_utc <= since_naive:
                break
            posts.append(self._normalize_post(post))
        return posts

    @staticmethod
    def _normalize_post(post: instaloader.Post) -> InstagramPost:
        """Transforme un Post Instaloader en InstagramPost normalisé."""
        images: list[str] = []
        video_url: str | None = None

        if post.typename == "GraphSidecar":
            # Carousel : image ou vidéo pour chaque nœud
            for node in post.get_sidecar_nodes():
                images.append(node.display_url)
                if node.is_video and video_url is None:
                    video_url = node.video_url
        else:
            images.append(post.url)
            if post.is_video:
                video_url = post.video_url

        caption = post.caption or ""
        first_line = caption.split("\n")[0][:100]
        title = first_line if first_line else f"Post {post.shortcode}"

        return InstagramPost(
            shortcode=post.shortcode,
            url=INSTAGRAM_POST_URL.format(shortcode=post.shortcode),
            title=title,
            caption=caption,
            images=images[:20],
            video_url=video_url,
            # Instaloader retourne des datetimes UTC naïves — on les rend aware
            timestamp=post.date_utc.replace(tzinfo=timezone.utc),
        )
