"""Client HTTP inter-service vers service-profile.

Récupère le résumé nutritionnel d'un utilisateur (profil, calcul métabolique,
préférences, contraintes médicales) en un seul appel, authentifié par le token
de service ``SERVICE_PROFILE_TOKEN``.
"""

import logging
import uuid

import httpx

from app.core.config import settings
from app.schemas.nutrition_summary import NutritionSummary

logger = logging.getLogger(__name__)


class ProfileClient:
    """Client async minimaliste pour service-profile."""

    def __init__(
        self,
        base_url: str | None = None,
        service_token: str | None = None,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self._base_url = (base_url or settings.SERVICE_PROFILE_URL).rstrip("/")
        self._token = (
            service_token
            if service_token is not None
            else settings.SERVICE_PROFILE_TOKEN
        )
        self._injected_client = http_client

    @property
    def enabled(self) -> bool:
        """Le client est exploitable seulement si un token de service est configuré."""
        return bool(self._token)

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._token}"}

    async def _request(self, method: str, url: str, **kwargs) -> httpx.Response:
        if self._injected_client is not None:
            return await self._injected_client.request(method, url, **kwargs)
        async with httpx.AsyncClient(timeout=10.0) as client:
            return await client.request(method, url, **kwargs)

    async def get_nutrition_summary(
        self, user_id: uuid.UUID
    ) -> NutritionSummary | None:
        """Retourne le résumé nutritionnel d'un utilisateur.

        Best-effort : retourne None si le client est désactivé, si le profil
        n'existe pas (404), ou en cas d'erreur réseau / réponse invalide — afin
        de ne jamais faire échouer l'appelant à cause de service-profile.
        """
        if not self.enabled:
            logger.info("ProfileClient désactivé (aucun token) — appel ignoré")
            return None

        url = f"{self._base_url}/api/v1/profiles/{user_id}/nutrition-summary"
        try:
            resp = await self._request("GET", url, headers=self._headers())
            if resp.status_code == 404:
                logger.info("Aucun profil nutrition pour user_id=%s", user_id)
                return None
            resp.raise_for_status()
            return NutritionSummary.model_validate(resp.json())
        except (httpx.HTTPError, ValueError) as exc:
            logger.warning(
                "Échec récupération du résumé nutrition pour user_id=%s : %s",
                user_id,
                exc,
            )
            return None
