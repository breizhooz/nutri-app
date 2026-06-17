from typing import Any

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jwt.exceptions import InvalidTokenError

from dataclasses import dataclass

from nutri_shared.core.context import AccessContext, parse_access_context, require_scope

from app.core.config import settings
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


# ── Multicomptes : contexte de compte + gardes de scope (recipe:*) ───────────
# Les recettes sont privées par compte (option 2 : act_account du JWT). Le scope
# autorise l'action ; account_id borne le périmètre (cf. docs/roles/).


def _account_id(ctx: AccessContext) -> str:
    """Extrait l'identifiant du compte actif. 403 si le token n'a pas de contexte."""
    if ctx.account_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No active account context",
        )
    return ctx.account_id


async def get_read_account_id(
    ctx: AccessContext = Depends(require_scope("recipe:read")),
) -> str:
    """Compte actif pour une lecture de recette (scope recipe:read requis)."""
    return _account_id(ctx)


async def get_write_account_id(
    ctx: AccessContext = Depends(require_scope("recipe:write")),
) -> str:
    """Compte actif pour une écriture de recette (scope recipe:write requis)."""
    return _account_id(ctx)


async def get_read_context(
    ctx: AccessContext = Depends(require_scope("recipe:read")),
) -> AccessContext:
    """Contexte complet pour une lecture (compte + identité).

    Utilisé par la recherche : les recettes sont filtrées par compte, mais les
    règles nutritionnelles restent résolues par identité (dossier profile).
    """
    _account_id(ctx)  # 403 si pas de compte actif
    return ctx


async def get_write_context(
    ctx: AccessContext = Depends(require_scope("recipe:write")),
) -> AccessContext:
    """Contexte complet pour une écriture (compte + identité auteur)."""
    _account_id(ctx)  # 403 si pas de compte actif
    return ctx


# ── Dual-auth (user OU service de confiance) pour les endpoints inter-services ─
# POST /recipe (crawler) et PUT /id (front + crawler/commit) sont appelés à la
# fois par des users (token de contexte) et par des services de confiance
# (crawler/import via SERVICE_RECIPE_TOKEN). Pour le service de confiance,
# l'appartenance au compte est résolue par l'appelant (compte de
# created_by_user_id pour la création ; compte de la recette pour l'update).


def is_trusted_service(token: str) -> bool:
    """Vrai si le Bearer correspond au secret de service de confiance configuré."""
    return (
        bool(settings.SERVICE_RECIPE_TOKEN) and token == settings.SERVICE_RECIPE_TOKEN
    )


@dataclass(frozen=True)
class WriteAuth:
    """Résultat de l'authentification d'une écriture (user ou service)."""

    trusted: bool
    account_id: str | None  # None pour un service de confiance (résolu en aval)
    sub: str | None  # identité auteur (None pour un service de confiance)


async def get_write_auth(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
) -> WriteAuth:
    """Auth d'écriture acceptant un token de contexte OU le service de confiance."""
    token = credentials.credentials
    if is_trusted_service(token):
        return WriteAuth(trusted=True, account_id=None, sub=None)

    try:
        payload = decode_token(token)
        if payload.get("type") != "access" or not payload.get("sub"):
            raise InvalidTokenError("missing sub or wrong token type")
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=t.get("auth.token_invalid", get_locale(request)),
            headers={"WWW-Authenticate": "Bearer"},
        )

    ctx: AccessContext = parse_access_context(payload)
    if not ctx.user_admin and "recipe:write" not in ctx.scopes:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Scope required: recipe:write"
        )
    if ctx.account_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="No active account context"
        )
    return WriteAuth(trusted=False, account_id=ctx.account_id, sub=ctx.sub)
