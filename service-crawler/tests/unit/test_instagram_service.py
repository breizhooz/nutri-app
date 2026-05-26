"""Tests unitaires — InstagramService."""

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import httpx
import instaloader.exceptions as il_exc
import pytest

from app.services.instagram_service import InstagramPost, InstagramService

# ─── Helpers ──────────────────────────────────────────────────────────────────

_TS_JUNE_1 = int(datetime(2024, 6, 1, 0, 0, 0, tzinfo=timezone.utc).timestamp())
_TS_JUNE_3 = int(datetime(2024, 6, 3, 0, 0, 0, tzinfo=timezone.utc).timestamp())
_TS_JUNE_5 = int(datetime(2024, 6, 5, 0, 0, 0, tzinfo=timezone.utc).timestamp())
_TS_MAY_30 = int(datetime(2024, 5, 30, 0, 0, 0, tzinfo=timezone.utc).timestamp())


def _photo_item(
    shortcode: str = "abc123",
    caption: str = "Test caption",
    taken_at: int = 1717243200,
    image_url: str = "https://cdn.ig.com/img.jpg",
) -> dict:
    return {
        "media_type": 1,
        "code": shortcode,
        "taken_at": taken_at,
        "caption": {"text": caption},
        "image_versions2": {
            "candidates": [{"url": image_url, "width": 1080, "height": 1080}]
        },
    }


def _video_item(
    shortcode: str = "vid01",
    caption: str = "Video caption",
    taken_at: int = 1717243200,
    image_url: str = "https://cdn.ig.com/thumb.jpg",
    video_url: str = "https://cdn.ig.com/video.mp4",
) -> dict:
    return {
        "media_type": 2,
        "code": shortcode,
        "taken_at": taken_at,
        "caption": {"text": caption},
        "image_versions2": {
            "candidates": [{"url": image_url, "width": 1080, "height": 1080}]
        },
        "video_versions": [{"url": video_url, "width": 1080, "height": 1080}],
    }


def _carousel_node(
    image_url: str,
    is_video: bool = False,
    video_url: str | None = None,
) -> dict:
    node: dict = {
        "media_type": 2 if is_video else 1,
        "image_versions2": {
            "candidates": [{"url": image_url, "width": 1080, "height": 1080}]
        },
    }
    if is_video and video_url:
        node["video_versions"] = [{"url": video_url, "width": 1080, "height": 1080}]
    return node


def _carousel_item(
    shortcode: str = "side01",
    caption: str = "Carousel caption",
    taken_at: int = 1717243200,
    nodes: list[dict] | None = None,
) -> dict:
    return {
        "media_type": 8,
        "code": shortcode,
        "taken_at": taken_at,
        "caption": {"text": caption},
        "carousel_media": nodes or [],
    }


# ─── normalize_account ────────────────────────────────────────────────────────


def test_normalize_account_strips_at_prefix():
    assert InstagramService.normalize_account("@johndoe") == "johndoe"


def test_normalize_account_without_at_unchanged():
    assert InstagramService.normalize_account("johndoe") == "johndoe"


def test_normalize_account_strips_multiple_at():
    assert InstagramService.normalize_account("@@johndoe") == "johndoe"


# ─── _ensure_session ──────────────────────────────────────────────────────────


def test_ensure_session_loads_existing_session():
    mock_loader = MagicMock()
    InstagramService._ensure_session(mock_loader, "user", "pass", "/tmp/session")
    mock_loader.load_session_from_file.assert_called_once_with("user", "/tmp/session")
    mock_loader.login.assert_not_called()


def test_ensure_session_logs_in_when_no_session_file():
    mock_loader = MagicMock()
    mock_loader.load_session_from_file.side_effect = FileNotFoundError
    InstagramService._ensure_session(mock_loader, "user", "pass", "/tmp/session")
    mock_loader.login.assert_called_once_with(user="user", passwd="pass")
    mock_loader.save_session_to_file.assert_called_once_with("/tmp/session")


def test_ensure_session_saves_after_login():
    mock_loader = MagicMock()
    mock_loader.load_session_from_file.side_effect = FileNotFoundError
    InstagramService._ensure_session(mock_loader, "user", "pass", "/tmp/s")
    assert mock_loader.save_session_to_file.call_count == 1


# ─── _make_authenticated_loader ───────────────────────────────────────────────


def test_make_authenticated_loader_calls_ensure_session_when_configured():
    with patch("app.services.instagram_service.settings") as mock_settings:
        mock_settings.INSTAGRAM_USERNAME = "mybot"
        mock_settings.INSTAGRAM_PASSWORD = "secret"
        mock_settings.INSTAGRAM_SESSION_FILE = "/data/session"
        with patch("app.services.instagram_service.instaloader.Instaloader") as mock_il:
            with patch.object(InstagramService, "_ensure_session") as mock_ensure:
                InstagramService._make_authenticated_loader()
            mock_ensure.assert_called_once_with(
                mock_il.return_value, "mybot", "secret", "/data/session"
            )


