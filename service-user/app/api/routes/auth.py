"""Authentication routes: login (with optional 2FA) and token refresh."""

import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
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
from app.schemas.user import RefreshRequest, TokenResponse, UserLogin
from app.repositories.user_repository import UserRepository
from app.services.notification_client import NotificationClient
from app.services.totp_service import CodeGenerator
from app.services.user_service import UserService

router: APIRouter = APIRouter()


@router.post(
    "/login",
    response_model=TokenResponse | PreAuthTokenResponse,
)
async def login(
    data: UserLogin,
    session: AsyncSession = Depends(get_session),
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
    result = await session.execute(select(User).where(User.email == data.email))
    user: User | None = result.scalar_one_or_none()

    if not user or not user.hashed_password:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
        )
    if not verify_password(data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Inactive user"
        )

    if not user.two_factor_enabled:
        return TokenResponse(
            access_token=create_access_token(
                str(user.id), UserService.build_token_claims(user)
            ),
            refresh_token=create_refresh_token(str(user.id)),
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
    data: RefreshRequest,
    session: AsyncSession = Depends(get_session),
) -> TokenResponse:
    """Issue a new token pair from a valid refresh token.

    The freshly minted access token re-embeds the user's current RBAC claims,
    so any rights change applies from the next refresh onward.

    Args:
        data: The refresh token payload.
        session: Async database session.

    Returns:
        A new TokenResponse with fresh access and refresh tokens.

    Raises:
        HTTPException: 401 if the token is invalid or not a refresh token.
    """
    try:
        payload = decode_token(data.refresh_token)
        if payload.get("type") != "refresh":
            raise ValueError("Invalid refresh token")
        user_id: str = payload["sub"]
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        )

    user = await UserRepository(session).get_by_id(uuid.UUID(user_id))
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        )

    return TokenResponse(
        access_token=create_access_token(user_id, UserService.build_token_claims(user)),
        refresh_token=create_refresh_token(user_id),
    )
