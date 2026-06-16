"""Tests de l'endpoint interne d'export RGPD (art. 20, portabilité).

Depuis la bascule E2E zero-knowledge, l'export ne renvoie que les blobs OPAQUES
(ciphertext base64) du compte : le serveur n'a jamais accès au clair.
"""

import base64
import os
import uuid

import pytest
from httpx import AsyncClient

_BYTES = bytes(range(64))
_B64 = base64.b64encode(_BYTES).decode()


def _service_headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {os.environ['SERVICE_PROFILE_TOKEN']}"}


class TestInternalExport:
    """POST /api/v1/internal/export."""

    @pytest.mark.unit
    async def test_export_returns_encrypted_blobs(
        self,
        client: AsyncClient,
        test_account_id: uuid.UUID,
        test_user_id: uuid.UUID,
    ) -> None:
        """L'export renvoie les blobs chiffrés opaques du compte."""
        put = await client.put(
            "/api/v1/profiles/me/blobs/health/default", json={"ciphertext": _B64}
        )
        assert put.status_code == 200

        resp = await client.post(
            "/api/v1/internal/export",
            headers=_service_headers(),
            json={"account_ids": [str(test_account_id)], "user_id": str(test_user_id)},
        )
        assert resp.status_code == 200
        blobs = resp.json()["data"]["encrypted_blobs"]
        assert len(blobs) == 1
        assert blobs[0]["collection"] == "health"
        assert blobs[0]["ref_key"] == "default"
        # Le ciphertext est rendu opaque (base64), identique à l'entrée.
        assert blobs[0]["ciphertext"] == _B64

    @pytest.mark.unit
    async def test_export_empty_when_no_data(
        self, client: AsyncClient, test_account_id: uuid.UUID
    ) -> None:
        """Sans donnée, l'export renvoie une liste vide (200)."""
        resp = await client.post(
            "/api/v1/internal/export",
            headers=_service_headers(),
            json={"account_ids": [str(test_account_id)], "user_id": None},
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["encrypted_blobs"] == []

    @pytest.mark.unit
    async def test_export_requires_service_token(
        self, client: AsyncClient, test_account_id: uuid.UUID
    ) -> None:
        """Sans token de service, l'accès est refusé (403)."""
        resp = await client.post(
            "/api/v1/internal/export",
            json={"account_ids": [str(test_account_id)]},
        )
        assert resp.status_code == 403
