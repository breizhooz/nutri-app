import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from unittest.mock import patch

from app.core.deps import get_token_payload
from app.main import app
from app.models.crawl_source import CrawlSource
from app.models.enums import CrawlType
from tests.unit.conftest import TEST_USER_ID


@pytest.mark.asyncio
async def test_oneshot_forbidden_without_web_right(client: AsyncClient):
    """Sans droit crawl.web, le one-shot doit être refusé (403)."""

    async def _no_rights() -> dict:
        return {
            "sub": str(TEST_USER_ID),
            "type": "access",
            "user_admin": False,
            "user_right": {"crawl": {"instagram": False, "web": False}},
        }

    app.dependency_overrides[get_token_payload] = _no_rights
    response = await client.post(
        "/api/v1/crawler/sources/oneshot", json={"url": "https://example.com"}
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_oneshot_web_routes_to_crawl_url(client: AsyncClient):
    with patch("app.api.routes.sources.crawl_url") as mock_url, patch(
        "app.api.routes.sources.crawl_instagram_post"
    ) as mock_post:
        resp = await client.post(
            "/api/v1/crawler/sources/oneshot", json={"url": "https://blog.com/curry"}
        )
    assert resp.status_code == 202
    assert resp.json()["type"] == "web"
    mock_url.delay.assert_called_once()
    mock_post.delay.assert_not_called()


@pytest.mark.asyncio
async def test_oneshot_instagram_link_routes_to_single_post(client: AsyncClient):
    with patch("app.api.routes.sources.crawl_url") as mock_url, patch(
        "app.api.routes.sources.crawl_instagram_post"
    ) as mock_post:
        resp = await client.post(
            "/api/v1/crawler/sources/oneshot",
            json={"url": "https://www.instagram.com/p/Cabc123/"},
        )
    assert resp.status_code == 202
    assert resp.json()["type"] == "instagram"
    mock_post.delay.assert_called_once()
    assert mock_post.delay.call_args[0][0] == "Cabc123"
    mock_url.delay.assert_not_called()


@pytest.mark.asyncio
async def test_oneshot_instagram_link_forbidden_without_uniq_link_insta(
    client: AsyncClient,
):
    async def _only_web() -> dict:
        return {
            "sub": str(TEST_USER_ID),
            "type": "access",
            "user_admin": False,
            "user_right": {"uniq_link": {"instagram": False, "web": True}},
        }

    app.dependency_overrides[get_token_payload] = _only_web
    resp = await client.post(
        "/api/v1/crawler/sources/oneshot",
        json={"url": "https://www.instagram.com/p/Cabc123/"},
    )
    app.dependency_overrides.pop(get_token_payload, None)
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_create_source(client: AsyncClient):
    response = await client.post(
        "/api/v1/crawler/sources",
        json={
            "type": CrawlType.WEB.value,
            "url": "https://example.com",
            "frequency_hours": 24,
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["url"] == "https://example.com"
    assert data["type"] == CrawlType.WEB.value
    assert data["actif"] is True


@pytest.mark.asyncio
async def test_list_sources_empty(client: AsyncClient):
    response = await client.get("/api/v1/crawler/sources")
    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.asyncio
async def test_list_sources_after_create(client: AsyncClient):
    await client.post(
        "/api/v1/crawler/sources",
        json={"type": CrawlType.WEB.value, "url": "https://a.com"},
    )
    with patch("app.api.routes.sources.crawl_instagram"):
        await client.post(
            "/api/v1/crawler/sources",
            json={"type": CrawlType.INSTAGRAM.value, "account": "@compte"},
        )
    response = await client.get("/api/v1/crawler/sources")
    assert response.status_code == 200
    assert len(response.json()) == 2


@pytest.mark.asyncio
async def test_get_source(client: AsyncClient):
    create = await client.post(
        "/api/v1/crawler/sources",
        json={"type": CrawlType.WEB.value, "url": "https://b.com"},
    )
    source_id = create.json()["id"]
    response = await client.get(f"/api/v1/crawler/sources/{source_id}")
    assert response.status_code == 200
    assert response.json()["id"] == source_id


@pytest.mark.asyncio
async def test_get_source_not_found(client: AsyncClient):
    response = await client.get(
        "/api/v1/crawler/sources/00000000-0000-0000-0000-000000000099"
    )
    assert response.status_code == 404
    assert response.json()["error"]["message"] == "Source introuvable."


@pytest.mark.asyncio
async def test_update_source(client: AsyncClient):
    create = await client.post(
        "/api/v1/crawler/sources",
        json={"type": CrawlType.WEB.value, "url": "https://c.com"},
    )
    source_id = create.json()["id"]
    response = await client.patch(
        f"/api/v1/crawler/sources/{source_id}", json={"actif": False}
    )
    assert response.status_code == 200
    assert response.json()["actif"] is False


@pytest.mark.asyncio
async def test_update_source_not_found(client: AsyncClient):
    response = await client.patch(
        "/api/v1/crawler/sources/00000000-0000-0000-0000-000000000099",
        json={"actif": False},
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_delete_source(client: AsyncClient):
    create = await client.post(
        "/api/v1/crawler/sources",
        json={"type": CrawlType.WEB.value, "url": "https://d.com"},
    )
    source_id = create.json()["id"]
    response = await client.delete(f"/api/v1/crawler/sources/{source_id}")
    assert response.status_code == 204
    get = await client.get(f"/api/v1/crawler/sources/{source_id}")
    assert get.status_code == 404


@pytest.mark.asyncio
async def test_delete_source_not_found(client: AsyncClient):
    response = await client.delete(
        "/api/v1/crawler/sources/00000000-0000-0000-0000-000000000099"
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_trigger_crawl(client: AsyncClient):
    create = await client.post(
        "/api/v1/crawler/sources",
        json={"type": CrawlType.WEB.value, "url": "https://e.com"},
    )
    source_id = create.json()["id"]
    with patch("app.api.routes.sources.crawl_url") as mock_task:
        mock_task.delay.return_value.id = "fake-task-id"
        response = await client.post(f"/api/v1/crawler/sources/{source_id}/crawl")
    assert response.status_code == 202
    assert response.json()["detail"] == "Crawl déclenché, en attente de traitement."
    assert response.json()["task_id"] == "fake-task-id"
    mock_task.delay.assert_called_once()


@pytest.mark.asyncio
async def test_trigger_crawl_not_found(client: AsyncClient):
    response = await client.post(
        "/api/v1/crawler/sources/00000000-0000-0000-0000-000000000099/crawl"
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_health(client: AsyncClient):
    response = await client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_trigger_crawl_unsupported_type(
    client: AsyncClient, db_session: AsyncSession
):
    source = CrawlSource(
        user_id=TEST_USER_ID, type=CrawlType.YOUTUBE, url="https://youtube.com/@chef"
    )
    db_session.add(source)
    await db_session.commit()
    response = await client.post(f"/api/v1/crawler/sources/{source.id}/crawl")
    assert response.status_code == 400
    assert (
        response.json()["error"]["message"]
        == "Ce type de source n'est pas encore pris en charge."
    )
