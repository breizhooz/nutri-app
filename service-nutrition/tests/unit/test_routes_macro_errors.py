import uuid

import pytest
from httpx import AsyncClient

from app.repositories.macro_error_repository import MacroErrorRepository

USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")
OTHER_USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000002")


async def _create_error(session, raw="gochujank", user_id=USER_ID):
    return await MacroErrorRepository(session).create(
        user_id=user_id, raw_ingredient=raw
    )


class TestMacroErrorsRoutes:
    @pytest.mark.unit
    async def test_list_macro_errors_for_current_user(self, client: AsyncClient, db_session):
        """GET /users/{user_id}/macro-errors → liste des erreurs du user."""
        await _create_error(db_session, "gochujank")
        await _create_error(db_session, "autre-truc")
        resp = await client.get(f"/api/v1/users/{USER_ID}/macro-errors")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2
        assert all(e["user_id"] == str(USER_ID) for e in data)

    @pytest.mark.unit
    async def test_list_macro_errors_empty_for_new_user(self, client: AsyncClient, db_session):
        """User sans erreurs → liste vide."""
        resp = await client.get(f"/api/v1/users/{USER_ID}/macro-errors")
        assert resp.status_code == 200
        assert resp.json() == []

    @pytest.mark.unit
    async def test_list_macro_errors_forbidden_for_other_user(
        self, client: AsyncClient, db_session
    ):
        """GET avec autre user_id → 403."""
        resp = await client.get(f"/api/v1/users/{OTHER_USER_ID}/macro-errors")
        assert resp.status_code == 403

    @pytest.mark.unit
    async def test_list_macro_errors_invalid_uuid_returns_422(
        self, client: AsyncClient, db_session
    ):
        """user_slug non UUID → 422."""
        resp = await client.get("/api/v1/users/jean-dupont/macro-errors")
        assert resp.status_code == 422

    @pytest.mark.unit
    async def test_patch_resolve_with_name_only(self, client: AsyncClient, db_session):
        """PATCH avec resolved_name seul → status=resolved."""
        error = await _create_error(db_session)
        resp = await client.patch(
            f"/api/v1/macro-errors/{error.slug}",
            json={"resolved_name": "gochujang"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "resolved"
        assert data["resolved_name"] == "gochujang"

    @pytest.mark.unit
    async def test_patch_resolve_with_manual_macros(self, client: AsyncClient, db_session):
        """PATCH avec macros manuelles → status=manual."""
        error = await _create_error(db_session)
        resp = await client.patch(
            f"/api/v1/macro-errors/{error.slug}",
            json={
                "resolved_name": "perso",
                "calories_manual": 100.0,
                "proteines_manual": 5.0,
                "glucides_manual": 15.0,
                "lipides_manual": 3.0,
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "manual"
        assert data["calories_manual"] == pytest.approx(100.0)

    @pytest.mark.unit
    async def test_patch_not_found_returns_404(self, client: AsyncClient, db_session):
        """PATCH slug inexistant → 404."""
        resp = await client.patch(
            "/api/v1/macro-errors/slug-inexistant",
            json={"resolved_name": "test"},
        )
        assert resp.status_code == 404

    @pytest.mark.unit
    async def test_patch_forbidden_for_other_user(self, client: AsyncClient, db_session):
        """PATCH d'un error appartenant à un autre user → 403."""
        error = await _create_error(db_session, user_id=OTHER_USER_ID)
        resp = await client.patch(
            f"/api/v1/macro-errors/{error.slug}",
            json={"resolved_name": "test"},
        )
        assert resp.status_code == 403

    @pytest.mark.unit
    async def test_patch_already_resolved_returns_409(self, client: AsyncClient, db_session):
        """PATCH d'une erreur déjà résolue → 409."""
        repo = MacroErrorRepository(db_session)
        error = await _create_error(db_session)
        await repo.resolve(error, resolved_name="gochujang")

        resp = await client.patch(
            f"/api/v1/macro-errors/{error.slug}",
            json={"resolved_name": "autre"},
        )
        assert resp.status_code == 409