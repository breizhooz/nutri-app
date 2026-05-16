import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.crawl_result import CrawlResult
from app.models.enums import CrawlStatus, CrawlType
from app.repositories.result_repository import ResultRepository
from app.schemas.crawl_result import CrawlResultUpdate


class CrawlResultFactory:
    @staticmethod
    def make(
        result_id: uuid.UUID | None = None,
        status: CrawlStatus = CrawlStatus.WAITING,
        url: str = "https://example.com",
    ) -> MagicMock:
        r = MagicMock(spec=CrawlResult)
        r.id = result_id or uuid.uuid4()
        r.source_id = None
        r.user_id = None
        r.type = CrawlType.WEB
        r.url_origin = url
        r.title = "Test"
        r.raw_content = "content"
        r.images = []
        r.video_url = None
        r.status = status
        r.validate_by = None
        r.validate_date = None
        r.created_at = datetime.now(timezone.utc)
        return r

    @staticmethod
    def make_session() -> AsyncMock:
        session = AsyncMock(spec=AsyncSession)
        session.add = MagicMock()
        return session


class TestResultRepositoryCreate:
    @pytest.fixture
    def session(self):
        return CrawlResultFactory.make_session()

    async def test_create_adds_and_commits(self, session):
        repo = ResultRepository(session)
        data = {
            "source_id": None,
            "user_id": None,
            "type": CrawlType.WEB,
            "url_origin": "https://example.com",
            "title": "Test",
            "raw_content": "content",
            "images": [],
            "video_url": None,
            "status": CrawlStatus.WAITING,
        }
        result = await repo.create(data)
        session.add.assert_called_once()
        session.commit.assert_called_once()
        session.refresh.assert_called_once()
        assert isinstance(result, CrawlResult)


class TestResultRepositoryGetById:
    @pytest.fixture
    def session(self):
        return CrawlResultFactory.make_session()

    async def test_found(self, session):
        r = CrawlResultFactory.make()
        execute_result = MagicMock()
        execute_result.scalar_one_or_none.return_value = r
        session.execute.return_value = execute_result
        result = await ResultRepository(session).get_by_id(r.id)
        assert result == r

    async def test_not_found_returns_none(self, session):
        execute_result = MagicMock()
        execute_result.scalar_one_or_none.return_value = None
        session.execute.return_value = execute_result
        result = await ResultRepository(session).get_by_id(uuid.uuid4())
        assert result is None


class TestResultRepositoryListByFilters:
    @pytest.fixture
    def session(self):
        return CrawlResultFactory.make_session()

    async def test_empty_result(self, session):
        count_mock = MagicMock()
        count_mock.scalar_one.return_value = 0
        data_mock = MagicMock()
        data_mock.scalars.return_value.all.return_value = []
        session.execute.side_effect = [count_mock, data_mock]

        items, total = await ResultRepository(session).list_by_filters()
        assert total == 0
        assert items == []

    async def test_returns_items_and_total(self, session):
        r1, r2 = CrawlResultFactory.make(), CrawlResultFactory.make()
        count_mock = MagicMock()
        count_mock.scalar_one.return_value = 2
        data_mock = MagicMock()
        data_mock.scalars.return_value.all.return_value = [r1, r2]
        session.execute.side_effect = [count_mock, data_mock]

        items, total = await ResultRepository(session).list_by_filters(
            status=CrawlStatus.WAITING, page=1, page_size=20
        )
        assert total == 2
        assert len(items) == 2

    async def test_pagination_calls_execute_twice(self, session):
        count_mock = MagicMock()
        count_mock.scalar_one.return_value = 50
        data_mock = MagicMock()
        data_mock.scalars.return_value.all.return_value = []
        session.execute.side_effect = [count_mock, data_mock]

        await ResultRepository(session).list_by_filters(page=3, page_size=10)
        assert session.execute.call_count == 2


class TestResultRepositoryMutations:
    @pytest.fixture
    def session(self):
        return CrawlResultFactory.make_session()

    async def test_update_sets_fields_and_commits(self, session):
        r = CrawlResultFactory.make()
        repo = ResultRepository(session)
        data = CrawlResultUpdate(title="New Title")
        await repo.update(r, data)
        assert r.title == "New Title"
        session.commit.assert_called_once()

    async def test_validate_sets_status_and_metadata(self, session):
        r = CrawlResultFactory.make(status=CrawlStatus.WAITING)
        user_id = uuid.uuid4()
        repo = ResultRepository(session)
        await repo.validate(r, validated_by=user_id)
        assert r.status == CrawlStatus.VALID
        assert r.validate_by == user_id
        assert r.validate_date is not None
        session.commit.assert_called_once()

    async def test_reject_sets_status(self, session):
        r = CrawlResultFactory.make(status=CrawlStatus.WAITING)
        repo = ResultRepository(session)
        await repo.reject(r)
        assert r.status == CrawlStatus.REJECTED
        session.commit.assert_called_once()


class TestResultRepositoryUrlExists:
    @pytest.fixture
    def session(self):
        return CrawlResultFactory.make_session()

    async def test_url_exists_returns_true(self, session):
        execute_result = MagicMock()
        execute_result.scalar_one_or_none.return_value = uuid.uuid4()
        session.execute.return_value = execute_result
        result = await ResultRepository(session).url_exists("https://example.com")
        assert result is True

    async def test_url_not_exists_returns_false(self, session):
        execute_result = MagicMock()
        execute_result.scalar_one_or_none.return_value = None
        session.execute.return_value = execute_result
        result = await ResultRepository(session).url_exists("https://unknown.com")
        assert result is False