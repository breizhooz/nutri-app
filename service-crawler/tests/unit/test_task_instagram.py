"""Tests de la politique de retry anti-blocage du crawl Instagram."""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest
from instaloader.exceptions import (
    ConnectionException,
    LoginRequiredException,
    QueryReturnedForbiddenException,
    TooManyRequestsException,
)

from app.models.enums import CrawlStatus

import tasks.instagram as ig

SOURCE_ID = "f84dba54-edfe-4192-9ef0-062acae09619"


class _FakeSession:
    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False


def _patch_db_and_source(monkeypatch):
    """Mocke la fabrique de session et le SourceRepository (source valide, 1er crawl)."""
    monkeypatch.setattr(ig, "_make_session_factory", lambda: (lambda: _FakeSession()))

    source = MagicMock()
    source.user_id = "user-1"
    source.last_crawl = None  # → chemin fetch_posts (crawl complet)

    source_repo = MagicMock()
    source_repo.get_by_id = AsyncMock(return_value=source)
    monkeypatch.setattr(ig, "SourceRepository", lambda session: source_repo)
    monkeypatch.setattr(ig, "ResultRepository", lambda session: MagicMock())


def _run_with_fetch_error(monkeypatch, exc: Exception):
    _patch_db_and_source(monkeypatch)
    service = MagicMock()
    service.fetch_posts.side_effect = exc
    monkeypatch.setattr(ig, "InstagramService", lambda: service)

    task = MagicMock()
    task.retry.side_effect = RuntimeError("retry called")  # sentinelle
    asyncio.run(ig._do_crawl(task, SOURCE_ID, "joladiete"))
    return task


@pytest.mark.parametrize(
    "exc",
    [
        TooManyRequestsException("429"),
        LoginRequiredException("login required"),
        QueryReturnedForbiddenException("403"),
    ],
)
def test_blocking_errors_do_not_retry(monkeypatch, exc):
    task = _run_with_fetch_error(monkeypatch, exc)
    task.retry.assert_not_called()


def test_403_connection_error_is_treated_as_block(monkeypatch):
    # get_posts() remonte le 403 comme un ConnectionException générique.
    task = _run_with_fetch_error(
        monkeypatch,
        ConnectionException("JSON Query to graphql/query: 403 Forbidden"),
    )
    task.retry.assert_not_called()


def test_transient_connection_error_retries_with_long_backoff(monkeypatch):
    _patch_db_and_source(monkeypatch)
    service = MagicMock()
    service.fetch_posts.side_effect = ConnectionException("timeout")
    monkeypatch.setattr(ig, "InstagramService", lambda: service)

    task = MagicMock()
    task.retry.side_effect = RuntimeError("retry")  # interrompt comme le vrai retry

    with pytest.raises(RuntimeError):
        asyncio.run(ig._do_crawl(task, SOURCE_ID, "joladiete"))

    task.retry.assert_called_once()
    assert task.retry.call_args.kwargs["countdown"] == ig._TRANSIENT_RETRY_DELAY


def test_unknown_error_retries(monkeypatch):
    _patch_db_and_source(monkeypatch)
    service = MagicMock()
    service.fetch_posts.side_effect = ValueError("boom")
    monkeypatch.setattr(ig, "InstagramService", lambda: service)

    task = MagicMock()
    task.retry.side_effect = RuntimeError("retry")

    with pytest.raises(RuntimeError):
        asyncio.run(ig._do_crawl(task, SOURCE_ID, "joladiete"))

    task.retry.assert_called_once()
    assert task.retry.call_args.kwargs["countdown"] == ig._TRANSIENT_RETRY_DELAY


# ─── crawl_instagram_post (import d'un seul post) ──────────────────────────────

USER_ID = "00000000-0000-0000-0000-000000000001"


def _patch_db_post(monkeypatch, existing=None):
    monkeypatch.setattr(ig, "_make_session_factory", lambda: (lambda: _FakeSession()))
    result = MagicMock()
    result.id = "res-1"
    repo = MagicMock()
    repo.get_user_link_by_url = AsyncMock(return_value=existing)
    repo.reset_to_waiting = AsyncMock()
    repo.get_or_create_result = AsyncMock(return_value=(result, True))
    repo.create_user_link = AsyncMock()
    monkeypatch.setattr(ig, "ResultRepository", lambda session: repo)
    monkeypatch.setattr(ig, "NotificationClient", lambda: MagicMock(
        notify_crawl_done=AsyncMock(),
        notify_crawl_error=AsyncMock(),
    ))
    return repo


def _patch_ig_service(monkeypatch, service: MagicMock) -> None:
    """Remplace InstagramService par un mock de classe (préserve POST_URL)."""
    cls = MagicMock()
    cls.POST_URL = "https://www.instagram.com/p/{shortcode}/"
    cls.return_value = service
    monkeypatch.setattr(ig, "InstagramService", cls)


def test_single_post_success_creates_result(monkeypatch):
    repo = _patch_db_post(monkeypatch)
    post = MagicMock(
        url="https://www.instagram.com/p/Cabc/",
        title="Recette",
        caption="…",
        images=[],
        video_url=None,
        timestamp=None,
    )
    service = MagicMock()
    service.fetch_post.return_value = post
    _patch_ig_service(monkeypatch, service)

    asyncio.run(ig._do_crawl_post(MagicMock(), "Cabc", USER_ID))

    service.fetch_post.assert_called_once_with("Cabc")
    repo.get_or_create_result.assert_awaited_once()
    repo.create_user_link.assert_awaited_once()


def test_single_post_existing_reopens_from_cache(monkeypatch):
    # Déjà importé (VALID) → ré-ouvert depuis le cache, sans appel Instagram.
    existing = MagicMock()
    existing.status = CrawlStatus.VALID
    repo = _patch_db_post(monkeypatch, existing=existing)
    service = MagicMock()
    _patch_ig_service(monkeypatch, service)

    asyncio.run(ig._do_crawl_post(MagicMock(), "Cabc", USER_ID))

    service.fetch_post.assert_not_called()
    repo.reset_to_waiting.assert_awaited_once_with(existing)
    repo.get_or_create_result.assert_not_called()


def test_single_post_already_waiting_does_nothing(monkeypatch):
    existing = MagicMock()
    existing.status = CrawlStatus.WAITING
    repo = _patch_db_post(monkeypatch, existing=existing)
    service = MagicMock()
    _patch_ig_service(monkeypatch, service)

    asyncio.run(ig._do_crawl_post(MagicMock(), "Cabc", USER_ID))

    service.fetch_post.assert_not_called()
    repo.reset_to_waiting.assert_not_called()


def test_single_post_blocking_error_does_not_retry(monkeypatch):
    _patch_db_post(monkeypatch)
    service = MagicMock()
    service.fetch_post.side_effect = QueryReturnedForbiddenException("403")
    _patch_ig_service(monkeypatch, service)

    task = MagicMock()
    task.retry.side_effect = RuntimeError("retry")
    asyncio.run(ig._do_crawl_post(task, "Cabc", USER_ID))  # ne lève pas
    task.retry.assert_not_called()
