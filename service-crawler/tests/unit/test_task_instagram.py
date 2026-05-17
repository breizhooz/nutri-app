"""Tests unitaires — tâche Celery crawl_instagram (Phase 6)."""
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.enums import CrawlStatus, CrawlType
from app.services.instagram_service import InstagramPost
from tasks.instagram import _do_crawl


# ─── Helpers ──────────────────────────────────────────────────────────────────


def _make_post(shortcode: str = "abc123", url: str | None = None) -> InstagramPost:
    return InstagramPost(
        shortcode=shortcode,
        url=url or f"https://www.instagram.com/p/{shortcode}/",
        title=f"Post {shortcode}",
        caption="Test caption",
        images=["https://cdn.ig.com/img.jpg"],
        video_url=None,
        timestamp=datetime.now(timezone.utc),
    )


def _make_source(last_crawl: datetime | None = None) -> MagicMock:
    source = MagicMock()
    source.id = uuid.uuid4()
    source.user_id = uuid.uuid4()
    source.last_crawl = last_crawl
    return source


def _build_session_factory() -> tuple[MagicMock, AsyncMock]:
    """Retourne (factory_mock, session_mock) pour patcher _make_session_factory."""
    mock_session = AsyncMock()
    session_cm = AsyncMock()
    session_cm.__aenter__.return_value = mock_session
    session_cm.__aexit__.return_value = None
    factory = MagicMock()
    factory.return_value = session_cm
    return factory, mock_session


def _patch_all(result_repo, source_repo, ig_service, factory):
    """Retourne un tuple de context managers pour patcher toutes les dépendances."""
    return (
        patch("tasks.instagram.ResultRepository", return_value=result_repo),
        patch("tasks.instagram.SourceRepository", return_value=source_repo),
        patch("tasks.instagram.InstagramService", return_value=ig_service),
        patch("tasks.instagram._make_session_factory", return_value=factory),
    )


# ─── Tests ────────────────────────────────────────────────────────────────────


@pytest.mark.anyio
async def test_initial_crawl_calls_fetch_posts():
    """Sans last_crawl, on appelle fetch_posts, pas fetch_new_posts."""
    source = _make_source(last_crawl=None)
    post = _make_post()
    factory, _ = _build_session_factory()

    result_repo = AsyncMock()
    result_repo.url_exists.return_value = False
    source_repo = AsyncMock()
    source_repo.get_by_id.return_value = source

    ig_service = MagicMock()
    ig_service.fetch_posts.return_value = [post]

    with patch("tasks.instagram.ResultRepository", return_value=result_repo), \
     patch("tasks.instagram.SourceRepository", return_value=source_repo), \
     patch("tasks.instagram.InstagramService", return_value=ig_service), \
     patch("tasks.instagram._make_session_factory", return_value=factory):
        await _do_crawl(MagicMock(), str(source.id), "@testuser")

    ig_service.fetch_posts.assert_called_once_with("@testuser")
    ig_service.fetch_new_posts.assert_not_called()


@pytest.mark.anyio
async def test_incremental_crawl_calls_fetch_new_posts():
    """Avec last_crawl défini, on appelle fetch_new_posts."""
    since = datetime(2024, 6, 1, 0, 0, 0, tzinfo=timezone.utc)
    source = _make_source(last_crawl=since)
    post = _make_post()
    factory, _ = _build_session_factory()

    result_repo = AsyncMock()
    result_repo.url_exists.return_value = False
    source_repo = AsyncMock()
    source_repo.get_by_id.return_value = source

    ig_service = MagicMock()
    ig_service.fetch_new_posts.return_value = [post]

    with patch("tasks.instagram.ResultRepository", return_value=result_repo), \
         patch("tasks.instagram.SourceRepository", return_value=source_repo), \
         patch("tasks.instagram.InstagramService", return_value=ig_service), \
         patch("tasks.instagram._make_session_factory", return_value=factory):
        await _do_crawl(MagicMock(), str(source.id), "@testuser")

    ig_service.fetch_new_posts.assert_called_once_with("@testuser", since)
    ig_service.fetch_posts.assert_not_called()


