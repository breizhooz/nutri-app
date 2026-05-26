import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone

import instaloader

from app.core.config import settings

logger = logging.getLogger(__name__)

_IG_APP_ID = "936619743392459"
_IG_BASE = "https://www.instagram.com"


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
            loader.test_login()
            return
        except FileNotFoundError:
            pass
        except instaloader.exceptions.LoginRequiredException:
            logger.warning("Instagram session expired, re-authenticating")

        loader.login(user=username, passwd=password)
        loader.save_session_to_file(session_file)

    def _get(self, path: str, params: dict | None = None) -> dict:
        """Authenticated GET using the instaloader session (preserves all headers/cookies)."""
        session = self._loader.context._session
        resp = session.get(
            f"{_IG_BASE}{path}",
            params=params or {},
            headers={"X-IG-App-ID": _IG_APP_ID},
            timeout=15,
        )
        resp.raise_for_status()
        return resp.json()

    def _resolve_user_id(self, username: str) -> str:
        data = self._get(
            "/web/search/topsearch/",
            {"context": "user", "query": username, "count": "10"},
        )
        for entry in data.get("users", []):
            user = entry.get("user", {})
            if user.get("username") == username:
                return str(user["pk"])
        raise ValueError(f"Instagram user {username!r} not found in search results")

    def _get_media_count(self, user_id: str) -> int:
        """Retourne le nombre total de posts pour un user_id Instagram."""
        data = self._get(f"/api/v1/users/{user_id}/info/")
        return int(data.get("user", {}).get("media_count", 50))

    def _fetch_page(
        self, user_id: str, max_id: str | None = None
    ) -> tuple[list[dict], str | None]:
        params: dict[str, str] = {"count": "50"}
        if max_id:
            params["max_id"] = max_id
        data = self._get(f"/api/v1/feed/user/{user_id}/", params)
        return data.get("items", []), data.get("next_max_id")

    @staticmethod
    def normalize_account(account: str) -> str:
        return account.lstrip("@")

    def fetch_posts(self, account: str, max_posts: int | None = None) -> list[InstagramPost]:
        """Récupère tous les posts du compte. Si max_posts est None, utilise le media_count réel."""
        username = self.normalize_account(account)
        user_id = self._resolve_user_id(username)
        if max_posts is None:
            max_posts = self._get_media_count(user_id)
        posts: list[InstagramPost] = []
        next_max_id: str | None = None

        while len(posts) < max_posts:
            items, next_max_id = self._fetch_page(user_id, next_max_id)
            for item in items:
                if len(posts) >= max_posts:
                    break
                posts.append(self._normalize_item(item))
            if not next_max_id:
                break

        return posts

    def fetch_new_posts(self, account: str, since: datetime) -> list[InstagramPost]:
        username = self.normalize_account(account)
        user_id = self._resolve_user_id(username)
        posts: list[InstagramPost] = []
        next_max_id: str | None = None
        since_ts = since.timestamp()

        while True:
            items, next_max_id = self._fetch_page(user_id, next_max_id)
            done = False
            for item in items:
                if item.get("taken_at", 0) <= since_ts:
                    done = True
                    break
                posts.append(self._normalize_item(item))
            if done or not next_max_id:
                break

        return posts

    @classmethod
    def _normalize_item(cls, item: dict) -> InstagramPost:
        media_type = item.get("media_type", 1)  # 1=photo, 2=video, 8=carousel
        shortcode = item.get("code", "")
        taken_at = item.get("taken_at", 0)
        caption_text = (item.get("caption") or {}).get("text") or ""

        images: list[str] = []
        video_url: str | None = None

        if media_type == 8:
            for node in item.get("carousel_media", []):
                node_imgs = node.get("image_versions2", {}).get("candidates", [])
                if node_imgs:
                    images.append(node_imgs[0]["url"])
                if node.get("media_type") == 2 and video_url is None:
                    vids = node.get("video_versions", [])
                    if vids:
                        video_url = vids[0]["url"]
        else:
            img_candidates = item.get("image_versions2", {}).get("candidates", [])
            if img_candidates:
                images.append(img_candidates[0]["url"])
            if media_type == 2:
                vids = item.get("video_versions", [])
                if vids:
                    video_url = vids[0]["url"]

        first_line = caption_text.split("\n")[0][:100]
        title = first_line if first_line else f"Post {shortcode}"

        return InstagramPost(
            shortcode=shortcode,
            url=cls.POST_URL.format(shortcode=shortcode),
            title=title,
            caption=caption_text,
            images=images[:20],
            video_url=video_url,
            timestamp=datetime.fromtimestamp(taken_at, tz=timezone.utc),
        )

