"""Tests de l'endpoint interne d'export RGPD (art. 20, portabilité)."""

import os
import uuid

import pytest
from httpx import AsyncClient


def _service_headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {os.environ['SERVICE_PROFILE_TOKEN']}"}


class TestInternalExport:
    """POST /api/v1/internal/export."""

    @pytest.mark.unit
    async def test_export_returns_profile_and_children(
        self,
        client: AsyncClient,
        test_account_id: uuid.UUID,
        test_user_id: uuid.UUID,
    ) -> None:
        """L'export renvoie le dossier et ses sous-ressources de santé."""
        await client.post("/api/v1/profiles", json={"height_cm": 175.0})
        await client.post(
            "/api/v1/profiles/me/conditions",
            json={"category": "metabolic", "condition_name": "Diabète type 2"},
        )

        resp = await client.post(
            "/api/v1/internal/export",
            headers=_service_headers(),
            json={"account_ids": [str(test_account_id)], "user_id": str(test_user_id)},
        )
        assert resp.status_code == 200
        profiles = resp.json()["data"]["profiles"]
        assert len(profiles) == 1
        assert profiles[0]["height_cm"] == 175.0
        conditions = profiles[0]["medical_conditions"]
        assert len(conditions) == 1
        assert conditions[0]["condition_name"] == "Diabète type 2"

    @pytest.mark.unit
    async def test_export_empty_when_no_profile(
        self, client: AsyncClient, test_account_id: uuid.UUID
    ) -> None:
        """Sans dossier, l'export renvoie une liste vide (200)."""
        resp = await client.post(
            "/api/v1/internal/export",
            headers=_service_headers(),
            json={"account_ids": [str(test_account_id)], "user_id": None},
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["profiles"] == []

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
