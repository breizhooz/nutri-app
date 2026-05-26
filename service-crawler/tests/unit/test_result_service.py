import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest
from fastapi import HTTPException

from app.models.enums import CrawlStatus, CrawlType
from app.schemas.crawl_result import CrawlResultListParams, CrawlResultUpdate
from app.services.result_service import ResultService


# ─── Factories ────────────────────────────────────────────────────────────────


def make_result(result_id: uuid.UUID | None = None) -> MagicMock:
    r = MagicMock()
    r.id = result_id or uuid.uuid4()
    r.type = CrawlType.WEB
    r.url_origin = "https://example.com"
    r.title = "Test Title"
    r.raw_content = "some content"
    r.images = []
    r.video_url = None
    r.created_at = datetime.now(timezone.utc)
    return r


def make_link(
    result_id: uuid.UUID | None = None,
    user_id: uuid.UUID | None = None,
    status: CrawlStatus = CrawlStatus.WAITING,
) -> MagicMock:
    r = make_result(result_id)
    lnk = MagicMock()
    lnk.id = uuid.uuid4()
    lnk.result_id = r.id
    lnk.result = r
    lnk.user_id = user_id or uuid.uuid4()
    lnk.source_id = None
    lnk.status = status
    lnk.validate_by = None
    lnk.validate_date = None
    lnk.created_at = r.created_at
    return lnk


_USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")


# ─── list_results ─────────────────────────────────────────────────────────────


class TestResultServiceListResults:
    @pytest.fixture
    def mock_repo(self):
        return AsyncMock()

    @pytest.fixture
    def service(self, mock_repo):
        return ResultService(mock_repo)

    async def test_empty_returns_zero_total(self, service, mock_repo):
        mock_repo.list_by_user.return_value = ([], 0)
        result = await service.list_results(_USER_ID, CrawlResultListParams())
        assert result.total == 0
        assert result.items == []
        assert result.pages == 0

    async def test_pagination_pages_computed(self, service, mock_repo):
        links = [make_link() for _ in range(3)]
        mock_repo.list_by_user.return_value = (links, 25)
        result = await service.list_results(
            _USER_ID, CrawlResultListParams(page=2, page_size=10)
        )
        assert result.total == 25
        assert result.page == 2
        assert result.pages == 3

    async def test_status_filter_forwarded(self, service, mock_repo):
        mock_repo.list_by_user.return_value = ([], 0)
        await service.list_results(_USER_ID, CrawlResultListParams(status=CrawlStatus.VALID))
        mock_repo.list_by_user.assert_called_once_with(
            user_id=_USER_ID,
            status=CrawlStatus.VALID,
            source_id=None,
            page=1,
            page_size=20,
        )

    async def test_source_id_filter_forwarded(self, service, mock_repo):
        sid = uuid.uuid4()
        mock_repo.list_by_user.return_value = ([], 0)
        await service.list_results(_USER_ID, CrawlResultListParams(source_id=sid))
        mock_repo.list_by_user.assert_called_once_with(
            user_id=_USER_ID,
            status=CrawlStatus.WAITING,
            source_id=sid,
            page=1,
            page_size=20,
        )


# ─── get_result ───────────────────────────────────────────────────────────────


class TestResultServiceGetResult:
    @pytest.fixture
    def mock_repo(self):
        return AsyncMock()

    @pytest.fixture
    def service(self, mock_repo):
        return ResultService(mock_repo)

    async def test_found(self, service, mock_repo):
        lnk = make_link()
        mock_repo.get_user_link.return_value = lnk
        result = await service.get_result(lnk.result_id, _USER_ID)
        assert result.id == lnk.result.id

    async def test_not_found_raises_404(self, service, mock_repo):
        mock_repo.get_user_link.return_value = None
        with pytest.raises(HTTPException) as exc:
            await service.get_result(uuid.uuid4(), _USER_ID)
        assert exc.value.status_code == 404


# ─── update_result ────────────────────────────────────────────────────────────


