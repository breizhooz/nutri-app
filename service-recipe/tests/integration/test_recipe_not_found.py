import pytest

BASE = "/api/v1/recipe"


@pytest.mark.asyncio
@pytest.mark.integration
async def test_update_nonexistent_recipe_returns_404(override_db, http_client):
    override_db.get.return_value = None

    async with http_client as client:
        response = await client.put(f"{BASE}/id/9999", json={"title": "X"})

    assert response.status_code == 404


@pytest.mark.asyncio
@pytest.mark.integration
async def test_delete_nonexistent_recipe_returns_404(override_db, http_client):
    override_db.get.return_value = None

    async with http_client as client:
        response = await client.delete(f"{BASE}/id/9999")

    assert response.status_code == 404