@pytest.mark.anyio
async def test_new_post_is_stored_with_correct_fields():
    """Un nouveau post est persisté avec les bons champs."""
    source = _make_source()
    post = _make_post("xyz123")
    factory, _ = _build_session_factory()

    result_repo = AsyncMock()
    result_repo.url_exists.return_value = False
    source_repo = AsyncMock()
    source_repo.get_by_id.return_value = source

    ig_service = MagicMock()
    ig_service.fetch_posts.return_value = [post]

    with patch("tasks.instagram.ResultRepository", return_value=result_repo), \
         patch("tasks.instagram.SourceRepository", return_value=source_repo), \
         patch("tasks.instagram.InstagramService", return_value=ig_service), \
         patch("tasks.instagram._make_session_factory", return_value=factory):
        await _do_crawl(MagicMock(), str(source.id), "@testuser")

    result_repo.create.assert_called_once()
    payload = result_repo.create.call_args[0][0]
    assert payload["url_origin"] == post.url
    assert payload["type"] == CrawlType.INSTAGRAM
    assert payload["status"] == CrawlStatus.WAITING
    assert payload["source_id"] == source.id
    assert payload["user_id"] == source.user_id


@pytest.mark.anyio
async def test_duplicate_post_is_skipped():
    """Un post dont l'URL existe déjà n'est pas re-créé."""
    source = _make_source()
    post = _make_post()
    factory, _ = _build_session_factory()

    result_repo = AsyncMock()
    result_repo.url_exists.return_value = True
    source_repo = AsyncMock()
    source_repo.get_by_id.return_value = source

    ig_service = MagicMock()
    ig_service.fetch_posts.return_value = [post]

    with patch("tasks.instagram.ResultRepository", return_value=result_repo), \
         patch("tasks.instagram.SourceRepository", return_value=source_repo), \
         patch("tasks.instagram.InstagramService", return_value=ig_service), \
         patch("tasks.instagram._make_session_factory", return_value=factory):
        await _do_crawl(MagicMock(), str(source.id), "@testuser")

    result_repo.create.assert_not_called()


@pytest.mark.anyio
async def test_source_marked_crawled_after_success():
    """mark_crawled est appelé même quand il n'y a pas de nouveaux posts."""
    source = _make_source()
    factory, _ = _build_session_factory()

    result_repo = AsyncMock()
    source_repo = AsyncMock()
    source_repo.get_by_id.return_value = source

    ig_service = MagicMock()
    ig_service.fetch_posts.return_value = []

    with patch("tasks.instagram.ResultRepository", return_value=result_repo), \
         patch("tasks.instagram.SourceRepository", return_value=source_repo), \
         patch("tasks.instagram.InstagramService", return_value=ig_service), \
         patch("tasks.instagram._make_session_factory", return_value=factory):
        await _do_crawl(MagicMock(), str(source.id), "@testuser")

    source_repo.mark_crawled.assert_called_once_with(source)


@pytest.mark.anyio
async def test_source_not_found_returns_early():
    """Si la source est introuvable, on quitte sans rien créer."""
    factory, _ = _build_session_factory()

    result_repo = AsyncMock()
    source_repo = AsyncMock()
    source_repo.get_by_id.return_value = None
    ig_service = MagicMock()

    with patch("tasks.instagram.ResultRepository", return_value=result_repo), \
         patch("tasks.instagram.SourceRepository", return_value=source_repo), \
         patch("tasks.instagram.InstagramService", return_value=ig_service), \
         patch("tasks.instagram._make_session_factory", return_value=factory):
        await _do_crawl(MagicMock(), str(uuid.uuid4()), "@testuser")

    ig_service.fetch_posts.assert_not_called()
    result_repo.create.assert_not_called()
    source_repo.mark_crawled.assert_not_called()


@pytest.mark.anyio
async def test_instagram_exception_triggers_retry():
    """Une exception de fetch déclenche task.retry."""
    source = _make_source()
    factory, _ = _build_session_factory()

    result_repo = AsyncMock()
    source_repo = AsyncMock()
    source_repo.get_by_id.return_value = source

    ig_service = MagicMock()
    ig_service.fetch_posts.side_effect = RuntimeError("Network error")

    mock_task = MagicMock()
    mock_task.retry.side_effect = RuntimeError("retry triggered")

    with patch("tasks.instagram.ResultRepository", return_value=result_repo), \
         patch("tasks.instagram.SourceRepository", return_value=source_repo), \
         patch("tasks.instagram.InstagramService", return_value=ig_service), \
         patch("tasks.instagram._make_session_factory", return_value=factory):
        with pytest.raises(RuntimeError, match="retry triggered"):
            await _do_crawl(mock_task, str(source.id), "@testuser")

    mock_task.retry.assert_called_once()
    # mark_crawled ne doit PAS être appelé si le fetch a échoué
    source_repo.mark_crawled.assert_not_called()


