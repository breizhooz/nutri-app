import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException
from httpx import ASGITransport, AsyncClient

from app.api.routes.results import (
    GroqExtractorFactory,
    RecipeMapperFactory,
    ResultServiceFactory,
)
from app.core.deps import get_current_user_id
from app.main import app
from app.models.enums import CrawlStatus, CrawlType
from app.schemas.crawl_result import PaginatedCrawlResultResponse
from app.schemas.hydration import HydratedIngredient, RecipeHydrated

_STUB_USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")


@pytest.fixture
def mock_mapper() -> AsyncMock:
    return AsyncMock()


@pytest.fixture
def mock_extractor() -> AsyncMock:
    return AsyncMock()


@pytest.fixture
async def results_client(
    mock_service: AsyncMock, mock_mapper: AsyncMock, mock_extractor: AsyncMock
):
    app.dependency_overrides[ResultServiceFactory.inject] = lambda: mock_service
    app.dependency_overrides[RecipeMapperFactory.inject] = lambda: mock_mapper
    app.dependency_overrides[GroqExtractorFactory.inject] = lambda: mock_extractor
    app.dependency_overrides[get_current_user_id] = lambda: _STUB_USER_ID
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as c:
        yield c, mock_service
    app.dependency_overrides.clear()


class CrawlResultFactory:
    @staticmethod
    def make(
        result_id: uuid.UUID | None = None,
        status: CrawlStatus = CrawlStatus.WAITING,
    ) -> MagicMock:
        r = MagicMock()
        r.id = result_id or uuid.uuid4()
        r.source_id = None
        r.user_id = uuid.UUID("00000000-0000-0000-0000-000000000001")
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
        params = service.list_results.call_args.kwargs["params"]
        assert params.page == 2
        assert params.page_size == 10

    async def test_status_filter_forwarded(self, results_client):
        client, service = results_client
        service.list_results.return_value = CrawlResultFactory.make_paginated()
        await client.get("/api/v1/crawler/results?status=valid")
        params = service.list_results.call_args.kwargs["params"]
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
        params = service.list_results.call_args.kwargs["params"]
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
        assert response.json()["error"]["message"] == "Résultat introuvable."


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
        service.update_result.side_effect = HTTPException(
            status_code=404, detail="Not found"
        )
        response = await client.patch(
            "/api/v1/crawler/results/00000000-0000-0000-0000-000000000099",
            json={"title": "X"},
        )
        assert response.status_code == 404

    async def test_conflict_on_non_waiting_returns_409(self, results_client):
        client, service = results_client
        service.update_result.side_effect = HTTPException(
            status_code=409, detail="Conflict"
        )
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
        service.validate_result.side_effect = HTTPException(
            status_code=404, detail="Not found"
        )
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
        assert kwargs["validated_by"] == _STUB_USER_ID

    async def test_mapper_kwarg_passed_to_service(self, results_client):
        client, service = results_client
        r = CrawlResultFactory.make()
        validated = CrawlResultFactory.make(result_id=r.id, status=CrawlStatus.VALID)
        service.validate_result.return_value = validated
        await client.patch(f"/api/v1/crawler/results/{r.id}/validate")
        _, kwargs = service.validate_result.call_args
        assert "mapper" in kwargs
        assert kwargs["mapper"] is not None

    async def test_service_recipe_unavailable_returns_503(self, results_client):
        client, service = results_client
        service.validate_result.side_effect = HTTPException(
            status_code=503, detail="service indisponible"
        )
        r = CrawlResultFactory.make()
        response = await client.patch(f"/api/v1/crawler/results/{r.id}/validate")
        assert response.status_code == 503


class TestHydrateResult:
    def _make_hydrated(self, result_id: uuid.UUID | None = None) -> RecipeHydrated:
        return RecipeHydrated(
            title="Tarte aux pommes",
            description="Super tarte",
            instructions="Mélanger et cuire.",
            servings=4,
            prep_time_minutes=15,
            cook_time_minutes=30,
            ingredients=[HydratedIngredient(name="farine", quantity=200.0, unit="g")],
            groq_tokens_used=150,
        )

    async def test_hydrate_success_returns_200(self, results_client):
        client, service = results_client
        r = CrawlResultFactory.make()
        service.hydrate_result.return_value = self._make_hydrated(r.id)
        response = await client.post(f"/api/v1/crawler/results/{r.id}/hydrate")
        assert response.status_code == 200
        body = response.json()
        assert body["title"] == "Tarte aux pommes"
        assert body["groq_tokens_used"] == 150
        assert len(body["ingredients"]) == 1

    async def test_not_found_returns_404(self, results_client):
        client, service = results_client
        service.hydrate_result.side_effect = HTTPException(
            status_code=404, detail="Not found"
        )
        response = await client.post(
            "/api/v1/crawler/results/00000000-0000-0000-0000-000000000099/hydrate"
        )
        assert response.status_code == 404

    async def test_already_validated_returns_409(self, results_client):
        client, service = results_client
        service.hydrate_result.side_effect = HTTPException(
            status_code=409, detail="Conflict"
        )
        r = CrawlResultFactory.make()
        response = await client.post(f"/api/v1/crawler/results/{r.id}/hydrate")
        assert response.status_code == 409

    async def test_extractor_kwarg_passed_to_service(self, results_client):
        client, service = results_client
        r = CrawlResultFactory.make()
        service.hydrate_result.return_value = self._make_hydrated(r.id)
        await client.post(f"/api/v1/crawler/results/{r.id}/hydrate")
        _, kwargs = service.hydrate_result.call_args
        assert "extractor" in kwargs
        assert kwargs["extractor"] is not None