def test_make_authenticated_loader_skips_auth_when_no_username():
    with patch("app.services.instagram_service.settings") as mock_settings:
        mock_settings.INSTAGRAM_USERNAME = ""
        with patch("app.services.instagram_service.instaloader.Instaloader"):
            with patch.object(InstagramService, "_ensure_session") as mock_ensure:
                InstagramService._make_authenticated_loader()
            mock_ensure.assert_not_called()


# ─── _normalize_item ──────────────────────────────────────────────────────────


def test_normalize_item_photo():
    item = _photo_item(shortcode="img01", image_url="https://cdn.ig.com/img.jpg")
    result = InstagramService._normalize_item(item)
    assert result.shortcode == "img01"
    assert result.url == InstagramService.POST_URL.format(shortcode="img01")
    assert result.images == ["https://cdn.ig.com/img.jpg"]
    assert result.video_url is None


def test_normalize_item_video():
    item = _video_item(shortcode="vid01", video_url="https://cdn.ig.com/video.mp4")
    result = InstagramService._normalize_item(item)
    assert result.video_url == "https://cdn.ig.com/video.mp4"


def test_normalize_item_carousel_images_only():
    nodes = [
        _carousel_node("https://cdn.ig.com/img1.jpg"),
        _carousel_node("https://cdn.ig.com/img2.jpg"),
    ]
    item = _carousel_item(shortcode="side01", nodes=nodes)
    result = InstagramService._normalize_item(item)
    assert result.images == [
        "https://cdn.ig.com/img1.jpg",
        "https://cdn.ig.com/img2.jpg",
    ]
    assert result.video_url is None


def test_normalize_item_carousel_with_video_node():
    nodes = [
        _carousel_node("https://cdn.ig.com/img1.jpg"),
        _carousel_node(
            "https://cdn.ig.com/thumb.jpg",
            is_video=True,
            video_url="https://cdn.ig.com/vid.mp4",
        ),
    ]
    item = _carousel_item(shortcode="side02", nodes=nodes)
    result = InstagramService._normalize_item(item)
    assert result.video_url == "https://cdn.ig.com/vid.mp4"


def test_normalize_item_carousel_keeps_only_first_video_url():
    nodes = [
        _carousel_node("t1.jpg", is_video=True, video_url="https://cdn.ig.com/v1.mp4"),
        _carousel_node("t2.jpg", is_video=True, video_url="https://cdn.ig.com/v2.mp4"),
    ]
    item = _carousel_item(nodes=nodes)
    result = InstagramService._normalize_item(item)
    assert result.video_url == "https://cdn.ig.com/v1.mp4"


def test_normalize_item_title_uses_first_line_of_caption():
    item = _photo_item(caption="Première ligne\nDeuxième ligne")
    result = InstagramService._normalize_item(item)
    assert result.title == "Première ligne"


def test_normalize_item_long_caption_title_truncated_at_100():
    item = _photo_item(caption="A" * 150)
    result = InstagramService._normalize_item(item)
    assert result.title == "A" * 100


def test_normalize_item_null_caption_fallback_title():
    item = {
        "media_type": 1,
        "code": "xyz99",
        "taken_at": 1717243200,
        "caption": None,
        "image_versions2": {"candidates": [{"url": "https://cdn.ig.com/img.jpg"}]},
    }
    result = InstagramService._normalize_item(item)
    assert result.title == "Post xyz99"
    assert result.caption == ""


def test_normalize_item_missing_caption_fallback_title():
    item = {
        "media_type": 1,
        "code": "xyz98",
        "taken_at": 1717243200,
        "image_versions2": {"candidates": [{"url": "https://cdn.ig.com/img.jpg"}]},
    }
    result = InstagramService._normalize_item(item)
    assert result.title == "Post xyz98"


def test_normalize_item_images_capped_at_20():
    nodes = [_carousel_node(f"https://cdn.ig.com/img{i}.jpg") for i in range(25)]
    item = _carousel_item(nodes=nodes)
    result = InstagramService._normalize_item(item)
    assert len(result.images) == 20


def test_normalize_item_timestamp_is_utc_aware():
    item = _photo_item(taken_at=1710498600)
    result = InstagramService._normalize_item(item)
    assert result.timestamp.tzinfo == timezone.utc
    assert result.timestamp == datetime(2024, 3, 15, 10, 30, 0, tzinfo=timezone.utc)


# ─── fetch_posts ──────────────────────────────────────────────────────────────


def test_fetch_posts_returns_posts():
    service = InstagramService(loader=MagicMock())
    items = [_photo_item(shortcode=f"p{i}") for i in range(3)]
    with patch.object(service, "_resolve_user_id", return_value="12345"):
        with patch.object(service, "_get_media_count", return_value=3):
            with patch.object(service, "_fetch_page", return_value=(items, None)):
                result = service.fetch_posts("@testuser")
    assert len(result) == 3
    assert all(isinstance(p, InstagramPost) for p in result)


