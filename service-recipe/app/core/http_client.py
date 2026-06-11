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


@dataclass
class NutritionTargetsResult:
    """Sortie du moteur de cibles : cibles finales (+ warnings) et requête ES prête."""

    targets: dict
    search_query: dict


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
        account_id: str | None = None,
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
            # Multicomptes : permet à service-nutrition de tagger les macro_errors
            # par compte (frontière). None tant que l'appelant n'est pas account-aware.
            "account_id": account_id,
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

    async def compute_targets(
        self,
        *,
        goal: str,
        diet_type: str,
        tdee_kcal: float,
        bmr_kcal: float,
        weight_kg: float,
        excluded_foods: list[str],
        medical_contraindications: list[str],
        adjustment: dict | None = None,
    ) -> "NutritionTargetsResult | None":
        """Appelle le moteur de cibles (POST /api/v1/nutrition-targets).

        ``adjustment`` (optionnel) transporte les curseurs UI : intensité,
        tolérance variété et overrides manuels.

        Best-effort : retourne None si le service est absent, en erreur, ou si la
        réponse est malformée — l'appelant retombe alors sur une recherche standard.
        """
        if not settings.SERVICE_NUTRITION_URL:
            return None
        payload = {
            "goal": goal,
            "diet_type": diet_type,
            "tdee_kcal": tdee_kcal,
            "bmr_kcal": bmr_kcal,
            "weight_kg": weight_kg,
            "excluded_foods": excluded_foods,
            "medical_contraindications": medical_contraindications,
        }
        if adjustment:
            payload["adjustment"] = adjustment
        try:
            async with self._client() as client:
                resp = await client.post("/api/v1/nutrition-targets", json=payload)
                resp.raise_for_status()
            data = resp.json()
            return NutritionTargetsResult(
                targets=data["targets"], search_query=data["search_query"]
            )
        except (httpx.HTTPStatusError, httpx.RequestError, KeyError, ValueError) as exc:
            logger.warning("Nutrition targets computation failed: %s", exc)
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

    async def default_account(self, user_id: str) -> str | None:
        """Résout le compte personnel (default_account_id) d'une identité.

        Utilisé par les flux pilotés par token de service (crawler/import) pour
        attribuer la recette créée au bon compte. ``None`` si inconnu.
        """
        try:
            response = await self._client.get(
                f"/api/v1/users/{user_id}/default-account"
            )
            response.raise_for_status()
            return response.json().get("account_id")
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return None
            raise ServiceUnavailableError(
                f"service-user responded {e.response.status_code}"
            ) from e
        except httpx.HTTPError as e:
            raise ServiceUnavailableError(f"service-user unavailable: {e}") from e

    async def access_scopes(self, identity_id: str, account_id: str) -> list[str]:
        """Scopes effectifs d'une identité sur un compte (coaching : push).

        Permet à service-recipe de vérifier qu'un coach a bien ``recipe:write``
        sur le compte d'un client (qui n'est pas son compte actif). Liste vide si
        aucune adhésion active.
        """
        try:
            response = await self._client.get(
                f"/api/v1/accounts/{account_id}/access/{identity_id}"
            )
            response.raise_for_status()
            scopes = response.json().get("scopes", [])
            return [s for s in scopes if isinstance(s, str)]
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return []
            raise ServiceUnavailableError(
                f"service-user responded {e.response.status_code}"
            ) from e
        except httpx.HTTPError as e:
            raise ServiceUnavailableError(f"service-user unavailable: {e}") from e


async def get_user_client():
    async with ServicesUserClient() as client:
        yield client
