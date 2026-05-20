from __future__ import annotations

import logging
from contextlib import asynccontextmanager

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)


class NotificationClient:
    """Client HTTP vers service-notification (appels inter-services).

    Le client httpx est injectable pour les tests.
    """

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

    async def notify_macro_error(
        self,
        user_id: str,
        raw_ingredient: str,
        macro_error_slug: str,
    ) -> None:
        payload = {
            "user_slug": user_id,
            "type": "macro_error",
            "title": "NutriPlanner — Ingrédient non reconnu",
            "body": f"« {raw_ingredient} » n'a pas été trouvé dans notre base.",
            "data": {"macro_error_slug": macro_error_slug},
        }
        try:
            async with self._client() as client:
                resp = await client.post("/api/v1/notify", json=payload)
                resp.raise_for_status()
        except httpx.HTTPError as exc:
            logger.error("notify_macro_error failed (user=%s): %s", user_id, exc)