def test_fetch_posts_strips_at_from_username():
    service = InstagramService(loader=MagicMock())
    with patch.object(
        service, "_resolve_user_id", return_value="12345"
    ) as mock_resolve:
        with patch.object(service, "_fetch_page", return_value=([], None)):
            service.fetch_posts("@myaccount")
    mock_resolve.assert_called_once_with("myaccount")


def test_fetch_posts_empty_account_returns_empty():
    service = InstagramService(loader=MagicMock())
    with patch.object(service, "_resolve_user_id", return_value="12345"):
        with patch.object(service, "_fetch_page", return_value=([], None)):
            result = service.fetch_posts("emptyaccount")
    assert result == []


def test_fetch_posts_respects_max_posts():
    service = InstagramService(loader=MagicMock())
    items = [_photo_item(shortcode=f"p{i}") for i in range(10)]
    with patch.object(service, "_resolve_user_id", return_value="12345"):
        with patch.object(service, "_fetch_page", return_value=(items, None)):
            result = service.fetch_posts("account", max_posts=3)
    assert len(result) == 3


def test_fetch_posts_paginates_when_next_max_id():
    service = InstagramService(loader=MagicMock())
    page1 = [_photo_item(shortcode="p0")]
    page2 = [_photo_item(shortcode="p1")]
    with patch.object(service, "_resolve_user_id", return_value="12345"):
        with patch.object(
            service, "_fetch_page", side_effect=[(page1, "cursor123"), (page2, None)]
        ):
            result = service.fetch_posts("account", max_posts=50)
    assert len(result) == 2


def test_fetch_posts_propagates_resolve_error():
    service = InstagramService(loader=MagicMock())
    with patch.object(
        service, "_resolve_user_id", side_effect=ValueError("not found")
    ):
        with pytest.raises(ValueError):
            service.fetch_posts("notfound")


def test_fetch_posts_uses_media_count_when_max_posts_none():
    service = InstagramService(loader=MagicMock())
    items = [_photo_item(shortcode=f"p{i}") for i in range(5)]
    with patch.object(service, "_resolve_user_id", return_value="12345"):
        with patch.object(service, "_get_media_count", return_value=5) as mock_count:
            with patch.object(service, "_fetch_page", return_value=(items, None)):
                result = service.fetch_posts("account")
    mock_count.assert_called_once_with("12345")
    assert len(result) == 5


def test_fetch_posts_explicit_max_posts_skips_media_count():
    service = InstagramService(loader=MagicMock())
    items = [_photo_item(shortcode=f"p{i}") for i in range(3)]
    with patch.object(service, "_resolve_user_id", return_value="12345"):
        with patch.object(service, "_get_media_count") as mock_count:
            with patch.object(service, "_fetch_page", return_value=(items, None)):
                result = service.fetch_posts("account", max_posts=3)
    mock_count.assert_not_called()
    assert len(result) == 3


# ─── _get_media_count ─────────────────────────────────────────────────────────


def test_get_media_count_returns_count_from_api():
    service = InstagramService(loader=MagicMock())
    with patch.object(service, "_get", return_value={"user": {"media_count": 142}}):
        count = service._get_media_count("12345")
    assert count == 142


def test_get_media_count_fallback_when_missing():
    service = InstagramService(loader=MagicMock())
    with patch.object(service, "_get", return_value={"user": {}}):
        count = service._get_media_count("12345")
    assert count == 50


# ─── fetch_new_posts ──────────────────────────────────────────────────────────


def test_fetch_new_posts_returns_only_recent():
    since = datetime(2024, 6, 1, 0, 0, 0, tzinfo=timezone.utc)
    service = InstagramService(loader=MagicMock())
    items = [
        _photo_item(shortcode="new1", taken_at=_TS_JUNE_5),
        _photo_item(shortcode="new2", taken_at=_TS_JUNE_3),
        _photo_item(shortcode="old1", taken_at=_TS_MAY_30),
    ]
    with patch.object(service, "_resolve_user_id", return_value="12345"):
        with patch.object(service, "_fetch_page", return_value=(items, None)):
            result = service.fetch_new_posts("@testuser", since)
    assert len(result) == 2
    assert {p.shortcode for p in result} == {"new1", "new2"}


def test_fetch_new_posts_all_old_returns_empty():
    since = datetime(2024, 6, 1, 0, 0, 0, tzinfo=timezone.utc)
    service = InstagramService(loader=MagicMock())
    items = [_photo_item(shortcode="old1", taken_at=_TS_MAY_30)]
    with patch.object(service, "_resolve_user_id", return_value="12345"):
        with patch.object(service, "_fetch_page", return_value=(items, None)):
            result = service.fetch_new_posts("@testuser", since)
    assert result == []


def test_fetch_new_posts_all_new_returns_all():
    since = datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    service = InstagramService(loader=MagicMock())
    items = [_photo_item(shortcode=f"p{i}", taken_at=_TS_JUNE_5 + i) for i in range(3)]
    with patch.object(service, "_resolve_user_id", return_value="12345"):
        with patch.object(service, "_fetch_page", return_value=(items, None)):
            result = service.fetch_new_posts("@testuser", since)
    assert len(result) == 3
