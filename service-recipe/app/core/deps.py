from typing import Any

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jwt.exceptions import InvalidTokenError
from app.core.security import decode_token
from app.i18n.loader import t

bearer_scheme = HTTPBearer()


def get_locale(request: Request) -> str:
    """Locale resolved by LocaleMiddleware (defaults to 'fr')."""
    return getattr(getattr(request, "state", None), "locale", "fr")


async def get_token_payload(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
) -> dict[str, Any]:
    """Decode and validate the access token, returning its full payload.

    The payload carries RBAC claims (``user_admin``, ``user_right``) embedded
    by service-user, so this service can authorize locally.
    """
    try:
        payload = decode_token(credentials.credentials)
        token_type = payload.get("type")
        user_id: str | None = payload.get("sub")
        if not user_id or token_type != "access":  # nosec B105
            raise InvalidTokenError("missing sub or wrong token type")
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=t.get("auth.token_invalid", get_locale(request)),
            headers={"WWW-Authenticate": "Bearer"},
        )
    return payload


async def get_current_user_id(
    payload: dict[str, Any] = Depends(get_token_payload),
) -> str:
    return str(payload["sub"])


async def require_admin(
    request: Request,
    payload: dict[str, Any] = Depends(get_token_payload),
) -> dict[str, Any]:
    """Allow the request only if the access token carries the admin claim."""
    if not payload.get("user_admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=t.get("auth.admin_required", get_locale(request)),
        )
    return payload
