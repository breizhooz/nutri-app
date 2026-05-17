"""Tests unitaires — InstagramService (Phase 6)."""
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

import instaloader.exceptions as il_exc
from app.services.instagram_service import (
    INSTAGRAM_POST_URL,
    InstagramPost,
    InstagramService,
)


# ─── Helpers ──────────────────────────────────────────────────────────────────


class _MockSidecarNode:
    def __init__(
        self,
        display_url: str,
        is_video: bool = False,
        video_url: str | None = None,
    ):
        self.display_url = display_url
        self.is_video = is_video
        self.video_url = video_url


class _MockPost:
    def __init__(
        self,
        shortcode: str = "abc123",
        caption: str | None = "Test caption",
        url: str = "https://cdn.instagram.com/image.jpg",
        is_video: bool = False,
        video_url: str | None = None,
        typename: str = "GraphImage",
        date_utc: datetime | None = None,
        sidecar_nodes: list[_MockSidecarNode] | None = None,
    ):
        self.shortcode = shortcode
        self.caption = caption
        self.url = url
        self.is_video = is_video
        self.video_url = video_url
        self.typename = typename
        self.date_utc = date_utc or datetime(2024, 6, 1, 12, 0, 0)
        self._sidecar_nodes = sidecar_nodes or []

    def get_sidecar_nodes(self) -> list[_MockSidecarNode]:
        return self._sidecar_nodes


def _mock_profile(posts: list[_MockPost]) -> MagicMock:
    profile = MagicMock()
    profile.get_posts.return_value = posts
    return profile


# ─── normalize_account ────────────────────────────────────────────────────────


def test_normalize_account_strips_at_prefix():
    assert InstagramService.normalize_account("@johndoe") == "johndoe"


def test_normalize_account_without_at_unchanged():
    assert InstagramService.normalize_account("johndoe") == "johndoe"


def test_normalize_account_strips_multiple_at():
    assert InstagramService.normalize_account("@@johndoe") == "johndoe"


# ─── _normalize_post ──────────────────────────────────────────────────────────


def test_normalize_post_image_post():
    post = _MockPost(shortcode="img01", url="https://cdn.ig.com/img.jpg", is_video=False)
    result = InstagramService._normalize_post(post)

    assert result.shortcode == "img01"
    assert result.url == INSTAGRAM_POST_URL.format(shortcode="img01")
    assert result.images == ["https://cdn.ig.com/img.jpg"]
    assert result.video_url is None


def test_normalize_post_video_post():
    post = _MockPost(
        shortcode="vid01",
        url="https://cdn.ig.com/thumb.jpg",
        is_video=True,
        video_url="https://cdn.ig.com/video.mp4",
        typename="GraphVideo",
    )
    result = InstagramService._normalize_post(post)

    assert result.video_url == "https://cdn.ig.com/video.mp4"
    assert result.images == ["https://cdn.ig.com/thumb.jpg"]


def test_normalize_post_sidecar_images_only():
    nodes = [
        _MockSidecarNode("https://cdn.ig.com/img1.jpg"),
        _MockSidecarNode("https://cdn.ig.com/img2.jpg"),
    ]
    post = _MockPost(shortcode="side01", typename="GraphSidecar", sidecar_nodes=nodes)
    result = InstagramService._normalize_post(post)

    assert result.images == ["https://cdn.ig.com/img1.jpg", "https://cdn.ig.com/img2.jpg"]
    assert result.video_url is None


def test_normalize_post_sidecar_with_video_node():
    nodes = [
        _MockSidecarNode("https://cdn.ig.com/img1.jpg"),
        _MockSidecarNode(
            "https://cdn.ig.com/thumb.jpg",
            is_video=True,
            video_url="https://cdn.ig.com/vid.mp4",
        ),
    ]
    post = _MockPost(shortcode="side02", typename="GraphSidecar", sidecar_nodes=nodes)
    result = InstagramService._normalize_post(post)

    assert "https://cdn.ig.com/img1.jpg" in result.images
    assert "https://cdn.ig.com/thumb.jpg" in result.images
    assert result.video_url == "https://cdn.ig.com/vid.mp4"


def test_normalize_post_sidecar_keeps_only_first_video_url():
    """Seul le premier video_url du carousel est conservé."""
    nodes = [
        _MockSidecarNode("https://cdn.ig.com/t1.jpg", is_video=True, video_url="https://cdn.ig.com/v1.mp4"),
        _MockSidecarNode("https://cdn.ig.com/t2.jpg", is_video=True, video_url="https://cdn.ig.com/v2.mp4"),
    ]
    post = _MockPost(typename="GraphSidecar", sidecar_nodes=nodes)
    result = InstagramService._normalize_post(post)

    assert result.video_url == "https://cdn.ig.com/v1.mp4"


def test_normalize_post_title_uses_first_line_of_caption():
    post = _MockPost(caption="Première ligne\nDeuxième ligne\nTroisième ligne")
    result = InstagramService._normalize_post(post)

    assert result.title == "Première ligne"


