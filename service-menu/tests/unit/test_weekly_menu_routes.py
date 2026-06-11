"""Tests unitaires des routes WeeklyMenu (via TestClient ASGI)."""

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

TEST_USER_ID = "test-user-uuid-1234"
TEST_ACCOUNT_ID = "test-account-uuid-1234"


def _make_menu_response(menu_id: int = 1, slug: str = "menu-test") -> dict:
    return {
        "id": menu_id,
        "slug": slug,
        "user_id": TEST_USER_ID,
        "account_id": TEST_ACCOUNT_ID,
        "nb_persons": 2,
        "caloric_target": None,
        "start_date": str(date(2026, 6, 2)),
        "exclusions": [],
        "free_tags": {},
        "notes": None,
        "rating": None,
        "created_at": "2026-06-01T10:00:00",
        "updated_at": "2026-06-01T10:00:00",
        "slots": [],
    }


@pytest.fixture
async def client():
    from nutri_shared.core.context import AccessContext

    from app.main import app
    from app.db.session import get_session
    from app.core.deps import (
        get_read_account_id,
        get_write_account_id,
        get_write_context,
    )

    session = AsyncMock()

    async def _override_session():
        yield session

    app.dependency_overrides[get_session] = _override_session
    app.dependency_overrides[get_read_account_id] = lambda: TEST_ACCOUNT_ID
    app.dependency_overrides[get_write_account_id] = lambda: TEST_ACCOUNT_ID
    app.dependency_overrides[get_write_context] = lambda: AccessContext(
        sub=TEST_USER_ID,
        account_id=TEST_ACCOUNT_ID,
        scopes=frozenset({"plan:read", "plan:write"}),
        user_admin=False,
        capabilities={},
    )

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac

    app.dependency_overrides.clear()


class TestWeeklyMenuRoutes:
    @pytest.mark.unit
    async def test_create_menu_returns_201(self, client: AsyncClient):
        """POST /weekly-menus retourne 201 avec le menu créé."""
        menu = _make_menu_response()
        with patch(
            "app.repositories.menu_service.create_menu",
            new=AsyncMock(return_value=MagicMock(**menu)),
        ):
            resp = await client.post(
                "/api/v1/menus",
                json={"start_date": "2026-06-02", "nb_persons": 2, "slots": []},
            )
        assert resp.status_code == 201

    @pytest.mark.unit
    async def test_list_menus_returns_200(self, client: AsyncClient):
        """GET /weekly-menus retourne 200 avec la liste des menus."""
        with patch(
            "app.repositories.menu_service.get_menu_by_account",
            new=AsyncMock(return_value=[]),
        ):
            resp = await client.get("/api/v1/menus")
        assert resp.status_code == 200
        assert resp.json() == []

    @pytest.mark.unit
    async def test_get_menu_returns_404_when_not_found(self, client: AsyncClient):
        """GET /weekly-menus/{id} retourne 404 si le menu est introuvable."""
        with patch(
            "app.repositories.menu_service.get_menu", new=AsyncMock(return_value=None)
        ):
            resp = await client.get("/api/v1/menus/999")
        assert resp.status_code == 404

    @pytest.mark.unit
    async def test_get_menu_returns_403_for_other_user(self, client: AsyncClient):
        """GET /weekly-menus/{id} retourne 403 si le menu appartient à un autre compte."""
        menu = MagicMock()
        menu.account_id = "other-account-id"
        menu.id = 1
        with patch(
            "app.repositories.menu_service.get_menu", new=AsyncMock(return_value=menu)
        ):
            resp = await client.get("/api/v1/menus/1")
        assert resp.status_code == 403

    @pytest.mark.unit
    async def test_delete_menu_returns_404_when_not_found(self, client: AsyncClient):
        """DELETE /weekly-menus/{id} retourne 404 si le menu est introuvable."""
        with patch(
            "app.repositories.menu_service.get_menu", new=AsyncMock(return_value=None)
        ):
            resp = await client.delete("/api/v1/menus/999")
        assert resp.status_code == 404

    @pytest.mark.unit
    async def test_update_menu_returns_404_when_not_found(self, client: AsyncClient):
        """PUT /weekly-menus/{id} retourne 404 si le menu est introuvable."""
        with patch(
            "app.repositories.menu_service.get_menu", new=AsyncMock(return_value=None)
        ):
            resp = await client.put(
                "/api/v1/menus/999",
                json={"nb_persons": 3},
            )
        assert resp.status_code == 404
