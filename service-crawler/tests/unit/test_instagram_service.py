"""Tests unitaires — InstagramService (pagination GraphQL via instaloader)."""

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from app.services.instagram_service import InstagramPost, InstagramService

# ─── Helpers ──────────────────────────────────────────────────────────────────


def _post(
    shortcode: str = "abc123",
    caption: str | None = "Test caption",
    typename: str = "GraphImage",
    url: str = "https://cdn.ig.com/img.jpg",
    is_video: bool = False,
    video_url: str | None = None,
    date_utc: datetime | None = None,
    sidecar: list | None = None,
) -> MagicMock:
    """Construit un faux ``instaloader.Post``."""
    post = MagicMock()
    post.shortcode = shortcode
    post.caption = caption
    post.typename = typename
    post.url = url
    post.is_video = is_video
    post.video_url = video_url
    post.date_utc = date_utc if date_utc is not None else datetime(2024, 6, 1, 0, 0, 0)
    post.get_sidecar_nodes.return_value = sidecar if sidecar is not None else []
    return post


def _node(
    display_url: str, is_video: bool = False, video_url: str | None = None
) -> MagicMock:
    node = MagicMock()
    node.display_url = display_url
    node.is_video = is_video
    node.video_url = video_url
    return node


def _profile_with(posts: list) -> MagicMock:
    profile = MagicMock()
    profile.get_posts.return_value = iter(posts)
    return profile


# ─── normalize_account ────────────────────────────────────────────────────────


def test_normalize_account_strips_at_prefix():
    assert InstagramService.normalize_account("@johndoe") == "johndoe"


def test_normalize_account_without_at_unchanged():
    assert InstagramService.normalize_account("johndoe") == "johndoe"


def test_normalize_account_strips_multiple_at():
    assert InstagramService.normalize_account("@@johndoe") == "johndoe"


# ─── shortcode_from_url ───────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "url,expected",
    [
        ("https://www.instagram.com/p/Cabc123/", "Cabc123"),
        ("https://instagram.com/reel/Dxy_Z9/", "Dxy_Z9"),
        ("http://www.instagram.com/tv/Ee12/?utm=x", "Ee12"),
        ("instagram.com/p/Short", "Short"),
        ("https://unblog.com/recette/curry", None),
        ("https://www.instagram.com/joladiete/", None),  # profil, pas un post
        ("", None),
    ],
)
def test_shortcode_from_url(url, expected):
    assert InstagramService.shortcode_from_url(url) == expected


# ─── fetch_post ───────────────────────────────────────────────────────────────


def test_fetch_post_normalizes_single_post():
    service = InstagramService(loader=MagicMock())
    fake = _post(shortcode="Cabc123", caption="Recette")
    with patch(
        "app.services.instagram_service.instaloader.Post.from_shortcode",
        return_value=fake,
    ) as mock_from:
        result = service.fetch_post("Cabc123")
    mock_from.assert_called_once()
    assert isinstance(result, InstagramPost)
    assert result.shortcode == "Cabc123"
    assert result.url == InstagramService.POST_URL.format(shortcode="Cabc123")


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


# ─── _normalize_post ──────────────────────────────────────────────────────────


def test_normalize_post_photo():
    result = InstagramService._normalize_post(
        _post(shortcode="img01", url="https://cdn.ig.com/img.jpg")
    )
    assert result.shortcode == "img01"
    assert result.url == InstagramService.POST_URL.format(shortcode="img01")
    assert result.images == ["https://cdn.ig.com/img.jpg"]
    assert result.video_url is None


def test_normalize_post_video():
    result = InstagramService._normalize_post(
        _post(
            shortcode="vid01",
            typename="GraphVideo",
            url="https://cdn.ig.com/thumb.jpg",
            is_video=True,
            video_url="https://cdn.ig.com/video.mp4",
        )
    )
    assert result.images == ["https://cdn.ig.com/thumb.jpg"]
    assert result.video_url == "https://cdn.ig.com/video.mp4"


def test_normalize_post_carousel_images_only():
    result = InstagramService._normalize_post(
        _post(
            typename="GraphSidecar",
            sidecar=[
                _node("https://cdn.ig.com/img1.jpg"),
                _node("https://cdn.ig.com/img2.jpg"),
            ],
        )
    )
    assert result.images == [
        "https://cdn.ig.com/img1.jpg",
        "https://cdn.ig.com/img2.jpg",
    ]
    assert result.video_url is None


def test_normalize_post_carousel_with_video_node():
    result = InstagramService._normalize_post(
        _post(
            typename="GraphSidecar",
            sidecar=[
                _node("https://cdn.ig.com/img1.jpg"),
                _node(
                    "https://cdn.ig.com/thumb.jpg",
                    is_video=True,
                    video_url="https://cdn.ig.com/vid.mp4",
                ),
            ],
        )
    )
    assert result.video_url == "https://cdn.ig.com/vid.mp4"


def test_normalize_post_carousel_keeps_only_first_video_url():
    result = InstagramService._normalize_post(
        _post(
            typename="GraphSidecar",
            sidecar=[
                _node("t1.jpg", is_video=True, video_url="https://cdn.ig.com/v1.mp4"),
                _node("t2.jpg", is_video=True, video_url="https://cdn.ig.com/v2.mp4"),
            ],
        )
    )
    assert result.video_url == "https://cdn.ig.com/v1.mp4"


def test_normalize_post_title_uses_first_line_of_caption():
    result = InstagramService._normalize_post(
        _post(caption="Première ligne\nDeuxième ligne")
    )
    assert result.title == "Première ligne"


