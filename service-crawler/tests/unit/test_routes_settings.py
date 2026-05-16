import pytest
from httpx import AsyncClient

from app.services.web_service import WebService


@pytest.mark.asyncio
async def test_get_settings_returns_current_threshold(client: AsyncClient):
    response = await client.get("/api/v1/crawler/settings")
    assert response.status_code == 200
    data = response.json()
    assert "js_detection_threshold" in data
    assert data["js_detection_threshold"] == WebService.get_js_threshold()


@pytest.mark.asyncio
async def test_update_settings_changes_threshold(client: AsyncClient):
    original = WebService.get_js_threshold()
    try:
        response = await client.patch("/api/v1/crawler/settings", json={"js_detection_threshold": 500})
        assert response.status_code == 200
        assert response.json()["js_detection_threshold"] == 500
        assert WebService.get_js_threshold() == 500
    finally:
        WebService.set_js_threshold(original)


@pytest.mark.asyncio
async def test_update_settings_rejects_value_below_minimum(client: AsyncClient):
    response = await client.patch("/api/v1/crawler/settings", json={"js_detection_threshold": 10})
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_update_settings_rejects_value_above_maximum(client: AsyncClient):
    response = await client.patch("/api/v1/crawler/settings", json={"js_detection_threshold": 99999})
    assert response.status_code == 422