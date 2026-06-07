"""Tests for /auth/2fa/* endpoints."""

import pyotp
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import create_mfa_token, hash_password
from app.models.user import User
from app.services.crypto_service import CryptoService
from app.services.totp_service import TotpService


async def _make_user(
    session: AsyncSession,
    email: str = "mfa@test.com",
    two_factor_enabled: bool = False,
    two_factor_method: str | None = None,
    totp_secret_plain: str | None = None,
) -> User:
    """Insert a user into the test DB and return it."""
    user = User(
        email=email,
        hashed_password=hash_password("password123"),
        two_factor_enabled=two_factor_enabled,
        two_factor_method=two_factor_method,
    )
    if totp_secret_plain:
        user.totp_secret = CryptoService.encrypt(
            totp_secret_plain, settings.MFA_TOTP_ENCRYPTION_KEY
        )
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


@pytest.mark.unit
async def test_setup_totp_returns_provisioning_uri(
    auth_client: AsyncClient, db_session: AsyncSession
) -> None:
    """setup/totp stores an encrypted secret, returns an otpauth:// URI and a base64 QR code."""
    from conftest import TEST_USER_ID

    user = User(
        id=TEST_USER_ID,
        email="mfa@test.com",
        hashed_password=hash_password("password123"),
    )
    db_session.add(user)
    await db_session.commit()

    resp = await auth_client.post("/api/v1/auth/2fa/setup/totp")
    assert resp.status_code == 200
    body = resp.json()
    assert "provisioning_uri" in body
    assert body["provisioning_uri"].startswith("otpauth://totp/")
    # L'issuer affiché dans l'app d'authentification vient de la config.
    from app.core.config import settings

    assert f"issuer={settings.MFA_ISSUER}" in body["provisioning_uri"]
    assert "qr_code_base64" in body
    # Vérifie que c'est bien du base64 décodable en PNG
    import base64

    raw = base64.b64decode(body["qr_code_base64"])
    assert raw[:4] == b"\x89PNG", "La réponse n'est pas une image PNG valide"


@pytest.mark.unit
async def test_setup_totp_already_enabled_returns_409(
    auth_client: AsyncClient, db_session: AsyncSession
) -> None:
    """setup/totp when 2FA already enabled returns 409."""
    from conftest import TEST_USER_ID

    secret = TotpService.generate_secret()
    user = User(
        id=TEST_USER_ID,
        email="mfa@test.com",
        hashed_password=hash_password("password123"),
        two_factor_enabled=True,
        two_factor_method="totp",
        totp_secret=CryptoService.encrypt(secret, settings.MFA_TOTP_ENCRYPTION_KEY),
    )
    db_session.add(user)
    await db_session.commit()

    resp = await auth_client.post("/api/v1/auth/2fa/setup/totp")
    assert resp.status_code == 409


@pytest.mark.unit
async def test_confirm_totp_valid_code_enables_2fa(
    auth_client: AsyncClient, db_session: AsyncSession
) -> None:
    """confirm/totp with a valid code activates 2FA and returns tokens."""
    from conftest import TEST_USER_ID

    secret = TotpService.generate_secret()
    user = User(
        id=TEST_USER_ID,
        email="mfa@test.com",
        hashed_password=hash_password("password123"),
        totp_secret=CryptoService.encrypt(secret, settings.MFA_TOTP_ENCRYPTION_KEY),
    )
    db_session.add(user)
    await db_session.commit()

    code = pyotp.TOTP(secret).now()
    resp = await auth_client.post("/api/v1/auth/2fa/confirm/totp", json={"code": code})
    assert resp.status_code == 200
    body = resp.json()
    assert "access_token" in body
    assert "refresh_token" not in body  # SEC-05: refresh travels in the cookie
    assert "refresh_token=" in resp.headers.get("set-cookie", "")

    await db_session.refresh(user)
    assert user.two_factor_enabled is True
    assert user.two_factor_method == "totp"


@pytest.mark.unit
async def test_confirm_totp_invalid_code_returns_400(
    auth_client: AsyncClient, db_session: AsyncSession
) -> None:
    """confirm/totp with a wrong code returns 400."""
    from conftest import TEST_USER_ID

    secret = TotpService.generate_secret()
    user = User(
        id=TEST_USER_ID,
        email="mfa@test.com",
        hashed_password=hash_password("password123"),
        totp_secret=CryptoService.encrypt(secret, settings.MFA_TOTP_ENCRYPTION_KEY),
    )
    db_session.add(user)
    await db_session.commit()

    resp = await auth_client.post(
        "/api/v1/auth/2fa/confirm/totp", json={"code": "000000"}
    )
    assert resp.status_code == 400


@pytest.mark.unit
async def test_confirm_totp_no_secret_returns_400(
    auth_client: AsyncClient, db_session: AsyncSession
) -> None:
    """confirm/totp without a pending secret returns 400."""
    from conftest import TEST_USER_ID

    user = User(
        id=TEST_USER_ID,
        email="mfa@test.com",
        hashed_password=hash_password("password123"),
    )
    db_session.add(user)
    await db_session.commit()

    resp = await auth_client.post(
        "/api/v1/auth/2fa/confirm/totp", json={"code": "123456"}
    )
    assert resp.status_code == 400


