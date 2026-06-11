"""Shared access-context helpers for the multi-account (CRM) layer.

The JWT minted by service-user carries two dimensions: *who I am* (``sub``) and
*in which account I act, with which scopes* (``act_account`` + ``scopes``).
Business services use :func:`require_scope` to gate a route on a scope, then
filter their data by ``ctx.account_id`` — the scope authorizes the *action*,
``account_id`` bounds the *perimeter*.

Note: in the current increment the identity-level claims are still named
``user_admin`` / ``user_right`` (the ``platform_admin`` / ``capabilities``
rename is deferred), so this module reads those keys.
"""

from dataclasses import dataclass

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from nutri_shared.core.security import decode_token

__all__ = [
    "AccessContext",
    "parse_access_context",
    "get_access_context",
    "require_scope",
]

_bearer = HTTPBearer(auto_error=True)


@dataclass(frozen=True)
class AccessContext:
    """The access context decoded from a JWT of context."""

    sub: str
    account_id: str | None
    scopes: frozenset[str]
    user_admin: bool
    capabilities: dict
    role: str | None = None


def parse_access_context(payload: dict) -> AccessContext:
    """Build an :class:`AccessContext` from a decoded JWT payload."""
    return AccessContext(
        sub=str(payload.get("sub")),
        account_id=payload.get("act_account"),
        scopes=frozenset(payload.get("scopes") or []),
        user_admin=bool(payload.get("user_admin")),
        capabilities=payload.get("user_right") or {},
        role=payload.get("role"),
    )


async def get_access_context(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer),
) -> AccessContext:
    """Decode and validate the access token, returning its access context.

    Raises 401 if the token is missing, expired, or not an access token.
    """
    try:
        payload = decode_token(credentials.credentials)
        if payload.get("type") != "access" or not payload.get("sub"):
            raise ValueError("missing sub or wrong token type")
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return parse_access_context(payload)


def require_scope(scope: str):
    """FastAPI dependency factory gating a route on a given scope.

    * A platform admin (``user_admin``) bypasses the scope check (SAV / support;
      the action is meant to be audited at a later phase).
    * 403 if there is no active account context (token without ``act_account``).
    * 403 if the required scope is absent from the context.

    Returns the :class:`AccessContext` so the route can read ``ctx.account_id``.
    """

    async def _guard(
        ctx: AccessContext = Depends(get_access_context),
    ) -> AccessContext:
        if ctx.user_admin:
            return ctx
        if ctx.account_id is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No active account context",
            )
        if scope not in ctx.scopes:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Scope required: {scope}",
            )
        return ctx

    return _guard
