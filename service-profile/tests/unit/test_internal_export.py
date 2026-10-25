"""Tests de l'endpoint interne d'export RGPD (art. 20, portabilité).

L'export renvoie le profil nutritionnel du compte (préférences, exclusions, cibles).
"""

import os
import uuid

import pytest
from httpx import AsyncClient


def _service_headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {os.environ['SERVICE_PROFILE_TOKEN']}"}


class TestInternalExport:
    """POST /api/v1/internal/export."""

    @pytest.mark.unit
    async def test_export_returns_profile(
        self,
        client: AsyncClient,
        test_account_id: uuid.UUID,
        test_user_id: uuid.UUID,
    ) -> None:
        """L'export renvoie le profil du compte."""
        patch = await client.patch(
            "/api/v1/profiles/me",
            json={"diet_type": "vegan", "excluded_foods": ["arachide"]},
        )
        assert patch.status_code == 200

        resp = await client.post(
            "/api/v1/internal/export",
            headers=_service_headers(),
            json={"account_ids": [str(test_account_id)], "user_id": str(test_user_id)},
        )
        assert resp.status_code == 200
        profiles = resp.json()["data"]["nutrition_profiles"]
        assert len(profiles) == 1
        assert profiles[0]["account_id"] == str(test_account_id)
        assert profiles[0]["diet_type"] == "vegan"
        assert profiles[0]["excluded_foods"] == ["arachide"]

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
        assert resp.json()["data"]["nutrition_profiles"] == []

    @pytest.mark.unit
    async def test_export_requires_service_token(
        self, client: AsyncClient, test_account_id: uuid.UUID
    ) -> None:
        """Token de service invalide → accès refusé (403)."""
        resp = await client.post(
            "/api/v1/internal/export",
            headers={"Authorization": "Bearer invalid-token"},
            json={"account_ids": [str(test_account_id)]},
        )
        assert resp.status_code == 403
