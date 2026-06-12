import logging

import httpx
from starlette.requests import Request

from app.core.config import settings

logger = logging.getLogger(__name__)


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
    Http client allow to communicate with service-recipe.

    Multicomptes : les recettes sont privées par compte côté service-recipe, qui
    exige un token de contexte (act_account + scope recipe:read). On forwarde donc
    le token de l'utilisateur appelant pour que la génération de menus / les listes
    de courses ne voient que les recettes de SON compte.
    """

    def __init__(self, auth_header: str | None = None):
        self.base_url = settings.SERVICE_RECIPE_URL
        self._auth_header = auth_header
        self._client = None

    async def __aenter__(self):
        headers = {"Authorization": self._auth_header} if self._auth_header else {}
        self._client = httpx.AsyncClient(
            base_url=self.base_url, timeout=5.0, headers=headers
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self._client:
            await self._client.aclose()

    async def get_recipes(self, max_recipes: int = 200) -> list[dict]:
        try:
            all_items: list[dict] = []
            page = 1
            page_size = 50
            while len(all_items) < max_recipes:
                response = await self._client.get(
                    "/api/v1/recipe",
                    params={"page": page, "page_size": page_size},
                )
                response.raise_for_status()
                data = response.json()
                items = data.get("items", [])
                all_items.extend(items)
                if len(items) < page_size or len(all_items) >= data.get("total", 0):
                    break
                page += 1
            return all_items
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


class ServicesProfileClient:
    """
    Http client inter-service vers service-profile (résumé nutritionnel).

    Authentifié par le token de service SERVICE_PROFILE_TOKEN (même mécanique
    que service-recipe → service-profile). Sémantique volontairement
    fail-closed côté réseau : une erreur de service-profile lève
    ServiceUnavailableError plutôt que d'ignorer silencieusement les
    allergies/exclusions de l'utilisateur (sécurité alimentaire). En revanche :
    token non configuré → intégration désactivée (None) ; profil inexistant
    (404) → None.
    """

    def __init__(self):
        self.base_url = settings.SERVICE_PROFILE_URL
        self._token = settings.SERVICE_PROFILE_TOKEN
        self._client = None

    @property
    def enabled(self) -> bool:
        """L'intégration n'est active que si un token de service est configuré."""
        return bool(self._token)

    async def __aenter__(self):
        headers = {"Authorization": f"Bearer {self._token}"} if self._token else {}
        self._client = httpx.AsyncClient(
            base_url=self.base_url, timeout=5.0, headers=headers
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self._client:
            await self._client.aclose()

    async def get_nutrition_summary(self, user_id: str) -> dict | None:
        """Résumé nutritionnel d'un utilisateur (profil, allergies, exclusions…).

        Retourne None si l'intégration est désactivée ou si l'utilisateur n'a
        pas de profil ; lève ServiceUnavailableError sur toute autre erreur.
        """
        if not self.enabled:
            logger.info(
                "SERVICE_PROFILE_TOKEN absent — contraintes profil ignorées "
                "pour la génération de menu"
            )
            return None
        try:
            response = await self._client.get(
                f"/api/v1/profiles/{user_id}/nutrition-summary"
            )
            if response.status_code == 404:
                return None
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            raise ServiceUnavailableError(
                f"service-profile responded {e.response.status_code}"
            ) from e
        except httpx.HTTPError as e:
            raise ServiceUnavailableError(f"service-profile unavailable: {e}") from e


async def get_user_client():
    async with ServicesUserClient() as client:
        yield client


async def get_recipe_client(request: Request):
    # Forward le token de contexte de l'utilisateur vers service-recipe (recettes
    # privées par compte). Sans token, on retombe sur un client non authentifié
    # (les endpoints recipe répondront 401/403 — comportement attendu).
    auth_header = request.headers.get("authorization")
    async with ServicesRecipeClient(auth_header=auth_header) as client:
        yield client


async def get_profile_client():
    async with ServicesProfileClient() as client:
        yield client
