import httpx
from app.core.config import settings


class ServiceUnavailableError(Exception):
    """Raise a exception if service doesnt responding."""

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
            response = await self._client.get(f"/users/{user_id}/exists")
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


class ServicesRecipeClient:
    """
    Http client allow to communicate with service-recipe
    """

    def __init__(self):
        self.base_url = settings.SERVICE_RECIPE_URL
        self._client = None

    async def __aenter__(self):
        self._client = httpx.AsyncClient(base_url=self.base_url, timeout=5.0)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self._client:
            await self._client.aclose()

<<<<<<< Updated upstream
    async def get_recipes(self, max_recipes: int = 200) -> list[dict]:
        try:
            all_items: list[dict] = []
            page = 1
            page_size = 50
            while len(all_items) < max_recipes:
=======
    async def get_recipes(self, skip: int = 0, limit: int = 200) -> list[dict]:
        """Récupère jusqu'à `limit` recettes en suivant la pagination de service-recipe.

        service-recipe expose `GET /api/v1/recipe` (singulier) qui renvoie un objet
        paginé {items, total, page, page_size, pages} avec page_size ≤ 50.
        """
        page_size = min(limit, 50) if limit else 50
        items: list[dict] = []
        page = 1
        try:
            while len(items) < limit:
>>>>>>> Stashed changes
                response = await self._client.get(
                    "/api/v1/recipe",
                    params={"page": page, "page_size": page_size},
                )
                response.raise_for_status()
                data = response.json()
<<<<<<< Updated upstream
                items = data.get("items", [])
                all_items.extend(items)
                if len(items) < page_size or len(all_items) >= data.get("total", 0):
                    break
                page += 1
            return all_items
=======
                batch = data.get("items", [])
                items.extend(batch)
                if not batch or page >= data.get("pages", page):
                    break
                page += 1
            return items[:limit]
>>>>>>> Stashed changes
        except httpx.HTTPStatusError as e:
            raise ServiceUnavailableError(
                f"service-recipe responded {e.response.status_code}"
            ) from e
        except httpx.HTTPError as e:
            raise ServiceUnavailableError(f"service-recipe unavailable: {e}") from e

    async def get_recipe_by_id(self, recipe_id: int) -> dict | None:
        try:
            response = await self._client.get(f"/api/v1/recipe/id/{recipe_id}")
            if response.status_code == 404:
                return None
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            raise ServiceUnavailableError(
                f"service-recipe responded {e.response.status_code}"
            ) from e
        except httpx.HTTPError as e:
            raise ServiceUnavailableError(f"service-recipe unavailable: {e}") from e

    async def get_recipe_by_slug(self, slug: str) -> dict | None:
        try:
            response = await self._client.get(f"/api/v1/recipe/{slug}")
            if response.status_code == 404:
                return None
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            raise ServiceUnavailableError(
                f"service-recipe responded {e.response.status_code}"
            ) from e
        except httpx.HTTPError as e:
            raise ServiceUnavailableError(f"service-recipe unavailable: {e}") from e


async def get_user_client():
    async with ServicesUserClient() as client:
        yield client


async def get_recipe_client():
    async with ServicesRecipeClient() as client:
        yield client