def test_normalize_post_long_caption_title_truncated_at_100():
    post = _MockPost(caption="A" * 150)
    result = InstagramService._normalize_post(post)

    assert result.title == "A" * 100


def test_normalize_post_none_caption_fallback_title():
    post = _MockPost(shortcode="xyz99", caption=None)
    result = InstagramService._normalize_post(post)

    assert result.title == "Post xyz99"
    assert result.caption == ""


def test_normalize_post_empty_string_caption_fallback_title():
    post = _MockPost(shortcode="xyz98", caption="")
    result = InstagramService._normalize_post(post)

    assert result.title == "Post xyz98"


def test_normalize_post_images_capped_at_20():
    nodes = [_MockSidecarNode(f"https://cdn.ig.com/img{i}.jpg") for i in range(25)]
    post = _MockPost(typename="GraphSidecar", sidecar_nodes=nodes)
    result = InstagramService._normalize_post(post)

    assert len(result.images) == 20


def test_normalize_post_timestamp_is_utc_aware():
    post = _MockPost(date_utc=datetime(2024, 3, 15, 10, 30, 0))
    result = InstagramService._normalize_post(post)

    assert result.timestamp.tzinfo == timezone.utc
    assert result.timestamp.year == 2024
    assert result.timestamp.month == 3


# ─── fetch_posts ──────────────────────────────────────────────────────────────


def test_fetch_posts_returns_all_posts():
    posts = [_MockPost(shortcode=f"p{i}") for i in range(3)]
    profile = _mock_profile(posts)

    with patch(
        "app.services.instagram_service.instaloader.Profile.from_username",
        return_value=profile,
    ):
        result = InstagramService(loader=MagicMock()).fetch_posts("@testuser")

    assert len(result) == 3
    assert all(isinstance(p, InstagramPost) for p in result)


def test_fetch_posts_strips_at_from_username():
    profile = _mock_profile([])

    with patch(
        "app.services.instagram_service.instaloader.Profile.from_username",
        return_value=profile,
    ) as mock_fn:
        InstagramService(loader=MagicMock()).fetch_posts("@myaccount")

    _, called_username = mock_fn.call_args[0]
    assert called_username == "myaccount"


def test_fetch_posts_empty_account_returns_empty():
    profile = _mock_profile([])

    with patch(
        "app.services.instagram_service.instaloader.Profile.from_username",
        return_value=profile,
    ):
        result = InstagramService(loader=MagicMock()).fetch_posts("emptyaccount")

    assert result == []


def test_fetch_posts_propagates_profile_not_found():
    with patch(
        "app.services.instagram_service.instaloader.Profile.from_username",
        side_effect=il_exc.ProfileNotExistsException("notfound"),
    ):
        with pytest.raises(il_exc.ProfileNotExistsException):
            InstagramService(loader=MagicMock()).fetch_posts("notfound")


# ─── fetch_new_posts ──────────────────────────────────────────────────────────


def test_fetch_new_posts_returns_only_recent():
    since = datetime(2024, 6, 1, 0, 0, 0, tzinfo=timezone.utc)
    posts = [
        _MockPost(shortcode="new1", date_utc=datetime(2024, 6, 5, 0, 0, 0)),
        _MockPost(shortcode="new2", date_utc=datetime(2024, 6, 3, 0, 0, 0)),
        _MockPost(shortcode="old1", date_utc=datetime(2024, 5, 30, 0, 0, 0)),
        _MockPost(shortcode="old2", date_utc=datetime(2024, 5, 20, 0, 0, 0)),
    ]
    profile = _mock_profile(posts)

    with patch(
        "app.services.instagram_service.instaloader.Profile.from_username",
        return_value=profile,
    ):
        result = InstagramService(loader=MagicMock()).fetch_new_posts("@testuser", since)

    assert len(result) == 2
    assert {p.shortcode for p in result} == {"new1", "new2"}


def test_fetch_new_posts_all_old_returns_empty():
    since = datetime(2024, 6, 1, 0, 0, 0, tzinfo=timezone.utc)
    posts = [_MockPost(date_utc=datetime(2024, 5, 1, 0, 0, 0))]
    profile = _mock_profile(posts)

    with patch(
        "app.services.instagram_service.instaloader.Profile.from_username",
        return_value=profile,
    ):
        result = InstagramService(loader=MagicMock()).fetch_new_posts("@testuser", since)

    assert result == []


def test_fetch_new_posts_all_new_returns_all():
    since = datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    posts = [
        _MockPost(shortcode=f"p{i}", date_utc=datetime(2024, 6, i + 1, 0, 0, 0))
        for i in range(3)
    ]
    profile = _mock_profile(posts)

    with patch(
        "app.services.instagram_service.instaloader.Profile.from_username",
        return_value=profile,
    ):
        result = InstagramService(loader=MagicMock()).fetch_new_posts("@testuser", since)

    assert len(result) == 3
