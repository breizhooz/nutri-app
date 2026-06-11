from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jwt.exceptions import InvalidTokenError

from nutri_shared.core.context import AccessContext, require_scope

from app.core.security import decode_token
from app.i18n.exceptions import LocalizedHTTPException
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


# ── Multicomptes : contexte de compte + gardes de scope (plan:*) ─────────────
# Les menus (plans) sont bornés par le compte actif (act_account du JWT). Le
# scope autorise l'action ; account_id borne le périmètre (cf. docs/roles/).


def _account_id(request: Request, ctx: AccessContext) -> str:
    """Extrait l'identifiant du compte actif. 403 si le token n'a pas de contexte."""
    if ctx.account_id is None:
        raise LocalizedHTTPException.menu_unauthorized(request)
    return ctx.account_id


async def get_read_account_id(
    request: Request,
    ctx: AccessContext = Depends(require_scope("plan:read")),
) -> str:
    """Compte actif pour une lecture de menu (scope plan:read requis)."""
    return _account_id(request, ctx)


async def get_write_account_id(
    request: Request,
    ctx: AccessContext = Depends(require_scope("plan:write")),
) -> str:
    """Compte actif pour une écriture de menu (scope plan:write requis)."""
    return _account_id(request, ctx)


async def get_write_context(
    request: Request,
    ctx: AccessContext = Depends(require_scope("plan:write")),
) -> AccessContext:
    """Contexte complet pour une écriture (compte + identité auteur)."""
    _account_id(request, ctx)  # 403 si pas de compte actif
    return ctx
