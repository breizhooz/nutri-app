from typing import Any

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jwt.exceptions import InvalidTokenError
from app.core.security import decode_token

bearer_scheme = HTTPBearer()


async def get_token_payload(
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
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return payload


async def get_current_user_id(
    payload: dict[str, Any] = Depends(get_token_payload),
) -> str:
    return str(payload["sub"])


async def require_admin(
    payload: dict[str, Any] = Depends(get_token_payload),
) -> dict[str, Any]:
    """Allow the request only if the access token carries the admin claim."""
    if not payload.get("user_admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required",
        )
    return payload
