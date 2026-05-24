"""Tests for OAuthService (pure unit — no HTTP, no DB)."""

from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from app.services.oauth_service import OAuthService


# ── is_valid_provider ──────────────────────────────────────────────────────────


@pytest.mark.unit
def test_is_valid_provider_google() -> None:
    assert OAuthService.is_valid_provider("google") is True


@pytest.mark.unit
def test_is_valid_provider_facebook() -> None:
    assert OAuthService.is_valid_provider("facebook") is True


@pytest.mark.unit
def test_is_valid_provider_unknown_returns_false() -> None:
    assert OAuthService.is_valid_provider("twitter") is False


# ── build_authorization_url ────────────────────────────────────────────────────


@pytest.mark.unit
def test_build_authorization_url_google_contains_required_params() -> None:
    url = OAuthService.build_authorization_url("google", "cid", "http://cb", "state42")
    assert "accounts.google.com" in url
    assert "client_id=cid" in url
    assert "state=state42" in url
    assert "access_type=offline" in url
    assert "prompt=consent" in url
    assert "response_type=code" in url


@pytest.mark.unit
def test_build_authorization_url_facebook_no_offline_params() -> None:
    url = OAuthService.build_authorization_url(
        "facebook", "cid", "http://cb", "state42"
    )
    assert "facebook.com" in url
    assert "access_type" not in url
    assert "prompt" not in url


@pytest.mark.unit
def test_build_authorization_url_includes_redirect_uri() -> None:
    url = OAuthService.build_authorization_url(
        "google", "cid", "http://localhost/cb", "st"
    )
    assert "redirect_uri=" in url


# ── exchange_code ──────────────────────────────────────────────────────────────


@pytest.mark.unit
async def test_exchange_code_returns_token_dict() -> None:
    mock_resp = MagicMock()
    mock_resp.json = MagicMock(return_value={"access_token": "at123"})
    mock_resp.raise_for_status = MagicMock()
    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=mock_resp)

    result = await OAuthService.exchange_code(
        "google", "cid", "csec", "http://cb", "code99", http_client=mock_client
    )

    assert result == {"access_token": "at123"}
    mock_client.post.assert_called_once()


@pytest.mark.unit
async def test_exchange_code_posts_to_token_url() -> None:
    mock_resp = MagicMock()
    mock_resp.json = MagicMock(return_value={"access_token": "x"})
    mock_resp.raise_for_status = MagicMock()
    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=mock_resp)

    await OAuthService.exchange_code(
        "google", "cid", "csec", "http://cb", "code", http_client=mock_client
    )

    url_called = mock_client.post.call_args.args[0]
    assert "oauth2.googleapis.com" in url_called


@pytest.mark.unit
async def test_exchange_code_raises_on_http_error() -> None:
    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock(
        side_effect=httpx.HTTPStatusError(
            "401", request=MagicMock(), response=MagicMock()
        )
    )
    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=mock_resp)

    with pytest.raises(httpx.HTTPStatusError):
        await OAuthService.exchange_code(
            "google", "cid", "csec", "http://cb", "bad-code", http_client=mock_client
        )


# ── fetch_user_info ────────────────────────────────────────────────────────────


@pytest.mark.unit
async def test_fetch_user_info_google_returns_profile() -> None:
    mock_resp = MagicMock()
    mock_resp.json = MagicMock(return_value={"sub": "uid123", "email": "g@g.com"})
    mock_resp.raise_for_status = MagicMock()
    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_resp)

    result = await OAuthService.fetch_user_info(
        "google", "access-token", http_client=mock_client
    )

    assert result["sub"] == "uid123"
    assert result["email"] == "g@g.com"
    headers_sent = mock_client.get.call_args.kwargs["headers"]
    assert headers_sent["Authorization"] == "Bearer access-token"


@pytest.mark.unit
async def test_fetch_user_info_facebook_calls_correct_url() -> None:
    mock_resp = MagicMock()
    mock_resp.json = MagicMock(return_value={"id": "fb42", "email": "fb@fb.com"})
    mock_resp.raise_for_status = MagicMock()
    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_resp)

    await OAuthService.fetch_user_info("facebook", "tok", http_client=mock_client)

    url_called = mock_client.get.call_args.args[0]
    assert "graph.facebook.com" in url_called


@pytest.mark.unit
async def test_fetch_user_info_raises_on_http_error() -> None:
    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock(
        side_effect=httpx.HTTPStatusError(
            "403", request=MagicMock(), response=MagicMock()
        )
    )
    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_resp)

    with pytest.raises(httpx.HTTPStatusError):
        await OAuthService.fetch_user_info(
            "google", "bad-token", http_client=mock_client
        )


# ── extract_user_info ──────────────────────────────────────────────────────────


@pytest.mark.unit
def test_extract_user_info_google() -> None:
    uid, email = OAuthService.extract_user_info(
        "google", {"sub": "g-123", "email": "g@g.com"}
    )
    assert uid == "g-123"
    assert email == "g@g.com"


@pytest.mark.unit
def test_extract_user_info_google_email_optional() -> None:
    uid, email = OAuthService.extract_user_info("google", {"sub": "g-456"})
    assert uid == "g-456"
    assert email is None


@pytest.mark.unit
def test_extract_user_info_facebook() -> None:
    uid, email = OAuthService.extract_user_info(
        "facebook", {"id": "fb-99", "email": "fb@fb.com"}
    )
    assert uid == "fb-99"
    assert email == "fb@fb.com"


@pytest.mark.unit
def test_extract_user_info_unknown_raises_value_error() -> None:
    with pytest.raises(ValueError, match="Unsupported"):
        OAuthService.extract_user_info("twitter", {"id": "x"})
