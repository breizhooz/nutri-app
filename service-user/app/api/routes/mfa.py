"""2FA management routes: TOTP setup, confirmation, email setup, verify, disable."""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.deps import get_current_user, get_locale
from app.i18n.loader import t
from app.core.security import (
    create_access_token,
    create_refresh_token,
    verify_password,
)
from app.db.session import get_session
from app.models.mfa_pending_code import MfaPendingCode
from app.models.user import User
from app.schemas.auth import (
    MfaVerifyRequest,
    TotpConfirmRequest,
    TotpSetupResponse,
)
from app.schemas.user import TokenResponse
from app.services.crypto_service import CryptoService
from app.services.totp_service import TotpService
from app.services.user_service import UserService

router: APIRouter = APIRouter()


@router.post("/setup/totp", response_model=TotpSetupResponse)
async def setup_totp(
    request: Request,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> TotpSetupResponse:
    """Generate a TOTP secret, QR code and provisioning URI for the authenticated user.

    Does not activate 2FA yet — the user must confirm with a valid code via
    POST /auth/2fa/confirm/totp.

    Args:
        current_user: The authenticated user.
        session: Async database session.

    Returns:
        A TotpSetupResponse with the otpauth:// URI and a base64 PNG QR code.

    Raises:
        HTTPException: 409 if 2FA is already enabled.
    """
    if current_user.two_factor_enabled:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=t.get("mfa.already_enabled", get_locale(request)),
        )
    secret = TotpService.generate_secret()
    current_user.totp_secret = CryptoService.encrypt(
        secret, settings.MFA_TOTP_ENCRYPTION_KEY
    )
    session.add(current_user)
    await session.commit()

    uri = TotpService.get_provisioning_uri(secret, current_user.email)
    qr_base64 = TotpService.generate_qr_code_base64(uri)

    return TotpSetupResponse(
        provisioning_uri=uri,
        qr_code_base64=qr_base64,
    )


@router.post("/confirm/totp", response_model=TokenResponse)
async def confirm_totp(
    request: Request,
    data: TotpConfirmRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> TokenResponse:
    """Confirm TOTP setup by verifying the first authenticator code.

    Activates 2FA with method='totp' on the user account.

    Args:
        data: The 6-digit TOTP code from the authenticator app.
        current_user: The authenticated user.
        session: Async database session.

    Returns:
        A fresh TokenResponse (2FA is now active).

    Raises:
        HTTPException: 400 if no TOTP secret is pending or code is invalid.
        HTTPException: 409 if 2FA is already enabled.
    """
    if current_user.two_factor_enabled:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=t.get("mfa.already_enabled", get_locale(request)),
        )
    if not current_user.totp_secret:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=t.get("mfa.no_totp_setup", get_locale(request)),
        )
    secret = CryptoService.decrypt(
        current_user.totp_secret, settings.MFA_TOTP_ENCRYPTION_KEY
    )
    if not TotpService.verify_code(secret, data.code):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=t.get("mfa.invalid_totp", get_locale(request)),
        )
    current_user.two_factor_enabled = True
    current_user.two_factor_method = "totp"
    session.add(current_user)
    await session.commit()
    return TokenResponse(
        access_token=create_access_token(
            str(current_user.id), UserService.build_token_claims(current_user)
        ),
        refresh_token=create_refresh_token(str(current_user.id)),
    )


@router.post("/setup/email", status_code=status.HTTP_204_NO_CONTENT)
async def setup_email_2fa(
    request: Request,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> None:
    """Enable email-based 2FA for the authenticated user.

    Args:
        current_user: The authenticated user.
        session: Async database session.

    Raises:
        HTTPException: 409 if 2FA is already enabled.
    """
    if current_user.two_factor_enabled:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=t.get("mfa.already_enabled", get_locale(request)),
        )
    current_user.two_factor_enabled = True
    current_user.two_factor_method = "email"
    session.add(current_user)
    await session.commit()


@router.post("/verify", response_model=TokenResponse)
async def verify_mfa(
    request: Request,
    data: MfaVerifyRequest,
    session: AsyncSession = Depends(get_session),
) -> TokenResponse:
    """Verify a 2FA code and exchange the mfa_pending token for full tokens.

    Args:
        data: The mfa_token and OTP code.
        session: Async database session.

    Returns:
        Full TokenResponse (access + refresh tokens).

    Raises:
        HTTPException: 401 if the mfa_token is invalid.
        HTTPException: 400 if the OTP code is wrong or expired.
    """
    try:
        from app.core.security import decode_token

        payload = decode_token(data.mfa_token)
        if payload.get("type") != "mfa_pending":
            raise ValueError("Wrong token type")
        user_id_str: str = payload["sub"]
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=t.get("token.mfa_invalid_or_expired", get_locale(request)),
        )

    import uuid as _uuid

    result = await session.execute(
        select(User).where(User.id == _uuid.UUID(user_id_str))
    )
    user: User | None = result.scalar_one_or_none()
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=t.get("user.not_found_or_inactive", get_locale(request)),
        )

    if user.two_factor_method == "totp":
        if not user.totp_secret:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=t.get("mfa.totp_not_configured", get_locale(request)),
            )
        secret = CryptoService.decrypt(
            user.totp_secret, settings.MFA_TOTP_ENCRYPTION_KEY
        )
        if not TotpService.verify_code(secret, data.code):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=t.get("mfa.invalid_totp", get_locale(request)),
            )

    elif user.two_factor_method == "email":
        now = datetime.now(timezone.utc)
        code_result = await session.execute(
            select(MfaPendingCode)
            .where(MfaPendingCode.user_id == user.id)
            .where(MfaPendingCode.used_at.is_(None))
            .where(MfaPendingCode.expires_at > now)
            .order_by(MfaPendingCode.created_at.desc())
            .limit(1)
        )
        pending: MfaPendingCode | None = code_result.scalar_one_or_none()
        if not pending or not verify_password(data.code, pending.code_hash):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=t.get("mfa.invalid_email_code", get_locale(request)),
            )
        pending.used_at = now
        session.add(pending)
        await session.commit()

    return TokenResponse(
        access_token=create_access_token(
            str(user.id), UserService.build_token_claims(user)
        ),
        refresh_token=create_refresh_token(str(user.id)),
    )


@router.delete("/disable", status_code=status.HTTP_204_NO_CONTENT)
async def disable_mfa(
    request: Request,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> None:
    """Disable 2FA for the authenticated user.

    Args:
        current_user: The authenticated user.
        session: Async database session.

    Raises:
        HTTPException: 400 if 2FA is not currently enabled.
    """
    if not current_user.two_factor_enabled:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=t.get("mfa.not_enabled", get_locale(request)),
        )
    current_user.two_factor_enabled = False
    current_user.two_factor_method = None
    current_user.totp_secret = None
    session.add(current_user)
    await session.commit()
