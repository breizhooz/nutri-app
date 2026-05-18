from __future__ import annotations

import logging
from contextlib import asynccontextmanager

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)


class NotificationClient:
    """HTTP client for service-to-service calls to service-notification."""

    def __init__(self, http_client: httpx.AsyncClient | None = None) -> None:
        self._injected_client = http_client

    @asynccontextmanager
    async def _client(self):
        if self._injected_client is not None:
            yield self._injected_client
            return
        async with httpx.AsyncClient(
            base_url=settings.SERVICE_NOTIFICATION_URL,
            headers={"Authorization": f"Bearer {settings.SERVICE_NOTIFICATION_TOKEN}"},
            timeout=10.0,
        ) as client:
            yield client

    async def notify_crawl_done(
        self,
        user_id: str,
        source_type: str,
        new_count: int,
        source_label: str = "",
    ) -> None:
        label = source_label or source_type
        body = (
            f"{new_count} recette(s) extraite(s) depuis {label} "
            "sont en attente de validation."
        )
        payload = {
            "user_slug": user_id,
            "type": "crawl_done",
            "title": "NutriPlanner — Nouveaux contenus",
            "body": body,
            "data": {"source_type": source_type, "new_count": new_count},
        }
        try:
            async with self._client() as client:
                resp = await client.post("/api/v1/notify", json=payload)
                resp.raise_for_status()
        except httpx.HTTPError as exc:
            logger.error("notify_crawl_done échoué (user=%s) : %s", user_id, exc)

    async def notify_crawl_error(self, user_id: str, error: str) -> None:
        payload = {
            "user_slug": user_id,
            "type": "system",
            "title": "NutriPlanner — Erreur de crawl",
            "body": error,
            "data": None,
        }
        try:
            async with self._client() as client:
                resp = await client.post("/api/v1/notify", json=payload)
                resp.raise_for_status()
        except httpx.HTTPError as exc:
            logger.error("notify_crawl_error échoué (user=%s) : %s", user_id, exc)