import uuid

import pytest
from httpx import AsyncClient

from app.repositories.macro_error_repository import MacroErrorRepository
from tests.conftest import TEST_ACCOUNT_ID

USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")
OTHER_USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000002")


class TestStatsRoute:
    @pytest.mark.unit
    async def test_stats_returns_correct_counts(self, client: AsyncClient, db_session):
        """GET /users/{id}/stats → counts corrects depuis la DB."""
        repo = MacroErrorRepository(db_session)
        acc = TEST_ACCOUNT_ID
        e1 = await repo.create(user_id=USER_ID, raw_ingredient="err1", account_id=acc)
        e2 = await repo.create(user_id=USER_ID, raw_ingredient="err2", account_id=acc)
        await repo.create(user_id=USER_ID, raw_ingredient="err3", account_id=acc)
        await repo.resolve(e1, resolved_name="ok")
        await repo.resolve(e2, resolved_name="ok2", calories=50.0)

        resp = await client.get(f"/api/v1/users/{USER_ID}/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert data["user_slug"] == str(USER_ID)
        assert data["period"] == "last_30_days"
        assert data["macro_errors_pending"] == 1
        assert data["macro_errors_resolved"] == 2

    @pytest.mark.unit
    async def test_stats_empty_user_returns_zeros(
        self, client: AsyncClient, db_session
    ):
        """User sans données → counts à 0."""
        resp = await client.get(f"/api/v1/users/{USER_ID}/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert data["macro_errors_pending"] == 0
        assert data["macro_errors_resolved"] == 0
        assert data["recipes_analysed"] == 0

    @pytest.mark.unit
    async def test_stats_path_user_slug_is_informational(
        self, client: AsyncClient, db_session
    ):
        """Multicomptes : les stats sont bornées au compte actif du token, pas au
        user_slug du chemin (conservé pour compat d'API)."""
        resp = await client.get(f"/api/v1/users/{OTHER_USER_ID}/stats")
        assert resp.status_code == 200
        assert resp.json()["macro_errors_pending"] == 0

    @pytest.mark.unit
    async def test_stats_avg_daily_present(self, client: AsyncClient, db_session):
        """avg_daily contient les 4 champs macros."""
        resp = await client.get(f"/api/v1/users/{USER_ID}/stats")
        assert resp.status_code == 200
        avg = resp.json()["avg_daily"]
        assert "calories" in avg
        assert "proteines" in avg
        assert "glucides" in avg
        assert "lipides" in avg
