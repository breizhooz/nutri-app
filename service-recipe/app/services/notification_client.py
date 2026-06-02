from __future__ import annotations

import logging
from contextlib import asynccontextmanager

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)


class NotificationClient:
    """HTTP client for service-to-service calls to service-notification.

    Best-effort : un échec d'envoi est journalisé mais n'interrompt jamais
    l'import (la notification n'est qu'un confort UI).
    """

    def __init__(self, http_client: httpx.AsyncClient | None = None) -> None:
        self._injected_client = http_client

    @asynccontextmanager
    async def _client(self):
        if self._injected_client is not None:
            yield self._injected_client
            return
        headers = {}
        if settings.SERVICE_NOTIFICATION_TOKEN:
            headers["Authorization"] = f"Bearer {settings.SERVICE_NOTIFICATION_TOKEN}"
        async with httpx.AsyncClient(
            base_url=settings.SERVICE_NOTIFICATION_URL,
            headers=headers,
            timeout=10.0,
        ) as client:
            yield client

    async def _post(self, payload: dict, log_label: str, user_id: str) -> None:
        if not settings.SERVICE_NOTIFICATION_URL:
            return
        try:
            async with self._client() as client:
                resp = await client.post("/api/v1/notify", json=payload)
                resp.raise_for_status()
        except httpx.HTTPError as exc:
            logger.error("%s échoué (user=%s) : %s", log_label, user_id, exc)

    async def notify_import_done(
        self, user_id: str, recipes_created: int, ingredients_upserted: int
    ) -> None:
        body = (
            f"Import terminé : {recipes_created} recette(s) créée(s), "
            f"{ingredients_upserted} ingrédient(s) ajouté(s)/mis à jour."
        )
        payload = {
            "user_slug": user_id,
            "type": "recipe_import_done",
            "title": "NutriPlanner — Import de recettes terminé",
            "body": body,
            "data": {
                "recipes_created": recipes_created,
                "ingredients_upserted": ingredients_upserted,
            },
        }
        await self._post(payload, "notify_import_done", user_id)

    async def notify_import_error(self, user_id: str, error: str) -> None:
        payload = {
            "user_slug": user_id,
            "type": "system",
            "title": "NutriPlanner — Échec de l'import de recettes",
            "body": error,
            "data": None,
        }
        await self._post(payload, "notify_import_error", user_id)