@pytest.mark.unit
async def test_verify_mfa_totp_valid_code_returns_tokens(
    anon_client: AsyncClient, db_session: AsyncSession
) -> None:
    """verify with a valid TOTP code exchanges mfa_token for full tokens."""
    secret = TotpService.generate_secret()
    user = await _make_user(
        db_session,
        two_factor_enabled=True,
        two_factor_method="totp",
        totp_secret_plain=secret,
    )
    mfa_token = create_mfa_token(str(user.id))
    code = pyotp.TOTP(secret).now()

    resp = await anon_client.post(
        "/api/v1/auth/2fa/verify", json={"mfa_token": mfa_token, "code": code}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert "access_token" in body
    assert "refresh_token" not in body  # SEC-05: refresh travels in the cookie
    assert "refresh_token=" in resp.headers.get("set-cookie", "")


@pytest.mark.unit
async def test_verify_mfa_totp_invalid_code_returns_400(
    anon_client: AsyncClient, db_session: AsyncSession
) -> None:
    """verify with a wrong TOTP code returns 400."""
    secret = TotpService.generate_secret()
    user = await _make_user(
        db_session,
        two_factor_enabled=True,
        two_factor_method="totp",
        totp_secret_plain=secret,
    )
    mfa_token = create_mfa_token(str(user.id))

    resp = await anon_client.post(
        "/api/v1/auth/2fa/verify", json={"mfa_token": mfa_token, "code": "000000"}
    )
    assert resp.status_code == 400


@pytest.mark.unit
async def test_verify_mfa_invalid_token_returns_401(anon_client: AsyncClient) -> None:
    """verify with a garbage mfa_token returns 401."""
    resp = await anon_client.post(
        "/api/v1/auth/2fa/verify",
        json={"mfa_token": "bad.token.here", "code": "123456"},
    )
    assert resp.status_code == 401


@pytest.mark.unit
async def test_setup_email_2fa_enables_email_method(
    auth_client: AsyncClient, db_session: AsyncSession
) -> None:
    """setup/email enables 2FA with method='email'."""
    from conftest import TEST_USER_ID

    user = User(
        id=TEST_USER_ID,
        email="mfa@test.com",
        hashed_password=hash_password("password123"),
    )
    db_session.add(user)
    await db_session.commit()

    resp = await auth_client.post("/api/v1/auth/2fa/setup/email")
    assert resp.status_code == 204

    await db_session.refresh(user)
    assert user.two_factor_enabled is True
    assert user.two_factor_method == "email"


@pytest.mark.unit
async def test_disable_mfa_clears_2fa_fields(
    auth_client: AsyncClient, db_session: AsyncSession
) -> None:
    """disable clears two_factor_enabled, method, and totp_secret."""
    from conftest import TEST_USER_ID

    secret = TotpService.generate_secret()
    user = User(
        id=TEST_USER_ID,
        email="mfa@test.com",
        hashed_password=hash_password("password123"),
        two_factor_enabled=True,
        two_factor_method="totp",
        totp_secret=CryptoService.encrypt(secret, settings.MFA_TOTP_ENCRYPTION_KEY),
    )
    db_session.add(user)
    await db_session.commit()

    resp = await auth_client.delete("/api/v1/auth/2fa/disable")
    assert resp.status_code == 204

    await db_session.refresh(user)
    assert user.two_factor_enabled is False
    assert user.two_factor_method is None
    assert user.totp_secret is None


@pytest.mark.unit
async def test_disable_mfa_not_enabled_returns_400(
    auth_client: AsyncClient, db_session: AsyncSession
) -> None:
    """disable when 2FA is not active returns 400."""
    from conftest import TEST_USER_ID

    user = User(
        id=TEST_USER_ID,
        email="mfa@test.com",
        hashed_password=hash_password("password123"),
    )
    db_session.add(user)
    await db_session.commit()

    resp = await auth_client.delete("/api/v1/auth/2fa/disable")
    assert resp.status_code == 400


@pytest.mark.unit
def test_generate_qr_code_embeds_logo_by_default() -> None:
    """The QR PNG embeds the bundled brand logo, differing from a plain QR."""
    import base64

    uri = "otpauth://totp/Rost.r:user@test.com?secret=ABC123&issuer=Rost.r"

    with_logo = TotpService.generate_qr_code_base64(uri)
    # An unknown logo path falls back to a plain QR code.
    plain = TotpService.generate_qr_code_base64(uri, logo_path="/no/such/logo.png")

    assert base64.b64decode(with_logo)[:4] == b"\x89PNG"
    assert base64.b64decode(plain)[:4] == b"\x89PNG"
    # Embedding the logo changes the rendered image.
    assert with_logo != plain
