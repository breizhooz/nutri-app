from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jwt.exceptions import InvalidTokenError
from app.core.security import decode_token

bearer_scheme = HTTPBearer()


async def get_current_user_id(
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
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user_id