class TestCommitResult:
    _COMMIT_BODY = {
        "title": "Tarte aux pommes",
        "instructions": "Mélanger et cuire.",
        "ingredients": [{"name": "farine", "quantity": 200.0, "unit": "g"}],
    }

    async def test_commit_success_returns_200(self, results_client):
        client, service = results_client
        r = CrawlResultFactory.make()
        validated = CrawlResultFactory.make(result_id=r.id, status=CrawlStatus.VALID)
        service.commit_result.return_value = validated
        response = await client.post(
            f"/api/v1/crawler/results/{r.id}/commit", json=self._COMMIT_BODY
        )
        assert response.status_code == 200
        assert response.json()["status"] == CrawlStatus.VALID.value

    async def test_not_found_returns_404(self, results_client):
        client, service = results_client
        service.commit_result.side_effect = HTTPException(
            status_code=404, detail="Not found"
        )
        response = await client.post(
            "/api/v1/crawler/results/00000000-0000-0000-0000-000000000099/commit",
            json=self._COMMIT_BODY,
        )
        assert response.status_code == 404

    async def test_already_validated_returns_409(self, results_client):
        client, service = results_client
        service.commit_result.side_effect = HTTPException(
            status_code=409, detail="Conflict"
        )
        r = CrawlResultFactory.make()
        response = await client.post(
            f"/api/v1/crawler/results/{r.id}/commit", json=self._COMMIT_BODY
        )
        assert response.status_code == 409

    async def test_service_recipe_unavailable_returns_503(self, results_client):
        client, service = results_client
        service.commit_result.side_effect = HTTPException(
            status_code=503, detail="indisponible"
        )
        r = CrawlResultFactory.make()
        response = await client.post(
            f"/api/v1/crawler/results/{r.id}/commit", json=self._COMMIT_BODY
        )
        assert response.status_code == 503

    async def test_missing_body_returns_422(self, results_client):
        client, _ = results_client
        r = CrawlResultFactory.make()
        response = await client.post(f"/api/v1/crawler/results/{r.id}/commit")
        assert response.status_code == 422

    async def test_mapper_and_validated_by_passed_to_service(self, results_client):
        client, service = results_client
        r = CrawlResultFactory.make()
        validated = CrawlResultFactory.make(result_id=r.id, status=CrawlStatus.VALID)
        service.commit_result.return_value = validated
        await client.post(
            f"/api/v1/crawler/results/{r.id}/commit", json=self._COMMIT_BODY
        )
        _, kwargs = service.commit_result.call_args
        assert "mapper" in kwargs
        assert "validated_by" in kwargs


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
        service.reject_result.side_effect = HTTPException(
            status_code=404, detail="Not found"
        )
        response = await client.patch(
            "/api/v1/crawler/results/00000000-0000-0000-0000-000000000099/reject"
        )
        assert response.status_code == 404

    async def test_conflict_returns_409(self, results_client):
        client, service = results_client
        service.reject_result.side_effect = HTTPException(
            status_code=409, detail="Conflict"
        )
        r = CrawlResultFactory.make()
        response = await client.patch(f"/api/v1/crawler/results/{r.id}/reject")
        assert response.status_code == 409


class TestResetResult:
    async def test_reset_success_returns_200(self, results_client):
        client, service = results_client
        r = CrawlResultFactory.make(status=CrawlStatus.REJECTED)
        reset = CrawlResultFactory.make(result_id=r.id, status=CrawlStatus.WAITING)
        service.reset_result.return_value = reset
        response = await client.patch(f"/api/v1/crawler/results/{r.id}/reset")
        assert response.status_code == 200
        assert response.json()["status"] == CrawlStatus.WAITING.value

    async def test_not_found_returns_404(self, results_client):
        client, service = results_client
        service.reset_result.side_effect = HTTPException(
            status_code=404, detail="Not found"
        )
        response = await client.patch(
            "/api/v1/crawler/results/00000000-0000-0000-0000-000000000099/reset"
        )
        assert response.status_code == 404

    async def test_conflict_returns_409(self, results_client):
        client, service = results_client
        service.reset_result.side_effect = HTTPException(
            status_code=409, detail="Conflict"
        )
        r = CrawlResultFactory.make()
        response = await client.patch(f"/api/v1/crawler/results/{r.id}/reset")
        assert response.status_code == 409
