import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.crawl_result import CrawlResult
from app.models.crawl_result_user import CrawlResultUser
from app.models.enums import CrawlStatus, CrawlType
from app.repositories.result_repository import ResultRepository
from app.schemas.crawl_result import CrawlResultUpdate


# ─── Factories ────────────────────────────────────────────────────────────────


def make_result(url: str = "https://example.com") -> MagicMock:
    r = MagicMock(spec=CrawlResult)
    r.id = uuid.uuid4()
    r.type = CrawlType.WEB
    r.url_origin = url
    r.title = "Test"
    r.raw_content = "content"
    r.images = []
    r.video_url = None
    r.created_at = datetime.now(timezone.utc)
    return r


def make_link(
    result: MagicMock | None = None,
    status: CrawlStatus = CrawlStatus.WAITING,
    user_id: uuid.UUID | None = None,
) -> MagicMock:
    r = result or make_result()
    lnk = MagicMock(spec=CrawlResultUser)
    lnk.id = uuid.uuid4()
    lnk.result_id = r.id
    lnk.result = r
    lnk.user_id = user_id or uuid.uuid4()
    lnk.source_id = None
    lnk.status = status
    lnk.validate_by = None
    lnk.validate_date = None
    lnk.created_at = datetime.now(timezone.utc)
    return lnk


def make_session() -> AsyncMock:
    session = AsyncMock(spec=AsyncSession)
    session.add = MagicMock()
    return session


# ─── get_or_create_result ─────────────────────────────────────────────────────


class TestGetOrCreateResult:
    @pytest.fixture
    def session(self):
        return make_session()

    async def test_creates_when_url_not_found(self, session):
        execute_result = MagicMock()
        execute_result.scalar_one_or_none.return_value = None
        session.execute.return_value = execute_result

        repo = ResultRepository(session)
        data = {
            "type": CrawlType.WEB,
            "url_origin": "https://new.com",
            "title": "New",
        }
        result, created = await repo.get_or_create_result(data)
        assert created is True
        session.add.assert_called_once()
        session.flush.assert_called_once()

    async def test_returns_existing_when_url_found(self, session):
        existing = make_result(url="https://exists.com")
        execute_result = MagicMock()
        execute_result.scalar_one_or_none.return_value = existing
        session.execute.return_value = execute_result

        repo = ResultRepository(session)
        result, created = await repo.get_or_create_result(
            {"type": CrawlType.WEB, "url_origin": "https://exists.com"}
        )
        assert created is False
        assert result is existing
        session.add.assert_not_called()


# ─── user_link_exists ─────────────────────────────────────────────────────────


class TestUserLinkExists:
    @pytest.fixture
    def session(self):
        return make_session()

    async def test_returns_true_when_link_found(self, session):
        execute_result = MagicMock()
        execute_result.scalar_one_or_none.return_value = uuid.uuid4()
        session.execute.return_value = execute_result
        result = await ResultRepository(session).user_link_exists(
            "https://example.com", uuid.uuid4()
        )
        assert result is True

    async def test_returns_false_when_no_link(self, session):
        execute_result = MagicMock()
        execute_result.scalar_one_or_none.return_value = None
        session.execute.return_value = execute_result
        result = await ResultRepository(session).user_link_exists(
            "https://unknown.com", uuid.uuid4()
        )
        assert result is False


# ─── create_user_link ─────────────────────────────────────────────────────────


class TestCreateUserLink:
    @pytest.fixture
    def session(self):
        return make_session()

    async def test_adds_and_commits(self, session):
        repo = ResultRepository(session)
        result_id = uuid.uuid4()
        user_id = uuid.uuid4()
        await repo.create_user_link(result_id, user_id, source_id=None)
        session.add.assert_called_once()
        session.commit.assert_called_once()
        session.refresh.assert_called_once()


# ─── get_user_link ────────────────────────────────────────────────────────────


class TestGetUserLink:
    @pytest.fixture
    def session(self):
        return make_session()

    async def test_found(self, session):
        lnk = make_link()
        execute_result = MagicMock()
        execute_result.scalar_one_or_none.return_value = lnk
        session.execute.return_value = execute_result
        result = await ResultRepository(session).get_user_link(
            lnk.result_id, lnk.user_id
        )
        assert result is lnk

    async def test_not_found_returns_none(self, session):
        execute_result = MagicMock()
        execute_result.scalar_one_or_none.return_value = None
        session.execute.return_value = execute_result
        result = await ResultRepository(session).get_user_link(
            uuid.uuid4(), uuid.uuid4()
        )
        assert result is None


# ─── list_by_user ─────────────────────────────────────────────────────────────


class TestListByUser:
    @pytest.fixture
    def session(self):
        return make_session()

    async def test_empty_result(self, session):
        count_mock = MagicMock()
        count_mock.scalar_one.return_value = 0
        data_mock = MagicMock()
        data_mock.scalars.return_value.all.return_value = []
        session.execute.side_effect = [count_mock, data_mock]

        items, total = await ResultRepository(session).list_by_user(uuid.uuid4())
        assert total == 0
        assert items == []

    async def test_returns_items_and_total(self, session):
        lnk1, lnk2 = make_link(), make_link()
        count_mock = MagicMock()
        count_mock.scalar_one.return_value = 2
        data_mock = MagicMock()
        data_mock.scalars.return_value.all.return_value = [lnk1, lnk2]
        session.execute.side_effect = [count_mock, data_mock]

        items, total = await ResultRepository(session).list_by_user(
            uuid.uuid4(), status=CrawlStatus.WAITING, page=1, page_size=20
        )
        assert total == 2
        assert len(items) == 2


# ─── mutations ────────────────────────────────────────────────────────────────


class TestMutations:
    @pytest.fixture
    def session(self):
        return make_session()

    async def test_validate_user_link(self, session):
        lnk = make_link(status=CrawlStatus.WAITING)
        user_id = uuid.uuid4()
        await ResultRepository(session).validate_user_link(lnk, validated_by=user_id)
        assert lnk.status == CrawlStatus.VALID
        assert lnk.validate_by == user_id
        assert lnk.validate_date is not None
        session.commit.assert_called_once()

    async def test_reject_user_link(self, session):
        lnk = make_link(status=CrawlStatus.WAITING)
        await ResultRepository(session).reject_user_link(lnk)
        assert lnk.status == CrawlStatus.REJECTED
        session.commit.assert_called_once()

    async def test_update_result_content(self, session):
        r = make_result()
        data = CrawlResultUpdate(title="Nouveau titre")
        await ResultRepository(session).update_result_content(r, data)
        assert r.title == "Nouveau titre"
        session.commit.assert_called_once()
