"""Tests de l'endpoint interne d'effacement RGPD (art. 17).

L'effacement purge le profil nutritionnel du compte (``nutrition_profiles``).
"""

import os
import uuid

import pytest
from httpx import AsyncClient


def _service_headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {os.environ['SERVICE_PROFILE_TOKEN']}"}


async def _seed_profile(client: AsyncClient) -> None:
    resp = await client.patch("/api/v1/profiles/me", json={"main_goal": "weight_loss"})
    assert resp.status_code == 200


class TestInternalErasure:
    """POST /api/v1/internal/erasure."""

    @pytest.mark.unit
    async def test_erasure_removes_profile(
        self,
        client: AsyncClient,
        test_account_id: uuid.UUID,
        test_user_id: uuid.UUID,
    ) -> None:
        """L'effacement supprime le profil du compte."""
        await _seed_profile(client)

        resp = await client.post(
            "/api/v1/internal/erasure",
            headers=_service_headers(),
            json={"account_ids": [str(test_account_id)], "user_id": str(test_user_id)},
        )
        assert resp.status_code == 200
        assert resp.json()["deleted"] == 1

        # Le profil n'existe plus.
        assert (await client.get("/api/v1/profiles/me")).status_code == 404

    @pytest.mark.unit
    async def test_erasure_is_idempotent(
        self, client: AsyncClient, test_account_id: uuid.UUID
    ) -> None:
        """Un second appel ne supprime rien et renvoie 200/deleted=0."""
        await _seed_profile(client)
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
        """Token de service invalide → accès refusé (403)."""
        resp = await client.post(
            "/api/v1/internal/erasure",
            headers={"Authorization": "Bearer invalid-token"},
            json={"account_ids": [str(test_account_id)]},
        )
        assert resp.status_code == 403
