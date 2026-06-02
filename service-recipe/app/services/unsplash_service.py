import logging
from dataclasses import asdict, dataclass

import httpx

from app.core.config import settings
from app.core.exceptions import ImageServiceUnavailable

logger = logging.getLogger(__name__)

DEFAULT_SUGGESTION_COUNT = 4


@dataclass
class ImageSuggestion:
    """One Unsplash photo proposal (thumbnail + HD url + tracking metadata)."""

    unsplash_id: str
    thumb_url: str
    full_url: str
    download_location: str
    author: str | None = None
    author_url: str | None = None

    def to_dict(self) -> dict:
        return asdict(self)


class UnsplashService:
    """
    Thin async client for the Unsplash public API.

    Uses application-only auth (``Authorization: Client-ID <ACCESS_KEY>``), which is
    all that is required to search photos. The download endpoint is triggered when a
    photo is actually selected, as required by the Unsplash API guidelines.
    """

    def __init__(
        self,
        access_key: str | None = None,
        api_url: str | None = None,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self._access_key = (
            access_key if access_key is not None else settings.UNSPLASH_ACCESS_KEY
        )
        self._api_url = (api_url or settings.UNSPLASH_API_URL).rstrip("/")
        self._injected_client = http_client

    @property
    def enabled(self) -> bool:
        return bool(self._access_key)

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Client-ID {self._access_key}",
            "Accept-Version": "v1",
        }

    async def _request(self, method: str, url: str, **kwargs) -> httpx.Response:
        if self._injected_client is not None:
            resp = await self._injected_client.request(method, url, **kwargs)
        else:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.request(method, url, **kwargs)
        resp.raise_for_status()
        return resp

    async def search(
        self, keyword: str, count: int = DEFAULT_SUGGESTION_COUNT
    ) -> list[ImageSuggestion]:
        """
        Return up to ``count`` image suggestions for ``keyword``.

        Renvoie une liste vide si Unsplash est désactivé (pas de clé) ou si le
        mot-clé est vide. En cas de **rate-limit / 403** (quota dépassé), lève
        ``ImageServiceUnavailable`` pour que l'appelant puisse l'afficher comme une
        indisponibilité (et non comme un « 0 résultat » trompeur). Les autres
        erreurs (réseau, réponse malformée) restent best-effort → liste vide.
        """
        if not self.enabled:
            logger.info("Unsplash disabled (no access key) — skipping image search")
            return []
        keyword = (keyword or "").strip()
        if not keyword:
            return []

        try:
            resp = await self._request(
                "GET",
                f"{self._api_url}/search/photos",
                headers=self._headers(),
                params={
                    "query": keyword,
                    "per_page": count,
                    "orientation": "landscape",
                },
            )
            results = resp.json().get("results", [])
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code in (403, 429):
                logger.warning(
                    "Unsplash indisponible (quota/clé) pour %r : %s", keyword, exc
                )
                raise ImageServiceUnavailable() from exc
            logger.warning("Unsplash search failed for %r: %s", keyword, exc)
            return []
        except (httpx.HTTPError, ValueError) as exc:
            logger.warning("Unsplash search failed for %r: %s", keyword, exc)
            return []

        suggestions: list[ImageSuggestion] = []
        for photo in results[:count]:
            urls = photo.get("urls", {})
            user = photo.get("user", {})
            suggestions.append(
                ImageSuggestion(
                    unsplash_id=photo.get("id", ""),
                    thumb_url=urls.get("thumb") or urls.get("small", ""),
                    full_url=urls.get("regular") or urls.get("full", ""),
                    download_location=photo.get("links", {}).get(
                        "download_location", ""
                    ),
                    author=user.get("name"),
                    author_url=(user.get("links") or {}).get("html"),
                )
            )
        return suggestions

    async def track_download(self, download_location: str) -> None:
        """
        Notify Unsplash that a photo was used (mandatory per their API guidelines).
        Best-effort: failures are logged and swallowed.
        """
        if not self.enabled or not download_location:
            return
        try:
            await self._request("GET", download_location, headers=self._headers())
        except httpx.HTTPError as exc:
            logger.warning("Unsplash download tracking failed: %s", exc)
