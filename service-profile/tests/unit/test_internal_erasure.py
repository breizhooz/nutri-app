"""Tests de l'endpoint interne d'effacement RGPD (art. 17).

Depuis la bascule E2E zero-knowledge, l'effacement purge les blobs chiffrés du
compte (table opaque ``encrypted_blobs``) — il n'y a plus de données en clair.
"""

import base64
import os
import uuid

import pytest
from httpx import AsyncClient

_B64 = base64.b64encode(bytes(range(64))).decode()


def _service_headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {os.environ['SERVICE_PROFILE_TOKEN']}"}


async def _seed_blob(client: AsyncClient, ref_key: str = "default") -> None:
    resp = await client.put(
        f"/api/v1/profiles/me/blobs/health/{ref_key}", json={"ciphertext": _B64}
    )
    assert resp.status_code == 200


class TestInternalErasure:
    """POST /api/v1/internal/erasure."""

    @pytest.mark.unit
    async def test_erasure_removes_encrypted_blobs(
        self,
        client: AsyncClient,
        test_account_id: uuid.UUID,
        test_user_id: uuid.UUID,
    ) -> None:
        """L'effacement supprime tous les blobs chiffrés du compte."""
        await _seed_blob(client, "default")
        await _seed_blob(client, "snapshot")

        resp = await client.post(
            "/api/v1/internal/erasure",
            headers=_service_headers(),
            json={"account_ids": [str(test_account_id)], "user_id": str(test_user_id)},
        )
        assert resp.status_code == 200
        assert resp.json()["deleted"] == 2

        # Les blobs n'existent plus.
        assert (
            await client.get("/api/v1/profiles/me/blobs/health/default")
        ).status_code == 404

    @pytest.mark.unit
    async def test_erasure_is_idempotent(
        self, client: AsyncClient, test_account_id: uuid.UUID
    ) -> None:
        """Un second appel ne supprime rien et renvoie 200/deleted=0."""
        await _seed_blob(client)
        body = {"account_ids": [str(test_account_id)], "user_id": None}

        first = await client.post(
            "/api/v1/internal/erasure", headers=_service_headers(), json=body
        )
        assert first.json()["deleted"] == 1

        second = await client.post(
            "/api/v1/internal/erasure", headers=_service_headers(), json=body
        )
        assert second.status_code == 200
        assert second.json()["deleted"] == 0

    @pytest.mark.unit
    async def test_erasure_requires_service_token(
        self, client: AsyncClient, test_account_id: uuid.UUID
    ) -> None:
        """Sans token de service, l'accès est refusé (403)."""
        resp = await client.post(
            "/api/v1/internal/erasure",
            json={"account_ids": [str(test_account_id)]},
        )
        assert resp.status_code == 403
