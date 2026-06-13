"""Client HTTP inter-service pour l'export RGPD (art. 20, portabilité).

Récupère les données d'un compte auprès de chaque microservice détenteur via
leur endpoint interne ``POST /api/v1/internal/export`` (gardé par token de
service). Miroir d'``ErasureClient`` : mêmes cibles, même résolution URL/token.
"""

import logging
from typing import Any

import httpx

from app.services.erasure_client import ERASURE_SERVICES, _service_target

logger = logging.getLogger(__name__)

# Mêmes services détenteurs de données que pour l'effacement (ordre stable).
EXPORT_SERVICES: tuple[str, ...] = ERASURE_SERVICES


class ExportClient:
    """Appelle l'endpoint interne d'export d'un microservice."""

    def __init__(
        self, http_client: httpx.AsyncClient | None = None, timeout: float = 10.0
    ) -> None:
        self._client = http_client
        self._timeout = timeout

    async def export(
        self, service: str, account_ids: list[str], user_id: str | None
    ) -> dict[str, Any]:
        """Récupère les données du service cible. Retourne le dict ``data``.

        Lève en cas de service non configuré ou de réponse HTTP non 2xx —
        l'appelant décide comment traiter l'échec partiel.
        """
        url, token = _service_target(service)
        if not url or not token:
            raise RuntimeError(
                f"service '{service}' non configuré (URL/token manquant)"
            )

        endpoint = f"{url.rstrip('/')}/api/v1/internal/export"
        payload = {"account_ids": account_ids, "user_id": user_id}
        headers = {"Authorization": f"Bearer {token}"}

        if self._client is not None:
            resp = await self._client.post(endpoint, json=payload, headers=headers)
        else:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                resp = await client.post(endpoint, json=payload, headers=headers)
        resp.raise_for_status()
        return dict(resp.json().get("data", {}))
