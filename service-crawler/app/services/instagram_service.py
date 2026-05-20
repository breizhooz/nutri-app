import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone

import instaloader

from app.core.config import settings

logger = logging.getLogger(__name__)


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
        except FileNotFoundError:
            loader.login(user=username, passwd=password)
            loader.save_session_to_file(session_file)

    @staticmethod
    def normalize_account(account: str) -> str:
        return account.lstrip("@")

    def fetch_posts(self, account: str) -> list[InstagramPost]:
        username = self.normalize_account(account)
        profile = instaloader.Profile.from_username(self._loader.context, username)
        return [self._normalize_post(post) for post in profile.get_posts()]

    def fetch_new_posts(self, account: str, since: datetime) -> list[InstagramPost]:
        username = self.normalize_account(account)
        profile = instaloader.Profile.from_username(self._loader.context, username)
        since_naive = since.replace(tzinfo=None)
        posts: list[InstagramPost] = []
        for post in profile.get_posts():
            if post.date_utc <= since_naive:
                break
            posts.append(self._normalize_post(post))
        return posts

    @classmethod
    def _normalize_post(cls, post: instaloader.Post) -> InstagramPost:
        images: list[str] = []
        video_url: str | None = None

        if post.typename == "GraphSidecar":
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
            url=cls.POST_URL.format(shortcode=post.shortcode),
            title=title,
            caption=caption,
            images=images[:20],
            video_url=video_url,
            timestamp=post.date_utc.replace(tzinfo=timezone.utc),
        )