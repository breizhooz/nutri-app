"""Tests routes sources — comportement spécifique Instagram (Phase 6)."""
import uuid
from unittest.mock import MagicMock, patch

import pytest


@pytest.mark.anyio
async def test_create_instagram_source_triggers_initial_crawl(client):
    """POST /sources type=instagram déclenche crawl_instagram.delay immédiatement."""
    mock_task = MagicMock()
    mock_task.id = str(uuid.uuid4())

    with patch("app.api.routes.sources.crawl_instagram") as mock_crawl:
        mock_crawl.delay.return_value = mock_task
        resp = await client.post(
            "/api/v1/crawler/sources",
            json={"type": "instagram", "url": "@testchef", "frequency_hours": 24},
        )

    assert resp.status_code == 201
    mock_crawl.delay.assert_called_once()
    # L'URL de la source est passée en second argument
    assert mock_crawl.delay.call_args[0][1] == "@testchef"


@pytest.mark.anyio
async def test_create_web_source_does_not_trigger_instagram_crawl(client):
    """POST /sources type=web ne doit PAS appeler crawl_instagram."""
    with patch("app.api.routes.sources.crawl_instagram") as mock_instagram:
        resp = await client.post(
            "/api/v1/crawler/sources",
            json={"type": "web", "url": "https://example.com/recipe"},
        )

    assert resp.status_code == 201
    mock_instagram.delay.assert_not_called()


@pytest.mark.anyio
async def test_trigger_crawl_instagram_returns_202_with_task_id(client):
    """POST /sources/{id}/crawl type=instagram → 202 + task_id dans la réponse."""
    with patch("app.api.routes.sources.crawl_instagram") as mock_crawl:
        mock_crawl.delay.return_value = MagicMock(id="task-for-manual")
        # Création de la source (déclenche le crawl initial)
        create_resp = await client.post(
            "/api/v1/crawler/sources",
            json={"type": "instagram", "url": "@chefalain"},
        )
        source_id = create_resp.json()["id"]

        # Crawl manuel
        resp = await client.post(f"/api/v1/crawler/sources/{source_id}/crawl")

    assert resp.status_code == 202
    data = resp.json()
    assert data["task_id"] == "task-for-manual"
    assert data["source_id"] == source_id


@pytest.mark.anyio
async def test_trigger_crawl_youtube_returns_400(client):
    """POST /sources/{id}/crawl type=youtube (non supporté) → 400."""
    # Création d'une source youtube
    create_resp = await client.post(
        "/api/v1/crawler/sources",
        json={"type": "youtube", "url": "https://youtube.com/@chef"},
    )
    assert create_resp.status_code == 201
    source_id = create_resp.json()["id"]

    resp = await client.post(f"/api/v1/crawler/sources/{source_id}/crawl")
    assert resp.status_code == 400


@pytest.mark.anyio
async def test_trigger_crawl_unknown_source_returns_404(client):
    """POST /sources/{id}/crawl avec id inexistant → 404."""
    resp = await client.post(f"/api/v1/crawler/sources/{uuid.uuid4()}/crawl")
    assert resp.status_code == 404
