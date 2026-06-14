"""Tests de l'endpoint interne d'effacement RGPD (art. 17)."""

import os
import uuid

import pytest
from httpx import AsyncClient


def _service_headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {os.environ['SERVICE_PROFILE_TOKEN']}"}


class TestInternalErasure:
    """POST /api/v1/internal/erasure."""

    @pytest.mark.unit
    async def test_erasure_removes_profile_and_children(
        self,
        client: AsyncClient,
        test_account_id: uuid.UUID,
        test_user_id: uuid.UUID,
    ) -> None:
        """L'effacement supprime le profil et ses données de santé."""
        await client.post("/api/v1/profiles", json={"height_cm": 175.0})
        await client.post(
            "/api/v1/profiles/me/conditions",
            json={"category": "metabolic", "condition_name": "Diabète type 2"},
        )

        resp = await client.post(
            "/api/v1/internal/erasure",
            headers=_service_headers(),
            json={"account_ids": [str(test_account_id)], "user_id": str(test_user_id)},
        )
        assert resp.status_code == 200
        assert resp.json()["deleted"] == 1

        # Le dossier n'existe plus → la résolution /me renvoie 404.
        assert (await client.get("/api/v1/profiles/me/injuries")).status_code == 404

    @pytest.mark.unit
    async def test_erasure_is_idempotent(
        self, client: AsyncClient, test_account_id: uuid.UUID
    ) -> None:
        """Un second appel ne supprime rien et renvoie 200/deleted=0."""
        await client.post("/api/v1/profiles", json={"height_cm": 180.0})
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
