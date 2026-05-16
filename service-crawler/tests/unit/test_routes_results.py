import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException
from httpx import ASGITransport, AsyncClient

from app.api.routes.results import ResultServiceFactory
from app.main import app
from app.models.enums import CrawlStatus, CrawlType
from app.schemas.crawl_result import PaginatedCrawlResultResponse


class CrawlResultFactory:
    @staticmethod
    def make(
        result_id: uuid.UUID | None = None,
        status: CrawlStatus = CrawlStatus.WAITING,
    ) -> MagicMock:
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
        r.status = status
        r.validate_by = None
        r.validate_date = None
        r.created_at = datetime.now(timezone.utc)
        return r

    @staticmethod
    def make_paginated(
        items: list | None = None,
        total: int = 0,
        page: int = 1,
        page_size: int = 20,
    ) -> PaginatedCrawlResultResponse:
        pages = (total + page_size - 1) // page_size if total > 0 else 0
        return PaginatedCrawlResultResponse(
            items=items or [],
            total=total,
            page=page,
            page_size=page_size,
            pages=pages,
        )


@pytest.fixture
def mock_service() -> AsyncMock:
    return AsyncMock()


@pytest.fixture
async def results_client(mock_service: AsyncMock):
    app.dependency_overrides[ResultServiceFactory.inject] = lambda: mock_service
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c, mock_service
    app.dependency_overrides.clear()


class TestListResults:
    async def test_empty_returns_paginated_zero(self, results_client):
        client, service = results_client
        service.list_results.return_value = CrawlResultFactory.make_paginated()
        response = await client.get("/api/v1/crawler/results")
        assert response.status_code == 200
        body = response.json()
        assert body["total"] == 0
        assert body["items"] == []
        assert body["pages"] == 0

    async def test_returns_items_in_paginated_envelope(self, results_client):
        client, service = results_client
        items = [CrawlResultFactory.make(), CrawlResultFactory.make()]
        service.list_results.return_value = CrawlResultFactory.make_paginated(
            items=items, total=2
        )
        response = await client.get("/api/v1/crawler/results")
        assert response.status_code == 200
        assert response.json()["total"] == 2

    async def test_pagination_params_forwarded(self, results_client):
        client, service = results_client
        service.list_results.return_value = CrawlResultFactory.make_paginated(
            total=50, page=2, page_size=10
        )
        await client.get("/api/v1/crawler/results?page=2&page_size=10")
        params = service.list_results.call_args[0][0]
        assert params.page == 2
        assert params.page_size == 10

    async def test_status_filter_forwarded(self, results_client):
        client, service = results_client
        service.list_results.return_value = CrawlResultFactory.make_paginated()
        await client.get("/api/v1/crawler/results?status=valid")
        params = service.list_results.call_args[0][0]
        assert params.status == CrawlStatus.VALID

    async def test_page_size_above_max_returns_422(self, results_client):
        client, _ = results_client
        response = await client.get("/api/v1/crawler/results?page_size=200")
        assert response.status_code == 422

    async def test_page_zero_returns_422(self, results_client):
        client, _ = results_client
        response = await client.get("/api/v1/crawler/results?page=0")
        assert response.status_code == 422

    async def test_default_status_is_waiting(self, results_client):
        client, service = results_client
        service.list_results.return_value = CrawlResultFactory.make_paginated()
        await client.get("/api/v1/crawler/results")
        params = service.list_results.call_args[0][0]
        assert params.status == CrawlStatus.WAITING


class TestGetResult:
    async def test_found_returns_200(self, results_client):
        client, service = results_client
        r = CrawlResultFactory.make()
        service.get_result.return_value = r
        response = await client.get(f"/api/v1/crawler/results/{r.id}")
        assert response.status_code == 200
        assert response.json()["id"] == str(r.id)

    async def test_not_found_returns_404(self, results_client):
        client, service = results_client
        service.get_result.side_effect = HTTPException(
            status_code=404, detail="Résultat introuvable."
        )
        response = await client.get(
            "/api/v1/crawler/results/00000000-0000-0000-0000-000000000099"
        )
        assert response.status_code == 404
        assert response.json()["detail"] == "Résultat introuvable."


