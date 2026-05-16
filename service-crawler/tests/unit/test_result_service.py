import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException

from app.models.enums import CrawlStatus, CrawlType
from app.schemas.crawl_result import CrawlResultListParams, CrawlResultUpdate
from app.services.result_service import ResultService


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
        r.title = "Test Title"
        r.raw_content = "some content"
        r.images = []
        r.video_url = None
        r.status = status
        r.validate_by = None
        r.validate_date = None
        r.created_at = datetime.now(timezone.utc)
        return r


class TestResultServiceListResults:
    @pytest.fixture
    def mock_repo(self):
        return AsyncMock()

    @pytest.fixture
    def service(self, mock_repo):
        return ResultService(mock_repo)

    async def test_empty_returns_zero_total(self, service, mock_repo):
        mock_repo.list_by_filters.return_value = ([], 0)
        result = await service.list_results(CrawlResultListParams())
        assert result.total == 0
        assert result.items == []
        assert result.pages == 0

    async def test_pagination_pages_computed(self, service, mock_repo):
        items = [CrawlResultFactory.make() for _ in range(3)]
        mock_repo.list_by_filters.return_value = (items, 25)
        result = await service.list_results(CrawlResultListParams(page=2, page_size=10))
        assert result.total == 25
        assert result.page == 2
        assert result.page_size == 10
        assert result.pages == 3

    async def test_single_page(self, service, mock_repo):
        items = [CrawlResultFactory.make() for _ in range(5)]
        mock_repo.list_by_filters.return_value = (items, 5)
        result = await service.list_results(CrawlResultListParams(page=1, page_size=20))
        assert result.pages == 1

    async def test_status_filter_forwarded(self, service, mock_repo):
        mock_repo.list_by_filters.return_value = ([], 0)
        await service.list_results(CrawlResultListParams(status=CrawlStatus.VALID))
        mock_repo.list_by_filters.assert_called_once_with(
            status=CrawlStatus.VALID,
            source_id=None,
            page=1,
            page_size=20,
        )

    async def test_source_id_filter_forwarded(self, service, mock_repo):
        sid = uuid.uuid4()
        mock_repo.list_by_filters.return_value = ([], 0)
        await service.list_results(CrawlResultListParams(source_id=sid))
        mock_repo.list_by_filters.assert_called_once_with(
            status=CrawlStatus.WAITING,
            source_id=sid,
            page=1,
            page_size=20,
        )


class TestResultServiceGetResult:
    @pytest.fixture
    def mock_repo(self):
        return AsyncMock()

    @pytest.fixture
    def service(self, mock_repo):
        return ResultService(mock_repo)

    async def test_found(self, service, mock_repo):
        r = CrawlResultFactory.make()
        mock_repo.get_by_id.return_value = r
        result = await service.get_result(r.id)
        assert result.id == r.id

    async def test_not_found_raises_404(self, service, mock_repo):
        mock_repo.get_by_id.return_value = None
        with pytest.raises(HTTPException) as exc:
            await service.get_result(uuid.uuid4())
        assert exc.value.status_code == 404


class TestResultServiceUpdateResult:
    @pytest.fixture
    def mock_repo(self):
        return AsyncMock()

    @pytest.fixture
    def service(self, mock_repo):
        return ResultService(mock_repo)

    async def test_update_waiting_succeeds(self, service, mock_repo):
        r = CrawlResultFactory.make(status=CrawlStatus.WAITING)
        updated = CrawlResultFactory.make(result_id=r.id)
        updated.title = "New Title"
        mock_repo.get_by_id.return_value = r
        mock_repo.update.return_value = updated
        result = await service.update_result(r.id, CrawlResultUpdate(title="New Title"))
        assert result.title == "New Title"

    async def test_update_not_found_raises_404(self, service, mock_repo):
        mock_repo.get_by_id.return_value = None
        with pytest.raises(HTTPException) as exc:
            await service.update_result(uuid.uuid4(), CrawlResultUpdate(title="X"))
        assert exc.value.status_code == 404

    async def test_update_valid_raises_409(self, service, mock_repo):
        r = CrawlResultFactory.make(status=CrawlStatus.VALID)
        mock_repo.get_by_id.return_value = r
        with pytest.raises(HTTPException) as exc:
            await service.update_result(r.id, CrawlResultUpdate(title="X"))
        assert exc.value.status_code == 409

    async def test_update_rejected_raises_409(self, service, mock_repo):
        r = CrawlResultFactory.make(status=CrawlStatus.REJECTED)
        mock_repo.get_by_id.return_value = r
        with pytest.raises(HTTPException) as exc:
            await service.update_result(r.id, CrawlResultUpdate(title="X"))
        assert exc.value.status_code == 409


