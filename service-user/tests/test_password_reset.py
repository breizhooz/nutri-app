"""Tests for the password reset workflow.

Covers:
- PasswordResetService (token creation, validation, history check, update)
- NotificationClient.send_password_reset_email
- POST /api/v1/auth/password/reset-request
- POST /api/v1/auth/password/reset
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.security import hash_password
from app.models.password_history import PasswordHistory
from app.models.password_reset_token import PasswordResetToken
from app.models.user import User
from app.services.notification_client import NotificationClient
from app.services.password_reset_service import PasswordResetService


async def _make_user(
    session, email="reset@test.com", password="OldPass1!", is_active=True
):
    user = User(
        email=email, hashed_password=hash_password(password), is_active=is_active
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


def _mock_httpx(status_code):
    mock_resp = MagicMock()
    mock_resp.status_code = status_code
    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=mock_resp)
    mock_cls = MagicMock()
    mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
    mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
    return mock_cls


# --- PasswordResetService ---


@pytest.mark.unit
async def test_hash_token_is_deterministic():
    h1 = PasswordResetService._hash_token("abc")
    h2 = PasswordResetService._hash_token("abc")
    assert h1 == h2 and len(h1) == 64


@pytest.mark.unit
async def test_generate_plain_token_is_nonempty():
    assert len(PasswordResetService._generate_plain_token()) >= 32


@pytest.mark.unit
async def test_create_reset_token_persists_and_returns_plain(db_session):
    user = await _make_user(db_session)
    plain = await PasswordResetService(db_session).create_reset_token(user, 30)
    from sqlalchemy import select

    row = (
        await db_session.execute(
            select(PasswordResetToken).where(
                PasswordResetToken.token_hash == PasswordResetService._hash_token(plain)
            )
        )
    ).scalar_one_or_none()
    assert row is not None and row.used_at is None


@pytest.mark.unit
async def test_validate_and_consume_token_success(db_session):
    user = await _make_user(db_session)
    plain = await PasswordResetService(db_session).create_reset_token(user, 30)
    returned = await PasswordResetService(db_session).validate_and_consume_token(plain)
    assert returned.id == user.id


@pytest.mark.unit
async def test_validate_and_consume_token_invalid_raises(db_session):
    with pytest.raises(ValueError, match="Invalid"):
        await PasswordResetService(db_session).validate_and_consume_token("bad-token")


@pytest.mark.unit
async def test_validate_and_consume_token_expired_raises(db_session):
    user = await _make_user(db_session)
    token_str = "expiredtoken12345"
    db_session.add(
        PasswordResetToken(
            user_id=user.id,
            token_hash=PasswordResetService._hash_token(token_str),
            expires_at=datetime.now(timezone.utc) - timedelta(hours=1),
        )
    )
    await db_session.commit()
    with pytest.raises(ValueError):
        await PasswordResetService(db_session).validate_and_consume_token(token_str)


@pytest.mark.unit
async def test_validate_and_consume_token_already_used_raises(db_session):
    user = await _make_user(db_session)
    token_str = "usedtoken12345678"
    db_session.add(
        PasswordResetToken(
            user_id=user.id,
            token_hash=PasswordResetService._hash_token(token_str),
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
            used_at=datetime.now(timezone.utc),
        )
    )
    await db_session.commit()
    with pytest.raises(ValueError):
        await PasswordResetService(db_session).validate_and_consume_token(token_str)


@pytest.mark.unit
async def test_is_password_reused_matches_current(db_session):
    user = await _make_user(db_session, password="CurrentPass1!")
    assert (
        await PasswordResetService(db_session).is_password_reused(user, "CurrentPass1!")
        is True
    )


@pytest.mark.unit
async def test_is_password_reused_matches_history(db_session):
    user = await _make_user(db_session, password="CurrentPass1!")
    db_session.add(
        PasswordHistory(user_id=user.id, hashed_password=hash_password("OldPass2!"))
    )
    await db_session.commit()
    assert (
        await PasswordResetService(db_session).is_password_reused(user, "OldPass2!")
        is True
    )


@pytest.mark.unit
async def test_is_password_reused_no_match(db_session):
    user = await _make_user(db_session, password="CurrentPass1!")
    assert (
        await PasswordResetService(db_session).is_password_reused(
            user, "BrandNewPass2!"
        )
        is False
    )


@pytest.mark.unit
async def test_is_password_reused_no_current_password(db_session):
    user = User(email="oauth@test.com", hashed_password=None, is_active=True)
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    assert (
        await PasswordResetService(db_session).is_password_reused(user, "AnyPass1!")
        is False
    )


@pytest.mark.unit
async def test_is_password_reused_ignores_beyond_history_count(db_session):
    user = await _make_user(db_session, password="CurrentPass1!")
    for i in range(4):
        db_session.add(
            PasswordHistory(
                user_id=user.id, hashed_password=hash_password(f"OldPass{i}!")
            )
        )
    db_session.add(
        PasswordHistory(user_id=user.id, hashed_password=hash_password("VeryOldPass6!"))
    )
    await db_session.commit()
    assert (
        await PasswordResetService(db_session).is_password_reused(
            user, "VeryOldPass6!", history_count=5
        )
        is False
    )


@pytest.mark.unit
async def test_update_password_changes_hash_and_archives_old(db_session):
    user = await _make_user(db_session, password="InitialPass1!")
    old_hash = user.hashed_password
    await PasswordResetService(db_session).update_password(user, "NewPass2!")
    await db_session.refresh(user)
    assert user.hashed_password != old_hash
    from sqlalchemy import select

    history = (
        (
            await db_session.execute(
                select(PasswordHistory).where(PasswordHistory.user_id == user.id)
            )
        )
        .scalars()
        .all()
    )
    assert len(history) == 1 and history[0].hashed_password == old_hash


@pytest.mark.unit
async def test_update_password_no_existing_password_skips_history(db_session):
    user = User(email="newuser@test.com", hashed_password=None, is_active=True)
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    await PasswordResetService(db_session).update_password(user, "NewPass1!")
    await db_session.refresh(user)
    assert user.hashed_password is not None
    from sqlalchemy import select

    assert (
        await db_session.execute(
            select(PasswordHistory).where(PasswordHistory.user_id == user.id)
        )
    ).scalars().all() == []


# --- NotificationClient ---


@pytest.mark.unit
async def test_send_password_reset_email_200_returns_true():
    with patch("httpx.AsyncClient", _mock_httpx(200)):
        assert (
            await NotificationClient.send_password_reset_email(
                "uid", "u@t.com", "http://reset?token=x", "http://notif", "tok"
            )
            is True
        )


@pytest.mark.unit
async def test_send_password_reset_email_400_returns_false():
    with patch("httpx.AsyncClient", _mock_httpx(400)):
        assert (
            await NotificationClient.send_password_reset_email(
                "uid", "u@t.com", "http://reset?token=x", "http://notif", "tok"
            )
            is False
        )


@pytest.mark.unit
async def test_send_password_reset_email_network_error_returns_false():
    mock_cls = MagicMock()
    mock_cls.return_value.__aenter__ = AsyncMock(side_effect=Exception("refused"))
    mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
    with patch("httpx.AsyncClient", mock_cls):
        assert (
            await NotificationClient.send_password_reset_email(
                "uid", "u@t.com", "http://reset?token=x", "http://notif", "tok"
            )
            is False
        )


@pytest.mark.unit
async def test_send_password_reset_email_payload():
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=mock_resp)
    mock_cls = MagicMock()
    mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
    mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
    with patch("httpx.AsyncClient", mock_cls):
        await NotificationClient.send_password_reset_email(
            "uid-99", "u@b.com", "http://app/reset?token=XYZ", "http://svc", "mytoken"
        )
    call = mock_client.post.call_args
    assert call.kwargs["json"]["type"] == "password_reset"
    assert call.kwargs["json"]["data"]["reset_url"] == "http://app/reset?token=XYZ"
    assert call.kwargs["headers"]["Authorization"] == "Bearer mytoken"


# --- Routes ---


@pytest.mark.unit
async def test_reset_request_known_email_returns_202(anon_client, db_session):
    await _make_user(db_session)
    with patch(
        "app.api.routes.password.NotificationClient.send_password_reset_email",
        new_callable=AsyncMock,
        return_value=True,
    ):
        resp = await anon_client.post(
            "/api/v1/auth/password/reset-request", json={"email": "reset@test.com"}
        )
    assert resp.status_code == 202


@pytest.mark.unit
async def test_reset_request_unknown_email_still_returns_202(anon_client):
    resp = await anon_client.post(
        "/api/v1/auth/password/reset-request", json={"email": "nobody@test.com"}
    )
    assert resp.status_code == 202


@pytest.mark.unit
async def test_reset_request_inactive_user_no_email_sent(anon_client, db_session):
    await _make_user(db_session, is_active=False)
    with patch(
        "app.api.routes.password.NotificationClient.send_password_reset_email",
        new_callable=AsyncMock,
        return_value=True,
    ) as mock_send:
        await anon_client.post(
            "/api/v1/auth/password/reset-request", json={"email": "reset@test.com"}
        )
    mock_send.assert_not_called()


@pytest.mark.unit
async def test_reset_request_invalid_email_returns_422(anon_client):
    resp = await anon_client.post(
        "/api/v1/auth/password/reset-request", json={"email": "not-an-email"}
    )
    assert resp.status_code == 422


@pytest.mark.unit
async def test_reset_confirm_success(anon_client, db_session):
    user = await _make_user(db_session, password="OldPass1!")
    plain = await PasswordResetService(db_session).create_reset_token(user, 30)
    resp = await anon_client.post(
        "/api/v1/auth/password/reset",
        json={"token": plain, "new_password": "BrandNew2!"},
    )
    assert resp.status_code == 200


@pytest.mark.unit
async def test_reset_confirm_invalid_token_returns_400(anon_client):
    resp = await anon_client.post(
        "/api/v1/auth/password/reset",
        json={"token": "invalid", "new_password": "NewPass1!"},
    )
    assert resp.status_code == 400


@pytest.mark.unit
async def test_reset_confirm_password_reuse_returns_409(anon_client, db_session):
    user = await _make_user(db_session, password="SamePass1!")
    plain = await PasswordResetService(db_session).create_reset_token(user, 30)
    resp = await anon_client.post(
        "/api/v1/auth/password/reset",
        json={"token": plain, "new_password": "SamePass1!"},
    )
    assert resp.status_code == 409


@pytest.mark.unit
async def test_reset_confirm_weak_password_returns_422(anon_client, db_session):
    user = await _make_user(db_session)
    plain = await PasswordResetService(db_session).create_reset_token(user, 30)
    resp = await anon_client.post(
        "/api/v1/auth/password/reset", json={"token": plain, "new_password": "short"}
    )
    assert resp.status_code == 422


@pytest.mark.unit
async def test_reset_confirm_token_consumed_after_use(anon_client, db_session):
    user = await _make_user(db_session, password="OldPass1!")
    plain = await PasswordResetService(db_session).create_reset_token(user, 30)
    await anon_client.post(
        "/api/v1/auth/password/reset",
        json={"token": plain, "new_password": "NewPass99!"},
    )
    resp = await anon_client.post(
        "/api/v1/auth/password/reset",
        json={"token": plain, "new_password": "AnotherPass!"},
    )
    assert resp.status_code == 400
