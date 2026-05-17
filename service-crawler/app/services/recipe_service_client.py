import logging
from contextlib import asynccontextmanager

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)


class RecipeServiceClient:
    """HTTP client for service-to-service calls to service-recipe."""

    def __init__(self, http_client: httpx.AsyncClient | None = None) -> None:
        # Inject an httpx.AsyncClient in tests; None → new client per request in production.
        self._injected_client = http_client

    @asynccontextmanager
    async def _client(self):
        if self._injected_client is not None:
            yield self._injected_client
            return
        async with httpx.AsyncClient(
            base_url=settings.SERVICE_RECIPE_URL,
            headers={"Authorization": f"Bearer {settings.SERVICE_RECIPE_TOKEN}"},
            timeout=10.0,
        ) as client:
            yield client

    async def find_ingredient_by_name(self, name: str) -> int | None:
        """Return the id of the ingredient matching `name` (case-insensitive), or None."""
        async with self._client() as client:
            resp = await client.get("/api/v1/ingredient/", params={"skip": 0, "limit": 1000})
            resp.raise_for_status()
        name_lower = name.strip().lower()
        for item in resp.json():
            if item.get("name", "").strip().lower() == name_lower:
                return int(item["id"])
        return None

    async def create_ingredient(self, name: str) -> int:
        """Create a minimal ingredient and return its id."""
        async with self._client() as client:
            resp = await client.post(
                "/api/v1/ingredient/",
                json={"name": name, "tags": [], "free_tags": []},
            )
            resp.raise_for_status()
        return int(resp.json()["id"])

    async def get_or_create_ingredient(self, name: str) -> int:
        """Return the existing ingredient id or create it."""
        ingredient_id = await self.find_ingredient_by_name(name)
        if ingredient_id is not None:
            return ingredient_id
        return await self.create_ingredient(name)

    async def create_recipe(self, payload: dict) -> dict:
        """POST /api/v1/recipe/ and return the created recipe as dict."""
        async with self._client() as client:
            resp = await client.post("/api/v1/recipe/", json=payload)
            resp.raise_for_status()
        return resp.json()