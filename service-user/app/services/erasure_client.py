"""Client HTTP inter-service pour l'effacement RGPD (art. 17).

Déclenche la purge des données d'un compte dans chaque microservice détenteur,
via leur endpoint interne ``POST /api/v1/internal/erasure`` (gardé par token de
service). Contrat à clés mixtes : ``account_ids`` + ``user_id``.
"""

import logging

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

# Services cibles détenant des données du compte (ordre stable).
ERASURE_SERVICES: tuple[str, ...] = ("profile", "menu", "notification", "nutrition")


def _service_target(service: str) -> tuple[str, str]:
    """Retourne (url, token) pour le service cible."""
    mapping = {
        "profile": (settings.PROFILE_SERVICE_URL, settings.PROFILE_SERVICE_TOKEN),
        "menu": (settings.MENU_SERVICE_URL, settings.MENU_SERVICE_TOKEN),
        "notification": (
            settings.NOTIFICATION_SERVICE_URL,
            settings.NOTIFICATION_SERVICE_TOKEN,
        ),
        "nutrition": (settings.NUTRITION_SERVICE_URL, settings.NUTRITION_SERVICE_TOKEN),
    }
    return mapping[service]


class ErasureClient:
    """Appelle l'endpoint interne d'effacement d'un microservice."""

    def __init__(
        self, http_client: httpx.AsyncClient | None = None, timeout: float = 10.0
    ) -> None:
        self._client = http_client
        self._timeout = timeout

    async def erase(
        self, service: str, account_ids: list[str], user_id: str | None
    ) -> int:
        """Demande l'effacement au service cible. Retourne le nb de lignes purgées.

        Lève en cas de service non configuré ou de réponse HTTP non 2xx — l'appelant
        (orchestrateur) marque alors la cible ``failed`` pour rejeu ultérieur.
        """
        url, token = _service_target(service)
        if not url or not token:
            raise RuntimeError(
                f"service '{service}' non configuré (URL/token manquant)"
            )

        endpoint = f"{url.rstrip('/')}/api/v1/internal/erasure"
        payload = {"account_ids": account_ids, "user_id": user_id}
        headers = {"Authorization": f"Bearer {token}"}

        if self._client is not None:
            resp = await self._client.post(endpoint, json=payload, headers=headers)
        else:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                resp = await client.post(endpoint, json=payload, headers=headers)
        resp.raise_for_status()
        return int(resp.json().get("deleted", 0))
