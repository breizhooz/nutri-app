import logging
from contextlib import asynccontextmanager
from dataclasses import dataclass

import httpx
from app.core.config import settings

logger = logging.getLogger(__name__)


@dataclass
class NutritionResult:
    calories_per_serving: float
    proteins_per_serving: float
    carbs_per_serving: float
    fats_per_serving: float


class NutritionServiceClient:
    """HTTP client for inter-service calls to service-nutrition /api/v1/calculate."""

    def __init__(self, http_client: httpx.AsyncClient | None = None) -> None:
        self._injected_client = http_client

    @asynccontextmanager
    async def _client(self):
        if self._injected_client is not None:
            yield self._injected_client
            return
        headers = {}
        if settings.SERVICE_NUTRITION_TOKEN:
            headers["Authorization"] = f"Bearer {settings.SERVICE_NUTRITION_TOKEN}"
        async with httpx.AsyncClient(
            base_url=settings.SERVICE_NUTRITION_URL,
            headers=headers,
            timeout=30.0,
            follow_redirects=True,
        ) as client:
            yield client

    async def calculate(
        self,
        recipe_slug: str,
        servings: int,
        user_id: str,
        ingredients: list[dict],
    ) -> NutritionResult | None:
        if not settings.SERVICE_NUTRITION_URL:
            return None
        raw_texts = [
            f"{ing['quantity']} {ing['unit']} {ing['name']}" for ing in ingredients
        ]
        payload = {
            "recipe_slug": recipe_slug,
            "servings": servings,
            "user_id": user_id,
            "ingredients": [{"raw_text": t} for t in raw_texts],
        }
        try:
            async with self._client() as client:
                resp = await client.post("/api/v1/calculate", json=payload)
                resp.raise_for_status()
            data = resp.json()
            ps = data.get("per_serving", {})
            return NutritionResult(
                calories_per_serving=ps.get("calories", 0.0),
                proteins_per_serving=ps.get("proteines", 0.0),
                carbs_per_serving=ps.get("glucides", 0.0),
                fats_per_serving=ps.get("lipides", 0.0),
            )
        except (httpx.HTTPStatusError, httpx.RequestError) as exc:
            logger.warning("Nutrition calculation failed for %r: %s", recipe_slug, exc)
            return None


class ServiceUnavailableError(Exception):
    """Raise a exception if service-user doesnt responding."""

    pass


class ServicesUserClient:
    """
    Http client allow to communicate with service-user
    """

    def __init__(self):
        self.base_url = settings.SERVICE_USER_URL
        self._client = None

    async def __aenter__(self):
        self._client = httpx.AsyncClient(base_url=self.base_url, timeout=5.0)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self._client:
            await self._client.aclose()

    async def user_exist(self, user_id: str) -> bool:
        """
        check if user exist in service-user
        """
        try:
            response = await self._client.get(f"/api/v1/users/{user_id}/exists")
            response.raise_for_status()
            return response.json().get("exists", False)
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return False
            raise ServiceUnavailableError(
                f"service-user responded {e.response.status_code}"
            ) from e
        except httpx.HTTPError as e:
            raise ServiceUnavailableError(f"service-user unavailable: {e}") from e


async def get_user_client():
    async with ServicesUserClient() as client:
        yield client