class TestResultServiceRejectResult:
    @pytest.fixture
    def mock_repo(self):
        return AsyncMock()

    @pytest.fixture
    def service(self, mock_repo):
        return ResultService(mock_repo)

    async def test_reject_waiting_succeeds(self, service, mock_repo):
        r = CrawlResultFactory.make(status=CrawlStatus.WAITING)
        rejected = CrawlResultFactory.make(result_id=r.id, status=CrawlStatus.REJECTED)
        mock_repo.get_by_id.return_value = r
        mock_repo.reject.return_value = rejected
        result = await service.reject_result(r.id)
        assert result.status == CrawlStatus.REJECTED

    async def test_reject_not_found_raises_404(self, service, mock_repo):
        mock_repo.get_by_id.return_value = None
        with pytest.raises(HTTPException) as exc:
            await service.reject_result(uuid.uuid4())
        assert exc.value.status_code == 404

    async def test_reject_already_rejected_raises_409(self, service, mock_repo):
        r = CrawlResultFactory.make(status=CrawlStatus.REJECTED)
        mock_repo.get_by_id.return_value = r
        with pytest.raises(HTTPException) as exc:
            await service.reject_result(r.id)
        assert exc.value.status_code == 409

    async def test_reject_already_validated_raises_409(self, service, mock_repo):
        r = CrawlResultFactory.make(status=CrawlStatus.VALID)
        mock_repo.get_by_id.return_value = r
        with pytest.raises(HTTPException) as exc:
            await service.reject_result(r.id)
        assert exc.value.status_code == 409


class TestResultServiceValidateResult:
    @pytest.fixture
    def mock_repo(self):
        return AsyncMock()

    @pytest.fixture
    def service(self, mock_repo):
        return ResultService(mock_repo)

    async def test_validate_waiting_succeeds(self, service, mock_repo):
        r = CrawlResultFactory.make(status=CrawlStatus.WAITING)
        user_id = uuid.UUID("00000000-0000-0000-0000-000000000001")
        validated = CrawlResultFactory.make(result_id=r.id, status=CrawlStatus.VALID)
        validated.validate_by = user_id
        mock_repo.get_by_id.return_value = r
        mock_repo.validate.return_value = validated
        result = await service.validate_result(r.id, user_id)
        assert result.status == CrawlStatus.VALID
        mock_repo.validate.assert_called_once_with(r, validated_by=user_id)

    async def test_validate_not_found_raises_404(self, service, mock_repo):
        mock_repo.get_by_id.return_value = None
        with pytest.raises(HTTPException) as exc:
            await service.validate_result(uuid.uuid4(), uuid.uuid4())
        assert exc.value.status_code == 404

    async def test_validate_already_validated_raises_409(self, service, mock_repo):
        r = CrawlResultFactory.make(status=CrawlStatus.VALID)
        mock_repo.get_by_id.return_value = r
        with pytest.raises(HTTPException) as exc:
            await service.validate_result(r.id, uuid.uuid4())
        assert exc.value.status_code == 409

    async def test_validate_already_rejected_raises_409(self, service, mock_repo):
        r = CrawlResultFactory.make(status=CrawlStatus.REJECTED)
        mock_repo.get_by_id.return_value = r
        with pytest.raises(HTTPException) as exc:
            await service.validate_result(r.id, uuid.uuid4())
        assert exc.value.status_code == 409


class TestResultServiceStaticGuards:
    def test_assert_editable_waiting_passes(self):
        r = MagicMock()
        r.status = CrawlStatus.WAITING
        ResultService._assert_editable(r)

    def test_assert_editable_valid_raises_409(self):
        r = MagicMock()
        r.status = CrawlStatus.VALID
        with pytest.raises(HTTPException) as exc:
            ResultService._assert_editable(r)
        assert exc.value.status_code == 409

    def test_assert_editable_rejected_raises_409(self):
        r = MagicMock()
        r.status = CrawlStatus.REJECTED
        with pytest.raises(HTTPException) as exc:
            ResultService._assert_editable(r)
        assert exc.value.status_code == 409

    def test_assert_rejectable_waiting_passes(self):
        r = MagicMock()
        r.status = CrawlStatus.WAITING
        ResultService._assert_rejectable(r)

    def test_assert_rejectable_rejected_raises_409(self):
        r = MagicMock()
        r.status = CrawlStatus.REJECTED
        with pytest.raises(HTTPException) as exc:
            ResultService._assert_rejectable(r)
        assert exc.value.status_code == 409

    def test_assert_rejectable_valid_raises_409(self):
        r = MagicMock()
        r.status = CrawlStatus.VALID
        with pytest.raises(HTTPException) as exc:
            ResultService._assert_rejectable(r)
        assert exc.value.status_code == 409

    def test_assert_validatable_waiting_passes(self):
        r = MagicMock()
        r.status = CrawlStatus.WAITING
        ResultService._assert_validatable(r)

    def test_assert_validatable_valid_raises_409(self):
        r = MagicMock()
        r.status = CrawlStatus.VALID
        with pytest.raises(HTTPException) as exc:
            ResultService._assert_validatable(r)
        assert exc.value.status_code == 409

    def test_assert_validatable_rejected_raises_409(self):
        r = MagicMock()
        r.status = CrawlStatus.REJECTED
        with pytest.raises(HTTPException) as exc:
            ResultService._assert_validatable(r)
        assert exc.value.status_code == 409