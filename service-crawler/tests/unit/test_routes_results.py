import uuid
import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch, MagicMock
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.models.enums import CrawlStatus, CrawlType


def _make_result(status=None, result_id=None):
    r = MagicMock()
    r.id = result_id or uuid.uuid4()
    r.source_id = None
    r.user_id = None
    r.type = CrawlType.WEB
    r.url_origin = "https://example.com"
    r.title = "Test"
    r.raw_content = "some content"
    r.images = []
    r.video_url = None
    r.status = status or CrawlStatus.WAITING
    r.validate_by = None
    r.validate_date = None
    r.created_at = r.created_at = datetime.now(timezone.utc)
    return r


@pytest.fixture
def mock_repo():
    return AsyncMock()


@pytest.fixture
async def results_client(mock_repo):
    with patch("app.api.routes.results.ResultRepository", return_value=mock_repo):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            yield c, mock_repo


@pytest.mark.asyncio
async def test_list_pending_empty(results_client):
    client, repo = results_client
    repo.list_pending.return_value = []
    response = await client.get("/api/v1/crawler/results")
    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.asyncio
async def test_list_pending_returns_results(results_client):
    client, repo = results_client
    repo.list_pending.return_value = [_make_result(), _make_result()]
    response = await client.get("/api/v1/crawler/results")
    assert response.status_code == 200
    assert len(response.json()) == 2


@pytest.mark.asyncio
async def test_get_result(results_client):
    client, repo = results_client
    r = _make_result()
    repo.get_by_id.return_value = r
    response = await client.get(f"/api/v1/crawler/results/{r.id}")
    assert response.status_code == 200
    assert response.json()["id"] == str(r.id)


@pytest.mark.asyncio
async def test_get_result_not_found(results_client):
    client, repo = results_client
    repo.get_by_id.return_value = None
    response = await client.get("/api/v1/crawler/results/00000000-0000-0000-0000-000000000099")
    assert response.status_code == 404
    assert response.json()["detail"] == "Résultat introuvable."


@pytest.mark.asyncio
async def test_update_result(results_client):
    client, repo = results_client
    r = _make_result()
    updated = _make_result(result_id=r.id)
    updated.title = "Nouveau titre"
    repo.get_by_id.return_value = r
    repo.update.return_value = updated
    response = await client.patch(f"/api/v1/crawler/results/{r.id}", json={"title": "Nouveau titre"})
    assert response.status_code == 200
    assert response.json()["title"] == "Nouveau titre"


@pytest.mark.asyncio
async def test_update_result_not_found(results_client):
    client, repo = results_client
    repo.get_by_id.return_value = None
    response = await client.patch(
        "/api/v1/crawler/results/00000000-0000-0000-0000-000000000099",
        json={"title": "X"},
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_validate_result(results_client):
    client, repo = results_client
    r = _make_result()
    validated = _make_result(result_id=r.id, status=CrawlStatus.VALID)
    validated.validate_by = uuid.UUID("00000000-0000-0000-0000-000000000001")
    repo.get_by_id.return_value = r
    repo.validate.return_value = validated
    response = await client.patch(f"/api/v1/crawler/results/{r.id}/validate")
    assert response.status_code == 200
    assert response.json()["status"] == CrawlStatus.VALID.value
    assert response.json()["validate_by"] is not None


@pytest.mark.asyncio
async def test_validate_result_not_found(results_client):
    client, repo = results_client
    repo.get_by_id.return_value = None
    response = await client.patch("/api/v1/crawler/results/00000000-0000-0000-0000-000000000099/validate")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_reject_result(results_client):
    client, repo = results_client
    r = _make_result()
    rejected = _make_result(result_id=r.id, status=CrawlStatus.REJECTED)
    repo.get_by_id.return_value = r
    repo.reject.return_value = rejected
    response = await client.patch(f"/api/v1/crawler/results/{r.id}/reject")
    assert response.status_code == 200
    assert response.json()["status"] == CrawlStatus.REJECTED.value


@pytest.mark.asyncio
async def test_reject_result_not_found(results_client):
    client, repo = results_client
    repo.get_by_id.return_value = None
    response = await client.patch("/api/v1/crawler/results/00000000-0000-0000-0000-000000000099/reject")
    assert response.status_code == 404