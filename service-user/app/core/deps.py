"""FastAPI injectable dependencies for authentication."""

import uuid

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import decode_token
from app.db.session import get_session
from app.models.user import User

_bearer_scheme: HTTPBearer = HTTPBearer()
_bearer_mfa: HTTPBearer = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer_scheme),
    session: AsyncSession = Depends(get_session),
) -> User:
    """Validate an access JWT and return the corresponding active user.

    Args:
        credentials: Bearer credentials from the Authorization header.
        session: Async database session.

    Returns:
        The authenticated User ORM instance.

    Raises:
        HTTPException: 401 if the token is invalid, 404 if the user is not
            found, 400 if the user account is inactive.
    """
    try:
        payload = decode_token(credentials.credentials)
        user_id: str | None = payload.get("sub")
        if not user_id:
            raise ValueError("sub missing in token")
        if payload.get("type") != "access":
            raise ValueError("Not an access token")
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    result = await session.execute(select(User).where(User.id == user_id))
    user: User | None = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Inactive user")

    return user


async def get_mfa_pending_user(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer_mfa),
    session: AsyncSession = Depends(get_session),
) -> User:
    """Validate an mfa_pending JWT and return the user awaiting 2FA.

    This dependency is used exclusively by the /auth/2fa/verify endpoint.

    Args:
        credentials: Bearer credentials containing the mfa_pending token.
        session: Async database session.

    Returns:
        The User ORM instance that must complete 2FA.

    Raises:
        HTTPException: 401 if the token is invalid or not of type mfa_pending.
    """
    try:
        payload = decode_token(credentials.credentials)
        if payload.get("type") != "mfa_pending":
            raise ValueError("Not an mfa_pending token")
        user_id: str | None = payload.get("sub")
        if not user_id:
            raise ValueError("sub missing in token")
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired MFA token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    result = await session.execute(select(User).where(User.id == user_id))
    user: User | None = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Inactive user")

    return user


async def get_mfa_user_id_from_token(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer_mfa),
) -> uuid.UUID:
    """Extract the user UUID from an mfa_pending JWT without a DB query.

    Args:
        credentials: Bearer credentials containing the mfa_pending token.

    Returns:
        The user UUID embedded in the token.

    Raises:
        HTTPException: 401 if the token is invalid or has the wrong type.
    """
    try:
        payload = decode_token(credentials.credentials)
        if payload.get("type") != "mfa_pending":
            raise ValueError("Not an mfa_pending token")
        user_id_str: str | None = payload.get("sub")
        if not user_id_str:
            raise ValueError("sub missing")
        return uuid.UUID(user_id_str)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired MFA token",
            headers={"WWW-Authenticate": "Bearer"},
        )