class TestUpdateResult:
    async def test_update_success_returns_200(self, results_client):
        client, service = results_client
        r = CrawlResultFactory.make()
        updated = CrawlResultFactory.make(result_id=r.id)
        updated.title = "Nouveau titre"
        service.update_result.return_value = updated
        response = await client.patch(
            f"/api/v1/crawler/results/{r.id}", json={"title": "Nouveau titre"}
        )
        assert response.status_code == 200
        assert response.json()["title"] == "Nouveau titre"

    async def test_not_found_returns_404(self, results_client):
        client, service = results_client
        service.update_result.side_effect = HTTPException(status_code=404, detail="Not found")
        response = await client.patch(
            "/api/v1/crawler/results/00000000-0000-0000-0000-000000000099",
            json={"title": "X"},
        )
        assert response.status_code == 404

    async def test_conflict_on_non_waiting_returns_409(self, results_client):
        client, service = results_client
        service.update_result.side_effect = HTTPException(status_code=409, detail="Conflict")
        r = CrawlResultFactory.make()
        response = await client.patch(
            f"/api/v1/crawler/results/{r.id}", json={"title": "X"}
        )
        assert response.status_code == 409


class TestValidateResult:
    async def test_validate_success_returns_200(self, results_client):
        client, service = results_client
        r = CrawlResultFactory.make()
        validated = CrawlResultFactory.make(result_id=r.id, status=CrawlStatus.VALID)
        validated.validate_by = uuid.UUID("00000000-0000-0000-0000-000000000001")
        service.validate_result.return_value = validated
        response = await client.patch(f"/api/v1/crawler/results/{r.id}/validate")
        assert response.status_code == 200
        assert response.json()["status"] == CrawlStatus.VALID.value
        assert response.json()["validate_by"] is not None

    async def test_not_found_returns_404(self, results_client):
        client, service = results_client
        service.validate_result.side_effect = HTTPException(status_code=404, detail="Not found")
        response = await client.patch(
            "/api/v1/crawler/results/00000000-0000-0000-0000-000000000099/validate"
        )
        assert response.status_code == 404

    async def test_already_validated_returns_409(self, results_client):
        client, service = results_client
        service.validate_result.side_effect = HTTPException(
            status_code=409, detail="Already validated"
        )
        r = CrawlResultFactory.make()
        response = await client.patch(f"/api/v1/crawler/results/{r.id}/validate")
        assert response.status_code == 409

    async def test_stub_user_id_passed_to_service(self, results_client):
        client, service = results_client
        r = CrawlResultFactory.make()
        validated = CrawlResultFactory.make(result_id=r.id, status=CrawlStatus.VALID)
        service.validate_result.return_value = validated
        await client.patch(f"/api/v1/crawler/results/{r.id}/validate")
        _, kwargs = service.validate_result.call_args
        assert kwargs["validated_by"] == uuid.UUID("00000000-0000-0000-0000-000000000001")


class TestRejectResult:
    async def test_reject_success_returns_200(self, results_client):
        client, service = results_client
        r = CrawlResultFactory.make()
        rejected = CrawlResultFactory.make(result_id=r.id, status=CrawlStatus.REJECTED)
        service.reject_result.return_value = rejected
        response = await client.patch(f"/api/v1/crawler/results/{r.id}/reject")
        assert response.status_code == 200
        assert response.json()["status"] == CrawlStatus.REJECTED.value

    async def test_not_found_returns_404(self, results_client):
        client, service = results_client
        service.reject_result.side_effect = HTTPException(status_code=404, detail="Not found")
        response = await client.patch(
            "/api/v1/crawler/results/00000000-0000-0000-0000-000000000099/reject"
        )
        assert response.status_code == 404

    async def test_conflict_returns_409(self, results_client):
        client, service = results_client
        service.reject_result.side_effect = HTTPException(status_code=409, detail="Conflict")
        r = CrawlResultFactory.make()
        response = await client.patch(f"/api/v1/crawler/results/{r.id}/reject")
        assert response.status_code == 409