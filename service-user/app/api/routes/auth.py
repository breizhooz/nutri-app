"""Authentication routes: login (with optional 2FA) and token refresh."""

import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.cookies import clear_refresh_cookie, set_refresh_cookie
from app.core.deps import get_locale
from app.core.rate_limit import login_rate_limit
from app.i18n.loader import t
from app.core.security import (
    create_access_token,
    create_mfa_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.db.session import get_session
from app.models.mfa_pending_code import MfaPendingCode
from app.models.user import User
from app.schemas.auth import PreAuthTokenResponse
from app.schemas.user import TokenResponse, UserLogin
from app.repositories.user_repository import UserRepository
from app.services.access_service import AccessService
from app.services.notification_client import NotificationClient
from app.services.totp_service import CodeGenerator

router: APIRouter = APIRouter()


@router.post(
    "/login",
    response_model=TokenResponse | PreAuthTokenResponse,
)
async def login(
    request: Request,
    data: UserLogin,
    response: Response,
    session: AsyncSession = Depends(get_session),
    _rate_limit: None = Depends(login_rate_limit),  # SEC-07
) -> TokenResponse | PreAuthTokenResponse:
    """Authenticate a user with email and password.

    If 2FA is not enabled, returns a full TokenResponse immediately.
    If 2FA is enabled, returns a PreAuthTokenResponse and (for email method)
    dispatches the OTP code via the notification service.

    Args:
        data: Login credentials.
        session: Async database session.

    Returns:
        TokenResponse if 2FA is disabled, PreAuthTokenResponse otherwise.

    Raises:
        HTTPException: 401 if credentials are invalid, 400 if user is inactive.
    """
    locale = get_locale(request)
    result = await session.execute(select(User).where(User.email == data.email))
    user: User | None = result.scalar_one_or_none()

    if not user or not user.hashed_password:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=t.get("auth.invalid_credentials", locale),
        )
    if not verify_password(data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=t.get("auth.invalid_credentials", locale),
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=t.get("user.inactive", locale),
        )

    if not user.two_factor_enabled:
        set_refresh_cookie(response, create_refresh_token(str(user.id)))
        claims = await AccessService(session).build_login_claims(user)
        return TokenResponse(
            access_token=create_access_token(str(user.id), claims),
        )

    mfa_token = create_mfa_token(str(user.id))

    if user.two_factor_method == "email":
        code = CodeGenerator.generate_otp()
        pending = MfaPendingCode(
            user_id=user.id,
            code_hash=hash_password(code),
            expires_at=datetime.now(timezone.utc)
            + timedelta(minutes=settings.MFA_EMAIL_CODE_EXPIRE_MINUTES),
        )
        session.add(pending)
        await session.commit()
        await NotificationClient.send_mfa_code(
            user_id=str(user.id),
            code=code,
            recipient_email=user.email,
            notification_url=settings.NOTIFICATION_SERVICE_URL,
            notification_token=settings.NOTIFICATION_SERVICE_TOKEN,
        )

    return PreAuthTokenResponse(
        mfa_token=mfa_token,
        mfa_method=user.two_factor_method or "totp",
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh(
    request: Request,
    response: Response,
    session: AsyncSession = Depends(get_session),
) -> TokenResponse:
    """Issue a fresh access token from the refresh-token cookie (SEC-05).

    The refresh token is read from the HttpOnly cookie (never the body) and is
    rotated: a new refresh cookie is set on every call. The freshly minted access
    token re-embeds the user's current RBAC claims, so any rights change applies
    from the next refresh onward.

    Args:
        request: Incoming request (carries the refresh cookie + locale).
        response: Response used to set the rotated refresh cookie.
        session: Async database session.

    Returns:
        A TokenResponse with a fresh access token (refresh travels in the cookie).

    Raises:
        HTTPException: 401 if the cookie is missing, invalid, or not a refresh token.
    """
    locale = get_locale(request)
    token = request.cookies.get(settings.REFRESH_COOKIE_NAME)
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=t.get("token.refresh_invalid_or_expired", locale),
        )
    try:
        payload = decode_token(token)
        if payload.get("type") != "refresh":
            raise ValueError("Invalid refresh token")
        user_id: str = payload["sub"]
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=t.get("token.refresh_invalid_or_expired", locale),
        )

    user = await UserRepository(session).get_by_id(uuid.UUID(user_id))
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=t.get("token.refresh_invalid_or_expired", locale),
        )

    set_refresh_cookie(response, create_refresh_token(user_id))
    claims = await AccessService(session).build_login_claims(user)
    return TokenResponse(
        access_token=create_access_token(user_id, claims),
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(response: Response) -> None:
    """Log out by clearing the refresh-token cookie (SEC-05).

    Stateless: the access token simply expires (no server-side blacklist).

    Args:
        response: Response used to clear the refresh cookie.
    """
    clear_refresh_cookie(response)
