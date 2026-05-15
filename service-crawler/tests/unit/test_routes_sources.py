import pytest
from httpx import AsyncClient

from app.models.enums import CrawlType


@pytest.mark.asyncio
async def test_create_source(client: AsyncClient):
    response = await client.post("/api/v1/crawler/sources", json={
        "type": CrawlType.WEB.value,
        "url": "https://example.com",
        "frequency_hours": 24,
    })
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
    await client.post("/api/v1/crawler/sources", json={"type": CrawlType.WEB.value, "url": "https://a.com"})
    await client.post("/api/v1/crawler/sources", json={"type": CrawlType.INSTAGRAM.value, "url": "@compte"})
    response = await client.get("/api/v1/crawler/sources")
    assert response.status_code == 200
    assert len(response.json()) == 2


@pytest.mark.asyncio
async def test_get_source(client: AsyncClient):
    create = await client.post("/api/v1/crawler/sources", json={"type": CrawlType.WEB.value, "url": "https://b.com"})
    source_id = create.json()["id"]
    response = await client.get(f"/api/v1/crawler/sources/{source_id}")
    assert response.status_code == 200
    assert response.json()["id"] == source_id


@pytest.mark.asyncio
async def test_get_source_not_found(client: AsyncClient):
    response = await client.get("/api/v1/crawler/sources/00000000-0000-0000-0000-000000000099")
    assert response.status_code == 404
    assert response.json()["detail"] == "Source introuvable."


@pytest.mark.asyncio
async def test_update_source(client: AsyncClient):
    create = await client.post("/api/v1/crawler/sources", json={"type": CrawlType.WEB.value, "url": "https://c.com"})
    source_id = create.json()["id"]
    response = await client.patch(f"/api/v1/crawler/sources/{source_id}", json={"actif": False})
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
    create = await client.post("/api/v1/crawler/sources", json={"type": CrawlType.WEB.value, "url": "https://d.com"})
    source_id = create.json()["id"]
    response = await client.delete(f"/api/v1/crawler/sources/{source_id}")
    assert response.status_code == 204
    get = await client.get(f"/api/v1/crawler/sources/{source_id}")
    assert get.status_code == 404


@pytest.mark.asyncio
async def test_delete_source_not_found(client: AsyncClient):
    response = await client.delete("/api/v1/crawler/sources/00000000-0000-0000-0000-000000000099")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_trigger_crawl(client: AsyncClient):
    create = await client.post("/api/v1/crawler/sources", json={"type": CrawlType.WEB.value, "url": "https://e.com"})
    source_id = create.json()["id"]
    response = await client.post(f"/api/v1/crawler/sources/{source_id}/crawl")
    assert response.status_code == 202
    assert "crawl_queued" in response.json()["detail"] or response.json()["detail"] == "Crawl déclenché, en attente de traitement."


@pytest.mark.asyncio
async def test_trigger_crawl_not_found(client: AsyncClient):
    response = await client.post("/api/v1/crawler/sources/00000000-0000-0000-0000-000000000099/crawl")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_health(client: AsyncClient):
    response = await client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"