import logging
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup

from app.core.config import settings

logger = logging.getLogger(__name__)



class WebService:

    _js_threshold: int = settings.JS_DETECTION_THRESHOLD

    @classmethod
    def get_js_threshold(cls) -> int :
        return cls._js_threshold

    @classmethod
    def set_js_threshold(cls, value: int) -> None:
        cls._js_threshold = value

    async def fetch(self, url: str) -> dict:
        try:
            async with httpx.AsyncClient(follow_redirects=True, timeout=30.0) as client:
                response = await client.get(url)
                response.raise_for_status()
            result = self._parse_html(url, response.text)
            if len(result["raw_content"]) < self._js_threshold:
                logger.info("JS site detected for %s, falling back to Playwright", url)
                result = await self._fetch_with_playwright(url)
            return result
        except httpx.HTTPError as exc:
            logger.warning("httpx failed for %s (%s), trying Playwright", url, exc)
            return await self._fetch_with_playwright(url)

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
        raw_content = content_tag.get_text(separator="\n", strip=True) if content_tag else ""

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
            "images": images[:20],
            "video_url": None,
        }

    async def _fetch_with_playwright(self, url: str) -> dict:
        from playwright.async_api import async_playwright

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            try:
                page = await browser.new_page()
                await page.goto(url, wait_until="networkidle", timeout=30_000)
                html = await page.content()
            finally:
                await browser.close()
        return self._parse_html(url, html)