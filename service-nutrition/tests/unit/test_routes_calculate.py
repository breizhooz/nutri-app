import uuid
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.services.extraction_service import ExtractionResult, FailedIngredient, ResolvedIngredient
from app.services.lookup_service import LookupResult

USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")


def _lookup() -> LookupResult:
    return LookupResult(
        slug="farine-sarrasin", nom_fr="Farine de sarrasin",
        calories=340.0, proteines=13.0, glucides=71.0, lipides=3.0,
        fibres=None, score=8.0,
    )


def _ok_result() -> ExtractionResult:
    return ExtractionResult(
        resolved=[ResolvedIngredient(raw_text="200g de farine", matched=_lookup(), grammes=200.0)],
        failed=[],
    )


def _err_result() -> ExtractionResult:
    return ExtractionResult(
        resolved=[ResolvedIngredient(raw_text="200g de farine", matched=_lookup(), grammes=200.0)],
        failed=[FailedIngredient(raw_text="gochujank", macro_error_slug="gochujank-err", suggested="gochujang")],
    )


class TestCalculateRoute:
    @pytest.mark.unit
    async def test_requires_service_token(self, client: AsyncClient):
        """JWT user → 403."""
        resp = await client.post("/api/v1/calculate", json={
            "recipe_slug": "test", "user_id": str(USER_ID),
            "ingredients": [{"raw_text": "200g farine"}],
        })
        assert resp.status_code == 403

    @pytest.mark.unit
    async def test_no_auth_returns_403(self):
        """Sans auth → 403."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.post("/api/v1/calculate", json={
                "recipe_slug": "test", "user_id": str(USER_ID),
                "ingredients": [{"raw_text": "100g sucre"}],
            })
        assert resp.status_code == 403

    @pytest.mark.unit
    async def test_invalid_user_id_returns_422(self, service_client: AsyncClient):
        """user_id non UUID → 422."""
        resp = await service_client.post("/api/v1/calculate", json={
            "recipe_slug": "test", "user_id": "jean-dupont",
            "ingredients": [{"raw_text": "100g sucre"}],
        })
        assert resp.status_code == 422

    @pytest.mark.unit
    async def test_empty_ingredients_returns_422(self, service_client: AsyncClient):
        """Liste vide → 422."""
        resp = await service_client.post("/api/v1/calculate", json={
            "recipe_slug": "test", "user_id": str(USER_ID), "ingredients": [],
        })
        assert resp.status_code == 422

    @pytest.mark.unit
    async def test_success_returns_macros(self, service_client: AsyncClient):
        """Ingrédients résolus → 200 avec macros correctes."""
        with patch("app.api.routes.calculate.ExtractionService") as M:
            M.return_value.process = AsyncMock(return_value=_ok_result())
            resp = await service_client.post("/api/v1/calculate", json={
                "recipe_slug": "poulet-tikka", "servings": 4,
                "user_id": str(USER_ID),
                "ingredients": [{"raw_text": "200g de farine de sarrasin"}],
            })

        assert resp.status_code == 200
        data = resp.json()
        assert data["recipe_slug"] == "poulet-tikka"
        assert data["servings"] == 4
        assert data["total"]["calories"] == pytest.approx(680.0)
        assert data["per_serving"]["calories"] == pytest.approx(170.0)
        assert len(data["resolved"]) == 1
        assert data["errors"] == []

    @pytest.mark.unit
    async def test_with_errors_in_response(self, service_client: AsyncClient):
        """Ingrédients non résolus → errors[] renseigné."""
        with patch("app.api.routes.calculate.ExtractionService") as M:
            M.return_value.process = AsyncMock(return_value=_err_result())
            resp = await service_client.post("/api/v1/calculate", json={
                "recipe_slug": "test", "servings": 1, "user_id": str(USER_ID),
                "ingredients": [{"raw_text": "200g farine"}, {"raw_text": "gochujank"}],
            })

        assert resp.status_code == 200
        data = resp.json()
        assert len(data["errors"]) == 1
        assert data["errors"][0]["slug"] == "gochujank-err"
        assert data["errors"][0]["suggested"] == "gochujang"

    @pytest.mark.unit
    async def test_all_unresolved_zero_macros(self, service_client: AsyncClient):
        """Tout en erreur → macros à zéro."""
        all_failed = ExtractionResult(
            resolved=[],
            failed=[FailedIngredient(raw_text="x", macro_error_slug="x-err", suggested=None)],
        )
        with patch("app.api.routes.calculate.ExtractionService") as M:
            M.return_value.process = AsyncMock(return_value=all_failed)
            resp = await service_client.post("/api/v1/calculate", json={
                "recipe_slug": "test", "servings": 1, "user_id": str(USER_ID),
                "ingredients": [{"raw_text": "x"}],
            })

        assert resp.status_code == 200
        data = resp.json()
        assert data["total"]["calories"] == pytest.approx(0.0)
        assert data["resolved"] == []