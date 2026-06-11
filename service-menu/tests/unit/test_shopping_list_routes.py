"""Tests unitaires des routes ShoppingList (via TestClient ASGI)."""

import os
from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("JWT_SECRET", "test-secret-key-for-testing-only")
os.environ.setdefault("JWT_ALGORITHM", "HS256")
os.environ.setdefault("SERVICE_RECIPE_URL", "http://service-recipe-test:8000")
os.environ.setdefault("ELASTICSEARCH_URL", "http://es-test:9200")
os.environ.setdefault("ELASTICSEARCH_INDEX_RECIPES", "recipes-test")

TEST_USER_ID = "test-user-uuid-5678"
TEST_ACCOUNT_ID = "test-account-uuid-5678"


@pytest.fixture
async def client():
    from app.main import app
    from app.db.session import get_session
    from app.core.deps import get_read_account_id
    from app.core.http_client import get_recipe_client

    session = AsyncMock()
    recipe_client = AsyncMock()

    async def _override_session():
        yield session

    async def _override_recipe_client():
        return recipe_client

    app.dependency_overrides[get_session] = _override_session
    app.dependency_overrides[get_read_account_id] = lambda: TEST_ACCOUNT_ID
    app.dependency_overrides[get_recipe_client] = _override_recipe_client

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac

    app.dependency_overrides.clear()


def _make_shopping_list():
    from app.schemas.shopping_list import ShoppingList

    return ShoppingList(
        menu_id=1,
        menu_slug="test-menu",
        nb_persons=2,
        start_date=date(2026, 6, 2),
        items=[],
    )


class TestShoppingListRoutes:
    @pytest.mark.unit
    async def test_get_shopping_list_returns_404_when_menu_not_found(
        self, client: AsyncClient
    ):
        """GET /weekly-menus/{id}/shopping-list retourne 404 si le menu est introuvable."""
        with patch(
            "app.api.routes.shopping_list.get_menu", new=AsyncMock(return_value=None)
        ):
            resp = await client.get("/api/v1/menus/999/shopping-list")
        assert resp.status_code == 404

    @pytest.mark.unit
    async def test_get_shopping_list_returns_403_for_other_user(
        self, client: AsyncClient
    ):
        """GET /shopping-list retourne 403 si le menu appartient à un autre utilisateur."""
        menu = MagicMock()
        menu.account_id = "other-account-id"
        with patch(
            "app.api.routes.shopping_list.get_menu", new=AsyncMock(return_value=menu)
        ):
            resp = await client.get("/api/v1/menus/1/shopping-list")
        assert resp.status_code == 403

    @pytest.mark.unit
    async def test_get_shopping_list_returns_200_for_owner(self, client: AsyncClient):
        """GET /shopping-list retourne 200 pour le propriétaire du menu."""
        menu = MagicMock()
        menu.account_id = TEST_ACCOUNT_ID
        sl = _make_shopping_list()
        with (
            patch(
                "app.api.routes.shopping_list.get_menu",
                new=AsyncMock(return_value=menu),
            ),
            patch(
                "app.api.routes.shopping_list.build_shopping_list",
                new=AsyncMock(return_value=sl),
            ),
        ):
            resp = await client.get("/api/v1/menus/1/shopping-list")
        assert resp.status_code == 200

    @pytest.mark.unit
    async def test_export_csv_returns_404_when_menu_not_found(
        self, client: AsyncClient
    ):
        """GET /shopping-list/export retourne 404 si le menu est introuvable."""
        with patch(
            "app.api.routes.shopping_list.get_menu", new=AsyncMock(return_value=None)
        ):
            resp = await client.get("/api/v1/menus/999/shopping-list/export?format=csv")
        assert resp.status_code == 404

    @pytest.mark.unit
    async def test_export_invalid_format_returns_422(self, client: AsyncClient):
        """GET /export avec un format invalide retourne 422."""
        resp = await client.get("/api/v1/menus/1/shopping-list/export?format=xlsx")
        assert resp.status_code == 422
