"""FastAPI injectable dependencies for authentication."""

import uuid

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from nutri_shared.core.context import AccessContext, get_access_context

from app.core.security import decode_token
from app.db.session import get_session
from app.i18n.loader import t
from app.models.user import User

_bearer_scheme: HTTPBearer = HTTPBearer()
_bearer_mfa: HTTPBearer = HTTPBearer()


def get_locale(request: Request) -> str:
    """Extrait la locale depuis le state injecté par LocaleMiddleware."""
    return getattr(getattr(request, "state", None), "locale", "fr")


async def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(_bearer_scheme),
    session: AsyncSession = Depends(get_session),
) -> User:
    """Validate an access JWT and return the corresponding active user.

    Args:
        request: Incoming request (used to resolve the locale).
        credentials: Bearer credentials from the Authorization header.
        session: Async database session.

    Returns:
        The authenticated User ORM instance.

    Raises:
        HTTPException: 401 if the token is invalid, 404 if the user is not
            found, 400 if the user account is inactive.
    """
    locale = get_locale(request)
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
            detail=t.get("token.invalid_or_expired", locale),
            headers={"WWW-Authenticate": "Bearer"},
        )

    result = await session.execute(select(User).where(User.id == uuid.UUID(user_id)))
    user: User | None = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=t.get("user.not_found", locale),
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=t.get("user.inactive", locale),
        )

    return user


async def require_account_manager(
    account_id: uuid.UUID,
    request: Request,
    ctx: AccessContext = Depends(get_access_context),
) -> AccessContext:
    """Garde des routes de gestion de membres (multicomptes, phase 3).

    Exige le scope ``member:manage`` ET que le compte actif du token de contexte
    soit bien celui du chemin (on ne gère que les membres de son compte actif).
    Un ``platform_admin`` (SAV) court-circuite mais l'action reste auditée.
    """
    if ctx.user_admin:
        return ctx
    if "member:manage" not in ctx.scopes or ctx.account_id != str(account_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=t.get("accounts.manage_forbidden", get_locale(request)),
        )
    return ctx


async def get_current_admin(
    request: Request,
    current_user: User = Depends(get_current_user),
) -> User:
    """Return the current user only if they hold admin privileges.

    Raises:
        HTTPException: 403 if the authenticated user is not an admin.
    """
    if not current_user.user_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=t.get("auth.admin_required", get_locale(request)),
        )
    return current_user


async def get_mfa_pending_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(_bearer_mfa),
    session: AsyncSession = Depends(get_session),
) -> User:
    """Validate an mfa_pending JWT and return the user awaiting 2FA.

    This dependency is used exclusively by the /auth/2fa/verify endpoint.

    Args:
        request: Incoming request (used to resolve the locale).
        credentials: Bearer credentials containing the mfa_pending token.
        session: Async database session.

    Returns:
        The User ORM instance that must complete 2FA.

    Raises:
        HTTPException: 401 if the token is invalid or not of type mfa_pending.
    """
    locale = get_locale(request)
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
            detail=t.get("token.mfa_invalid_or_expired", locale),
            headers={"WWW-Authenticate": "Bearer"},
        )

    result = await session.execute(select(User).where(User.id == uuid.UUID(user_id)))
    user: User | None = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=t.get("user.not_found", locale),
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=t.get("user.inactive", locale),
        )

    return user


async def get_mfa_user_id_from_token(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(_bearer_mfa),
) -> uuid.UUID:
    """Extract the user UUID from an mfa_pending JWT without a DB query.

    Args:
        request: Incoming request (used to resolve the locale).
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
            detail=t.get("token.mfa_invalid_or_expired", get_locale(request)),
            headers={"WWW-Authenticate": "Bearer"},
        )
