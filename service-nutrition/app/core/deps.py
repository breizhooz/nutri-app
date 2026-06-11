import uuid

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
import jwt
from jwt.exceptions import InvalidTokenError

from nutri_shared.core.context import AccessContext, require_scope

from app.core.config import settings
from app.i18n.loader import t

_bearer = HTTPBearer(auto_error=False)
_bearer_service = HTTPBearer()


# ── Multicomptes : contexte de compte + gardes de scope ──────────────────────
# Les macro_errors découlent des recettes : on les borne par le compte actif et
# on réutilise le scope recipe:read / recipe:write.


def _account_id(ctx: AccessContext) -> uuid.UUID:
    if ctx.account_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=t.get("errors.forbidden"),
        )
    return uuid.UUID(ctx.account_id)


async def get_read_account_id(
    ctx: AccessContext = Depends(require_scope("recipe:read")),
) -> uuid.UUID:
    """Compte actif pour une lecture (scope recipe:read requis)."""
    return _account_id(ctx)


async def get_write_account_id(
    ctx: AccessContext = Depends(require_scope("recipe:write")),
) -> uuid.UUID:
    """Compte actif pour une écriture (scope recipe:write requis)."""
    return _account_id(ctx)


async def get_current_user_id(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> uuid.UUID:
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=t.get("errors.unauthenticated"),
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        payload = jwt.decode(
            credentials.credentials,
            settings.JWT_SECRET,
            algorithms=[settings.JWT_ALGORITHM],
        )
        user_id: str | None = payload.get("sub")
        if not user_id:
            raise ValueError("sub manquant")
        return uuid.UUID(user_id)
    except (InvalidTokenError, ValueError, Exception):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=t.get("errors.token_invalid"),
            headers={"WWW-Authenticate": "Bearer"},
        )


async def verify_service_token(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer_service),
) -> None:
    if not settings.SERVICE_NUTRITION_TOKEN:
        return
    if credentials.credentials != settings.SERVICE_NUTRITION_TOKEN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=t.get("errors.service_token_invalid"),
        )