class TestResultServiceUpdateResult:
    @pytest.fixture
    def mock_repo(self):
        return AsyncMock()

    @pytest.fixture
    def service(self, mock_repo):
        return ResultService(mock_repo)

    async def test_update_waiting_succeeds(self, service, mock_repo):
        lnk = make_link(status=CrawlStatus.WAITING)
        mock_repo.get_user_link.return_value = lnk
        mock_repo.update_result_content.return_value = lnk.result
        result = await service.update_result(lnk.result_id, _USER_ID, CrawlResultUpdate(title="New"))
        mock_repo.update_result_content.assert_called_once()

    async def test_not_found_raises_404(self, service, mock_repo):
        mock_repo.get_user_link.return_value = None
        with pytest.raises(HTTPException) as exc:
            await service.update_result(uuid.uuid4(), _USER_ID, CrawlResultUpdate(title="X"))
        assert exc.value.status_code == 404

    async def test_update_valid_raises_409(self, service, mock_repo):
        lnk = make_link(status=CrawlStatus.VALID)
        mock_repo.get_user_link.return_value = lnk
        with pytest.raises(HTTPException) as exc:
            await service.update_result(lnk.result_id, _USER_ID, CrawlResultUpdate(title="X"))
        assert exc.value.status_code == 409

    async def test_update_rejected_raises_409(self, service, mock_repo):
        lnk = make_link(status=CrawlStatus.REJECTED)
        mock_repo.get_user_link.return_value = lnk
        with pytest.raises(HTTPException) as exc:
            await service.update_result(lnk.result_id, _USER_ID, CrawlResultUpdate(title="X"))
        assert exc.value.status_code == 409


# ─── reject_result ────────────────────────────────────────────────────────────


class TestResultServiceRejectResult:
    @pytest.fixture
    def mock_repo(self):
        return AsyncMock()

    @pytest.fixture
    def service(self, mock_repo):
        return ResultService(mock_repo)

    async def test_reject_waiting_succeeds(self, service, mock_repo):
        lnk = make_link(status=CrawlStatus.WAITING)
        rejected = make_link(result_id=lnk.result_id, status=CrawlStatus.REJECTED)
        mock_repo.get_user_link.return_value = lnk
        mock_repo.reject_user_link.return_value = rejected
        result = await service.reject_result(lnk.result_id, _USER_ID)
        assert result.status == CrawlStatus.REJECTED

    async def test_not_found_raises_404(self, service, mock_repo):
        mock_repo.get_user_link.return_value = None
        with pytest.raises(HTTPException) as exc:
            await service.reject_result(uuid.uuid4(), _USER_ID)
        assert exc.value.status_code == 404

    async def test_reject_already_rejected_raises_409(self, service, mock_repo):
        lnk = make_link(status=CrawlStatus.REJECTED)
        mock_repo.get_user_link.return_value = lnk
        with pytest.raises(HTTPException) as exc:
            await service.reject_result(lnk.result_id, _USER_ID)
        assert exc.value.status_code == 409

    async def test_reject_already_validated_raises_409(self, service, mock_repo):
        lnk = make_link(status=CrawlStatus.VALID)
        mock_repo.get_user_link.return_value = lnk
        with pytest.raises(HTTPException) as exc:
            await service.reject_result(lnk.result_id, _USER_ID)
        assert exc.value.status_code == 409


# ─── validate_result ──────────────────────────────────────────────────────────


