"""Tests du profil nutritionnel (sans donnée corporelle ni médicale).

``client`` injecte le compte actif et neutralise le garde consentement ;
``raw_client`` + JWT forgés vérifient l'isolation par compte et le consentement.
"""

import os
import uuid

import jwt
import pytest
from httpx import AsyncClient

from tests.conftest import make_context_token

_URL = "/api/v1/profiles/me"
_RW = ["profile:read", "profile:write"]


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _service_headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {os.environ['SERVICE_PROFILE_TOKEN']}"}


class TestProfile:
    @pytest.mark.unit
    async def test_no_profile_returns_404(self, client: AsyncClient) -> None:
        assert (await client.get(_URL)).status_code == 404

    @pytest.mark.unit
    async def test_first_patch_creates_with_defaults(
        self, client: AsyncClient, test_account_id: uuid.UUID
    ) -> None:
        resp = await client.patch(_URL, json={"main_goal": "weight_loss"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["account_id"] == str(test_account_id)
        assert body["main_goal"] == "weight_loss"
        assert body["diet_type"] == "omnivore"
        assert body["excluded_foods"] == []
        assert body["nutrition_rules_enabled"] is True
        assert body["target_calories_kcal"] is None
        assert (await client.get(_URL)).json()["main_goal"] == "weight_loss"

    @pytest.mark.unit
    async def test_patch_is_partial(self, client: AsyncClient) -> None:
        await client.patch(_URL, json={"diet_type": "vegan", "meals_per_day": 3})
        resp = await client.patch(
            _URL,
            json={"target_calories_kcal": 2100, "target_proteins_g": 140},
        )
        body = resp.json()
        assert body["diet_type"] == "vegan"
        assert body["meals_per_day"] == 3
        assert body["target_calories_kcal"] == 2100
        assert body["target_proteins_g"] == 140

    @pytest.mark.unit
    async def test_optional_field_can_be_cleared(self, client: AsyncClient) -> None:
        await client.patch(_URL, json={"rules_override_calories": 1800})
        resp = await client.patch(_URL, json={"rules_override_calories": None})
        assert resp.json()["rules_override_calories"] is None

    @pytest.mark.unit
    @pytest.mark.parametrize(
        "field", ["weight_kg", "height_cm", "date_of_birth", "allergies"]
    )
    async def test_body_or_medical_fields_rejected(
        self, client: AsyncClient, field: str
    ) -> None:
        """Le corps reste sur l'appareil : tout champ inconnu est refusé."""
        resp = await client.patch(_URL, json={field: 80})
        assert resp.status_code == 422

    @pytest.mark.unit
    async def test_required_field_cannot_be_nulled(self, client: AsyncClient) -> None:
        await client.patch(_URL, json={"main_goal": "maintenance"})
        resp = await client.patch(_URL, json={"main_goal": None})
        assert resp.status_code == 422

    @pytest.mark.unit
    async def test_excluded_foods_cleaned_and_deduplicated(
        self, client: AsyncClient
    ) -> None:
        resp = await client.patch(
            _URL,
            json={"excluded_foods": ["  Arachide ", "arachide", "", "fruits  de mer"]},
        )
        assert resp.json()["excluded_foods"] == ["Arachide", "fruits de mer"]

    @pytest.mark.unit
    async def test_out_of_range_target_rejected(self, client: AsyncClient) -> None:
        resp = await client.patch(_URL, json={"target_calories_kcal": -5})
        assert resp.status_code == 422


class TestProfileAuthorization:
    @pytest.mark.unit
    async def test_profiles_are_isolated_by_account(
        self, raw_client: AsyncClient
    ) -> None:
        user = uuid.uuid4()
        acc_a, acc_b = uuid.uuid4(), uuid.uuid4()
        token_a = make_context_token(sub=user, account_id=acc_a, scopes=_RW)
        token_b = make_context_token(sub=user, account_id=acc_b, scopes=_RW)

        await raw_client.patch(
            _URL, json={"diet_type": "halal"}, headers=_auth(token_a)
        )
        assert (await raw_client.get(_URL, headers=_auth(token_b))).status_code == 404
        assert (await raw_client.get(_URL, headers=_auth(token_a))).json()[
            "diet_type"
        ] == "halal"

    @pytest.mark.unit
    async def test_write_requires_consent(self, raw_client: AsyncClient) -> None:
        token = make_context_token(
            sub=uuid.uuid4(), account_id=uuid.uuid4(), scopes=_RW
        )
        payload = jwt.decode(token, os.environ["JWT_SECRET"], algorithms=["HS256"])
        payload["health_consent"] = False
        no_consent = jwt.encode(payload, os.environ["JWT_SECRET"], algorithm="HS256")
        resp = await raw_client.patch(
            _URL, json={"diet_type": "vegan"}, headers=_auth(no_consent)
        )
        assert resp.status_code == 403

    @pytest.mark.unit
    async def test_write_requires_scope(self, raw_client: AsyncClient) -> None:
        token = make_context_token(
            sub=uuid.uuid4(), account_id=uuid.uuid4(), scopes=["profile:read"]
        )
        resp = await raw_client.patch(
            _URL, json={"diet_type": "vegan"}, headers=_auth(token)
        )
        assert resp.status_code == 403


class TestNutritionSummary:
    @pytest.mark.unit
    async def test_summary_for_menu_and_search(
        self,
        client: AsyncClient,
        service_client: AsyncClient,
        test_account_id: uuid.UUID,
    ) -> None:
        await client.patch(
            _URL,
            json={
                "main_goal": "muscle_gain",
                "diet_type": "vegetarian",
                "excluded_foods": ["arachide"],
                "target_calories_kcal": 2600,
                "target_proteins_g": 160,
                "target_carbs_g": 300,
                "target_fats_g": 80,
                "rules_variety_pct": 0.2,
            },
        )
        resp = await service_client.get(
            f"/api/v1/internal/accounts/{test_account_id}/nutrition-summary"
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["main_goal"] == "muscle_gain"
        assert body["diet_type"] == "vegetarian"
        assert body["excluded_foods"] == ["arachide"]
        assert body["targets"] == {
            "calories": 2600,
            "proteines": 160,
            "glucides": 300,
            "lipides": 80,
        }
        assert body["rules"]["enabled"] is True
        assert body["rules"]["variety_pct"] == 0.2

    @pytest.mark.unit
    async def test_summary_without_targets(
        self,
        client: AsyncClient,
        service_client: AsyncClient,
        test_account_id: uuid.UUID,
    ) -> None:
        await client.patch(_URL, json={"diet_type": "vegan"})
        resp = await service_client.get(
            f"/api/v1/internal/accounts/{test_account_id}/nutrition-summary"
        )
        assert resp.json()["targets"] is None

    @pytest.mark.unit
    async def test_summary_unknown_account_404(
        self, client: AsyncClient, service_client: AsyncClient
    ) -> None:
        """``client`` installe la session de test (base en mémoire)."""
        resp = await service_client.get(
            f"/api/v1/internal/accounts/{uuid.uuid4()}/nutrition-summary"
        )
        assert resp.status_code == 404

    @pytest.mark.unit
    async def test_summary_requires_service_token(self, client: AsyncClient) -> None:
        resp = await client.get(
            f"/api/v1/internal/accounts/{uuid.uuid4()}/nutrition-summary",
            headers={"Authorization": "Bearer invalid-token"},
        )
        assert resp.status_code == 403