def test_normalize_post_long_caption_title_truncated_at_100():
    result = InstagramService._normalize_post(_post(caption="A" * 150))
    assert result.title == "A" * 100


def test_normalize_post_null_caption_fallback_title():
    result = InstagramService._normalize_post(_post(shortcode="xyz99", caption=None))
    assert result.title == "Post xyz99"
    assert result.caption == ""


def test_normalize_post_images_capped_at_20():
    result = InstagramService._normalize_post(
        _post(
            typename="GraphSidecar",
            sidecar=[_node(f"https://cdn.ig.com/img{i}.jpg") for i in range(25)],
        )
    )
    assert len(result.images) == 20


def test_normalize_post_timestamp_is_utc_aware():
    result = InstagramService._normalize_post(
        _post(date_utc=datetime(2024, 3, 15, 10, 30, 0))  # naïf → UTC
    )
    assert result.timestamp.tzinfo == timezone.utc
    assert result.timestamp == datetime(2024, 3, 15, 10, 30, 0, tzinfo=timezone.utc)


# ─── fetch_posts ──────────────────────────────────────────────────────────────


def test_fetch_posts_returns_posts():
    service = InstagramService(loader=MagicMock())
    posts = [_post(shortcode=f"p{i}") for i in range(3)]
    with patch.object(service, "_profile", return_value=_profile_with(posts)):
        result = service.fetch_posts("@testuser")
    assert len(result) == 3
    assert all(isinstance(p, InstagramPost) for p in result)


def test_fetch_posts_strips_at_from_username():
    service = InstagramService(loader=MagicMock())
    with patch.object(
        service, "_profile", return_value=_profile_with([])
    ) as mock_profile:
        service.fetch_posts("@myaccount")
    mock_profile.assert_called_once_with("myaccount")


def test_fetch_posts_empty_account_returns_empty():
    service = InstagramService(loader=MagicMock())
    with patch.object(service, "_profile", return_value=_profile_with([])):
        result = service.fetch_posts("emptyaccount")
    assert result == []


def test_fetch_posts_respects_max_posts():
    service = InstagramService(loader=MagicMock())
    posts = [_post(shortcode=f"p{i}") for i in range(10)]
    with patch.object(service, "_profile", return_value=_profile_with(posts)):
        result = service.fetch_posts("account", max_posts=3)
    assert len(result) == 3


def test_fetch_posts_paginates_beyond_100():
    """Régression du plafond ~100 : l'itérateur GraphQL renvoie tout."""
    service = InstagramService(loader=MagicMock())
    posts = [_post(shortcode=f"p{i}") for i in range(150)]
    with patch.object(service, "_profile", return_value=_profile_with(posts)):
        result = service.fetch_posts("account")
    assert len(result) == 150


def test_fetch_posts_propagates_profile_error():
    service = InstagramService(loader=MagicMock())
    with patch.object(service, "_profile", side_effect=ValueError("not found")):
        with pytest.raises(ValueError):
            service.fetch_posts("notfound")


def test_fetch_posts_throttles_every_page_size():
    service = InstagramService(loader=MagicMock())
    posts = [_post(shortcode=f"p{i}") for i in range(100)]
    sleeps: list[float] = []
    with patch(
        "app.services.instagram_service.time.sleep", lambda d: sleeps.append(d)
    ):
        with patch.object(service, "_profile", return_value=_profile_with(posts)):
            service.fetch_posts("account", page_delay=2.0, page_size=50)
    assert sleeps == [2.0, 2.0]  # toutes les 50 sur 100 posts


def test_fetch_posts_no_throttle_by_default():
    service = InstagramService(loader=MagicMock())
    posts = [_post(shortcode=f"p{i}") for i in range(60)]
    sleeps: list[float] = []
    with patch(
        "app.services.instagram_service.time.sleep", lambda d: sleeps.append(d)
    ):
        with patch.object(service, "_profile", return_value=_profile_with(posts)):
            service.fetch_posts("account")  # page_delay=0 par défaut
    assert sleeps == []


# ─── fetch_new_posts ──────────────────────────────────────────────────────────


def test_fetch_new_posts_returns_only_recent():
    since = datetime(2024, 6, 1, 0, 0, 0, tzinfo=timezone.utc)
    service = InstagramService(loader=MagicMock())
    posts = [
        _post(shortcode="new1", date_utc=datetime(2024, 6, 5)),
        _post(shortcode="new2", date_utc=datetime(2024, 6, 3)),
        _post(shortcode="old1", date_utc=datetime(2024, 5, 30)),
    ]
    with patch.object(service, "_profile", return_value=_profile_with(posts)):
        result = service.fetch_new_posts("@testuser", since)
    assert {p.shortcode for p in result} == {"new1", "new2"}


def test_fetch_new_posts_all_old_returns_empty():
    since = datetime(2024, 6, 1, 0, 0, 0, tzinfo=timezone.utc)
    service = InstagramService(loader=MagicMock())
    posts = [_post(shortcode="old1", date_utc=datetime(2024, 5, 30))]
    with patch.object(service, "_profile", return_value=_profile_with(posts)):
        result = service.fetch_new_posts("@testuser", since)
    assert result == []


def test_fetch_new_posts_all_new_returns_all():
    since = datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    service = InstagramService(loader=MagicMock())
    posts = [_post(shortcode=f"p{i}", date_utc=datetime(2024, 6, 5)) for i in range(3)]
    with patch.object(service, "_profile", return_value=_profile_with(posts)):
        result = service.fetch_new_posts("@testuser", since)
    assert len(result) == 3