@pytest.mark.anyio
async def test_multiple_new_posts_all_stored():
    """Plusieurs nouveaux posts sont tous persistés."""
    source = _make_source()
    posts = [_make_post(f"post{i}") for i in range(5)]
    factory, _ = _build_session_factory()

    result_repo = AsyncMock()
    result_repo.url_exists.return_value = False
    source_repo = AsyncMock()
    source_repo.get_by_id.return_value = source

    ig_service = MagicMock()
    ig_service.fetch_posts.return_value = posts

    with patch("tasks.instagram.ResultRepository", return_value=result_repo), \
         patch("tasks.instagram.SourceRepository", return_value=source_repo), \
         patch("tasks.instagram.InstagramService", return_value=ig_service), \
         patch("tasks.instagram._make_session_factory", return_value=factory):
        await _do_crawl(MagicMock(), str(source.id), "@testuser")

    assert result_repo.create.call_count == 5


@pytest.mark.anyio
async def test_mixed_new_and_duplicate_posts():
    """Seuls les posts dont l'URL est inconnue sont créés."""
    source = _make_source()
    posts = [_make_post(f"post{i}") for i in range(4)]
    existing_urls = {posts[0].url, posts[2].url}
    factory, _ = _build_session_factory()

    result_repo = AsyncMock()
    result_repo.url_exists.side_effect = lambda url: url in existing_urls
    source_repo = AsyncMock()
    source_repo.get_by_id.return_value = source

    ig_service = MagicMock()
    ig_service.fetch_posts.return_value = posts

    with patch("tasks.instagram.ResultRepository", return_value=result_repo), \
         patch("tasks.instagram.SourceRepository", return_value=source_repo), \
         patch("tasks.instagram.InstagramService", return_value=ig_service), \
         patch("tasks.instagram._make_session_factory", return_value=factory):
        await _do_crawl(MagicMock(), str(source.id), "@testuser")

    assert result_repo.create.call_count == 2


@pytest.mark.anyio
async def test_video_post_stores_video_url():
    """Un post vidéo est stocké avec son video_url."""
    source = _make_source()
    post = InstagramPost(
        shortcode="vid99",
        url="https://www.instagram.com/p/vid99/",
        title="Video",
        caption="Caption",
        images=["https://cdn.ig.com/thumb.jpg"],
        video_url="https://cdn.ig.com/video.mp4",
        timestamp=datetime.now(timezone.utc),
    )
    factory, _ = _build_session_factory()

    result_repo = AsyncMock()
    result_repo.url_exists.return_value = False
    source_repo = AsyncMock()
    source_repo.get_by_id.return_value = source

    ig_service = MagicMock()
    ig_service.fetch_posts.return_value = [post]

    with patch("tasks.instagram.ResultRepository", return_value=result_repo), \
         patch("tasks.instagram.SourceRepository", return_value=source_repo), \
         patch("tasks.instagram.InstagramService", return_value=ig_service), \
         patch("tasks.instagram._make_session_factory", return_value=factory):
        await _do_crawl(MagicMock(), str(source.id), "@testuser")

    payload = result_repo.create.call_args[0][0]
    assert payload["video_url"] == "https://cdn.ig.com/video.mp4"


@pytest.mark.anyio
async def test_no_posts_no_create_but_mark_crawled():
    """Aucun post → aucun create, mais mark_crawled est quand même appelé."""
    source = _make_source()
    factory, _ = _build_session_factory()

    result_repo = AsyncMock()
    source_repo = AsyncMock()
    source_repo.get_by_id.return_value = source

    ig_service = MagicMock()
    ig_service.fetch_posts.return_value = []

    with patch("tasks.instagram.ResultRepository", return_value=result_repo), \
         patch("tasks.instagram.SourceRepository", return_value=source_repo), \
         patch("tasks.instagram.InstagramService", return_value=ig_service), \
         patch("tasks.instagram._make_session_factory", return_value=factory):
        await _do_crawl(MagicMock(), str(source.id), "@testuser")

    result_repo.create.assert_not_called()
    source_repo.mark_crawled.assert_called_once()
