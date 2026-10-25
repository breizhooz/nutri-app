import logging
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup

from app.core.config import settings
from app.core.ssrf import assert_public_url
from app.services.recipe_schema_extractor import RecipeSchemaExtractor

logger = logging.getLogger(__name__)

_MAX_IMAGES = 20


class PermanentFetchError(Exception):
    """Échec définitif du crawl d'une page : inutile de réessayer."""


class InsufficientContentError(PermanentFetchError):
    """Page sans recette structurée et au texte trop court (site rendu en JS)."""


class WebService:
    _js_threshold: int = settings.JS_DETECTION_THRESHOLD

    def __init__(self, schema_extractor: RecipeSchemaExtractor | None = None) -> None:
        self._schema_extractor = schema_extractor or RecipeSchemaExtractor()

    @classmethod
    def get_js_threshold(cls) -> int:
        return cls._js_threshold

    @classmethod
    def set_js_threshold(cls, value: int) -> None:
        cls._js_threshold = value

    async def fetch(self, url: str) -> dict:
        # SEC-03 : refuse toute cible non publique AVANT la moindre requête.
        assert_public_url(url)
        html = await self._download(url)
        page = self._parse_html(url, html)

        # 1) Recette publiée en données structurées (schema.org) : prioritaire,
        #    y compris quand le texte visible est vide (site rendu en JS).
        recipe = self._schema_extractor.extract(url, html)
        if recipe is not None:
            recipe["title"] = recipe["title"] or page["title"]
            recipe["images"] = self._merge_images(recipe["images"], page["images"])
            return recipe

        # 2) Sinon, texte brut de la page — s'il y en a assez.
        if len(page["raw_content"]) < self._js_threshold:
            raise InsufficientContentError(
                f"Aucune recette structurée et contenu trop court "
                f"({len(page['raw_content'])} car.) pour {url} "
                f"— page probablement rendue en JavaScript"
            )
        return page

    async def _download(self, url: str) -> str:
        async with httpx.AsyncClient(follow_redirects=True, timeout=30.0) as client:
            response = await client.get(url)
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            code = exc.response.status_code
            if self._is_permanent_status(code):
                raise PermanentFetchError(f"HTTP {code} pour {url}") from exc
            raise
        return response.text

    @staticmethod
    def _is_permanent_status(code: int) -> bool:
        """4xx = définitif (404, 403, 410…), sauf les codes « réessayez plus tard »."""
        return 400 <= code < 500 and code not in (408, 425, 429)

    @staticmethod
    def _merge_images(first: list[str], others: list[str]) -> list[str]:
        merged = list(dict.fromkeys([*first, *others]))
        return merged[:_MAX_IMAGES]

    def _parse_html(self, base_url: str, html: str) -> dict:
        soup = BeautifulSoup(html, "html.parser")

        title = ""
        if soup.title and soup.title.string:
            title = soup.title.string.strip()
        if not title:
            h1 = soup.find("h1")
            if h1:
                title = h1.get_text(strip=True)

        content_tag = soup.find("article") or soup.find("main") or soup.body
        raw_content = (
            content_tag.get_text(separator="\n", strip=True) if content_tag else ""
        )

        images: list[str] = []
        for img in soup.find_all("img"):
            src = img.get("src", "").strip()
            if src:
                absolute = urljoin(base_url, src)
                if absolute.startswith("http"):
                    images.append(absolute)

        return {
            "title": title,
            "raw_content": raw_content,
            "images": images[:_MAX_IMAGES],
            "video_url": None,
        }
