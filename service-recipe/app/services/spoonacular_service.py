import logging
from dataclasses import dataclass, field
from typing import Any

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

DEFAULT_RECIPE_COUNT = 3
MIN_RECIPE_COUNT = 1
MAX_RECIPE_COUNT = 5


@dataclass
class SpoonacularRecipe:
    """Une recette Spoonacular normalisée (champs utiles + payload brut)."""

    spoonacular_id: int
    title: str
    image_url: str | None = None
    source_url: str | None = None
    payload: dict[str, Any] = field(default_factory=dict)


class SpoonacularClient:
    """Client async minimal pour l'API Spoonacular (endpoint ``/recipes/random``).

    Authentification par header ``x-api-key`` (cf. https://spoonacular.com/food-api).
    Désactivé (pas de clé) → renvoie une liste vide. Best-effort : les erreurs
    réseau / HTTP / JSON sont loguées et donnent une liste vide, de sorte que la
    tâche quotidienne ne fasse jamais planter le worker.
    """

    def __init__(
        self,
        api_key: str | None = None,
        api_url: str | None = None,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self._api_key = (
            api_key if api_key is not None else settings.SPOONACULAR_API_KEY
        )
        self._api_url = (api_url or settings.SPOONACULAR_API_URL).rstrip("/")
        self._injected_client = http_client

    @property
    def enabled(self) -> bool:
        return bool(self._api_key)

    def _headers(self) -> dict[str, str]:
        return {"x-api-key": self._api_key}

    async def _request(self, method: str, url: str, **kwargs) -> httpx.Response:
        if self._injected_client is not None:
            resp = await self._injected_client.request(method, url, **kwargs)
        else:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.request(method, url, **kwargs)
        resp.raise_for_status()
        return resp

    async def random_recipes(
        self, count: int = DEFAULT_RECIPE_COUNT
    ) -> list[SpoonacularRecipe]:
        """Renvoie jusqu'à ``count`` recettes aléatoires (borné à 1..5).

        Liste vide si le client est désactivé (pas de clé) ou en cas d'erreur
        (réseau, quota, réponse malformée) — l'appelant traite ça comme « rien
        de neuf aujourd'hui ».
        """
        if not self.enabled:
            logger.info("Spoonacular désactivé (pas de clé) — fetch ignoré")
            return []
        count = max(MIN_RECIPE_COUNT, min(count, MAX_RECIPE_COUNT))

        try:
            resp = await self._request(
                "GET",
                f"{self._api_url}/recipes/random",
                headers=self._headers(),
                params={"number": count},
            )
            results = resp.json().get("recipes", [])
        except httpx.HTTPError as exc:
            logger.warning("Spoonacular random fetch failed: %s", exc)
            return []
        except ValueError as exc:  # JSON malformé
            logger.warning("Spoonacular réponse malformée: %s", exc)
            return []

        recipes: list[SpoonacularRecipe] = []
        for raw in results:
            rid = raw.get("id")
            if rid is None:
                continue
            recipes.append(
                SpoonacularRecipe(
                    spoonacular_id=int(rid),
                    title=raw.get("title") or "",
                    image_url=raw.get("image"),
                    source_url=raw.get("sourceUrl"),
                    payload=raw,
                )
            )
        return recipes
