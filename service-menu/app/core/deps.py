from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jwt.exceptions import InvalidTokenError

from app.core.security import decode_token
from app.i18n.loader import t

bearer_scheme = HTTPBearer()


def get_locale(request: Request) -> str:
    """Locale resolved by LocaleMiddleware (defaults to 'fr')."""
    return getattr(getattr(request, "state", None), "locale", "fr")


async def get_current_user_id(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
) -> str:
    try:
        payload = decode_token(credentials.credentials)
        token_type = payload.get("type")
        user_id: str | None = payload.get("sub")
        if not user_id or token_type != "access":  # nosec B105
            raise InvalidTokenError("missing sub or wrong token type")
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=t.get("errors.token_invalid", get_locale(request)),
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user_id
