"""Tests routes sources — comportement spécifique Instagram."""

import uuid
from unittest.mock import MagicMock, patch

import pytest


@pytest.mark.anyio
async def test_create_instagram_source_triggers_initial_crawl(client):
    mock_task = MagicMock()
    mock_task.id = str(uuid.uuid4())

    with patch("app.api.routes.sources.crawl_instagram") as mock_crawl:
        mock_crawl.delay.return_value = mock_task
        resp = await client.post(
            "/api/v1/crawler/sources",
            json={"type": "instagram", "account": "@testchef", "frequency_hours": 24},
        )

    assert resp.status_code == 201
    mock_crawl.delay.assert_called_once()
    # Le @ est stripped par le schema avant stockage
    assert mock_crawl.delay.call_args[0][1] == "testchef"


@pytest.mark.anyio
async def test_create_instagram_source_stores_normalized_account(client):
    with patch("app.api.routes.sources.crawl_instagram"):
        resp = await client.post(
            "/api/v1/crawler/sources",
            json={"type": "instagram", "account": "@chef_paul"},
        )
    assert resp.status_code == 201
    assert resp.json()["url"] == "chef_paul"


@pytest.mark.anyio
async def test_create_instagram_source_rejects_empty_account(client):
    resp = await client.post(
        "/api/v1/crawler/sources",
        json={"type": "instagram", "account": "@"},
    )
    assert resp.status_code == 422


@pytest.mark.anyio
async def test_create_web_source_does_not_trigger_instagram_crawl(client):
    with patch("app.api.routes.sources.crawl_instagram") as mock_instagram:
        resp = await client.post(
            "/api/v1/crawler/sources",
            json={"type": "web", "url": "https://example.com/recipe"},
        )
    assert resp.status_code == 201
    mock_instagram.delay.assert_not_called()


@pytest.mark.anyio
async def test_create_web_source_rejects_invalid_url(client):
    resp = await client.post(
        "/api/v1/crawler/sources",
        json={"type": "web", "url": "not-a-url"},
    )
    assert resp.status_code == 422


@pytest.mark.anyio
async def test_trigger_crawl_instagram_returns_202_with_task_id(client):
    with patch("app.api.routes.sources.crawl_instagram") as mock_crawl:
        mock_crawl.delay.return_value = MagicMock(id="task-for-manual")
        create_resp = await client.post(
            "/api/v1/crawler/sources",
            json={"type": "instagram", "account": "@chefalain"},
        )
        source_id = create_resp.json()["id"]
        resp = await client.post(f"/api/v1/crawler/sources/{source_id}/crawl")

    assert resp.status_code == 202
    data = resp.json()
    assert data["task_id"] == "task-for-manual"
    assert data["source_id"] == source_id


@pytest.mark.anyio
async def test_create_youtube_source_rejected_by_schema(client):
    resp = await client.post(
        "/api/v1/crawler/sources",
        json={"type": "youtube", "url": "https://youtube.com/@chef"},
    )
    assert resp.status_code == 422


@pytest.mark.anyio
async def test_trigger_crawl_unknown_source_returns_404(client):
    resp = await client.post(f"/api/v1/crawler/sources/{uuid.uuid4()}/crawl")
    assert resp.status_code == 404