class TestResultServiceValidateResult:
    @pytest.fixture
    def mock_repo(self):
        return AsyncMock()

    @pytest.fixture
    def service(self, mock_repo):
        return ResultService(mock_repo)

    async def test_validate_waiting_succeeds(self, service, mock_repo):
        lnk = make_link(status=CrawlStatus.WAITING)
        validated = make_link(result_id=lnk.result_id, status=CrawlStatus.VALID)
        validated.validate_by = _USER_ID
        mock_repo.get_user_link.return_value = lnk
        mock_repo.validate_user_link.return_value = validated
        result = await service.validate_result(lnk.result_id, _USER_ID, _USER_ID)
        assert result.status == CrawlStatus.VALID
        mock_repo.validate_user_link.assert_called_once_with(lnk, validated_by=_USER_ID)

    async def test_not_found_raises_404(self, service, mock_repo):
        mock_repo.get_user_link.return_value = None
        with pytest.raises(HTTPException) as exc:
            await service.validate_result(uuid.uuid4(), _USER_ID, _USER_ID)
        assert exc.value.status_code == 404

    async def test_already_validated_raises_409(self, service, mock_repo):
        lnk = make_link(status=CrawlStatus.VALID)
        mock_repo.get_user_link.return_value = lnk
        with pytest.raises(HTTPException) as exc:
            await service.validate_result(lnk.result_id, _USER_ID, _USER_ID)
        assert exc.value.status_code == 409

    async def test_already_rejected_raises_409(self, service, mock_repo):
        lnk = make_link(status=CrawlStatus.REJECTED)
        mock_repo.get_user_link.return_value = lnk
        with pytest.raises(HTTPException) as exc:
            await service.validate_result(lnk.result_id, _USER_ID, _USER_ID)
        assert exc.value.status_code == 409

    async def test_mapper_called_with_result(self, service, mock_repo):
        lnk = make_link(status=CrawlStatus.WAITING)
        validated = make_link(result_id=lnk.result_id, status=CrawlStatus.VALID)
        mock_repo.get_user_link.return_value = lnk
        mock_repo.validate_user_link.return_value = validated
        mock_mapper = AsyncMock()
        mock_mapper.map_and_send.return_value = {}
        await service.validate_result(lnk.result_id, _USER_ID, _USER_ID, mapper=mock_mapper)
        mock_mapper.map_and_send.assert_called_once_with(validated.result)

    async def test_request_error_logged_validation_succeeds(self, service, mock_repo):
        lnk = make_link(status=CrawlStatus.WAITING)
        validated = make_link(result_id=lnk.result_id, status=CrawlStatus.VALID)
        mock_repo.get_user_link.return_value = lnk
        mock_repo.validate_user_link.return_value = validated
        mock_mapper = AsyncMock()
        mock_mapper.map_and_send.side_effect = httpx.RequestError(
            "connection refused", request=MagicMock()
        )
        result = await service.validate_result(lnk.result_id, _USER_ID, _USER_ID, mapper=mock_mapper)
        assert result.status == CrawlStatus.VALID

    async def test_no_mapper_skips_recipe_service(self, service, mock_repo):
        lnk = make_link(status=CrawlStatus.WAITING)
        validated = make_link(result_id=lnk.result_id, status=CrawlStatus.VALID)
        mock_repo.get_user_link.return_value = lnk
        mock_repo.validate_user_link.return_value = validated
        result = await service.validate_result(lnk.result_id, _USER_ID, _USER_ID, mapper=None)
        assert result.status == CrawlStatus.VALID


# ─── static guards ────────────────────────────────────────────────────────────


class TestResultServiceStaticGuards:
    def test_assert_editable_waiting_passes(self):
        lnk = MagicMock()
        lnk.status = CrawlStatus.WAITING
        ResultService._assert_editable(lnk)

    def test_assert_editable_valid_raises_409(self):
        lnk = MagicMock()
        lnk.status = CrawlStatus.VALID
        with pytest.raises(HTTPException) as exc:
            ResultService._assert_editable(lnk)
        assert exc.value.status_code == 409

    def test_assert_editable_rejected_raises_409(self):
        lnk = MagicMock()
        lnk.status = CrawlStatus.REJECTED
        with pytest.raises(HTTPException) as exc:
            ResultService._assert_editable(lnk)
        assert exc.value.status_code == 409

    def test_assert_rejectable_waiting_passes(self):
        lnk = MagicMock()
        lnk.status = CrawlStatus.WAITING
        ResultService._assert_rejectable(lnk)

    def test_assert_rejectable_rejected_raises_409(self):
        lnk = MagicMock()
        lnk.status = CrawlStatus.REJECTED
        with pytest.raises(HTTPException) as exc:
            ResultService._assert_rejectable(lnk)
        assert exc.value.status_code == 409

    def test_assert_rejectable_valid_raises_409(self):
        lnk = MagicMock()
        lnk.status = CrawlStatus.VALID
        with pytest.raises(HTTPException) as exc:
            ResultService._assert_rejectable(lnk)
        assert exc.value.status_code == 409

    def test_assert_validatable_waiting_passes(self):
        lnk = MagicMock()
        lnk.status = CrawlStatus.WAITING
        ResultService._assert_validatable(lnk)

    def test_assert_validatable_valid_raises_409(self):
        lnk = MagicMock()
        lnk.status = CrawlStatus.VALID
        with pytest.raises(HTTPException) as exc:
            ResultService._assert_validatable(lnk)
        assert exc.value.status_code == 409

    def test_assert_validatable_rejected_raises_409(self):
        lnk = MagicMock()
        lnk.status = CrawlStatus.REJECTED
        with pytest.raises(HTTPException) as exc:
            ResultService._assert_validatable(lnk)
        assert exc.value.status_code == 409
