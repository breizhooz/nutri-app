"""Helpers for the refresh-token cookie (SEC-05).

The refresh token is delivered as an HttpOnly cookie so it is unreachable from
JavaScript (no localStorage), neutralising XSS exfiltration of long-lived tokens.
Attributes are centralised here so set/clear stay symmetric — a delete only works
if path/domain match the original set_cookie.
"""

from fastapi import Response

from app.core.config import settings


def set_refresh_cookie(response: Response, token: str) -> None:
    """Attach the refresh token as an HttpOnly cookie on the response.

    Args:
        response: The FastAPI response to mutate.
        token: The signed refresh JWT to store.
    """
    response.set_cookie(
        key=settings.REFRESH_COOKIE_NAME,
        value=token,
        max_age=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS * 86400,
        path=settings.REFRESH_COOKIE_PATH,
        domain=settings.COOKIE_DOMAIN,
        httponly=True,
        secure=settings.COOKIE_SECURE,
        samesite=settings.COOKIE_SAMESITE,  # type: ignore[arg-type]
    )


def clear_refresh_cookie(response: Response) -> None:
    """Remove the refresh-token cookie (logout / invalid refresh).

    Path and domain must mirror :func:`set_refresh_cookie`, otherwise the browser
    keeps the original cookie.

    Args:
        response: The FastAPI response to mutate.
    """
    response.delete_cookie(
        key=settings.REFRESH_COOKIE_NAME,
        path=settings.REFRESH_COOKIE_PATH,
        domain=settings.COOKIE_DOMAIN,
        httponly=True,
        secure=settings.COOKIE_SECURE,
        samesite=settings.COOKIE_SAMESITE,  # type: ignore[arg-type]
    )
