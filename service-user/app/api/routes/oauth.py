"""OAuth2 social login routes for Google and Facebook."""

import logging
import uuid
from urllib.parse import quote, urlencode

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.cookies import set_refresh_cookie
from app.core.deps import get_locale
from app.i18n.loader import t
from app.core.security import (
    create_access_token,
    create_mfa_token,
    create_oauth_bootstrap_token,
    create_oauth_state,
    create_refresh_token,
    verify_oauth_bootstrap_token,
    verify_oauth_state,
)
from app.db.session import get_session
from app.models.oauth_account import OAuthAccount
from app.models.user import User
from app.repositories.user_repository import UserRepository
from app.schemas.auth import OAuthBootstrapRequest
from app.schemas.user import TokenResponse
from app.services.oauth_service import OAuthService
from app.services.user_service import UserService

logger: logging.Logger = logging.getLogger(__name__)

router: APIRouter = APIRouter()


def _front_callback_url(**params: str) -> str:
    """Build the front-end OAuth landing URL, optionally with query params.

    Args:
        **params: Query parameters to append (e.g. mfa_token, error).

    Returns:
        The absolute front-end callback URL.
    """
    base = f"{settings.FRONTEND_URL}/oauth/callback"
    return f"{base}?{urlencode(params)}" if params else base


def _error_redirect(message: str) -> RedirectResponse:
    """Redirect to the front-end callback with an error message (SEC-05).

    The callback now navigates the browser, so failures must surface as a
    front-end redirect rather than a raw JSON HTTPException.

    Args:
        message: The localized error message to display.

    Returns:
        A 302 redirect carrying the error in the query string.
    """
    return RedirectResponse(
        url=f"{settings.FRONTEND_URL}/oauth/callback?error={quote(message)}",
        status_code=302,
    )

_CLIENT_IDS: dict[str, str] = {
    "google": settings.GOOGLE_CLIENT_ID,
    "facebook": settings.FACEBOOK_CLIENT_ID,
}
_CLIENT_SECRETS: dict[str, str] = {
    "google": settings.GOOGLE_CLIENT_SECRET,
    "facebook": settings.FACEBOOK_CLIENT_SECRET,
}


def _redirect_uri(provider: str) -> str:
    """Build the OAuth2 callback URL for the given provider.

    Args:
        provider: The OAuth2 provider name.

    Returns:
        The full callback URL string.
    """
    return f"{settings.OAUTH_REDIRECT_BASE_URL}/api/v1/auth/oauth/{provider}/callback"


@router.get("/{provider}/authorize")
async def oauth_authorize(request: Request, provider: str) -> RedirectResponse:
    """Redirect the user to the OAuth2 provider authorization page.

    Args:
        provider: 'google' or 'facebook'.

    Returns:
        A 302 redirect to the provider's authorization URL.

    Raises:
        HTTPException: 400 if the provider is not supported.
    """
    if not OAuthService.is_valid_provider(provider):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=t.get(
                "oauth.unsupported_provider", get_locale(request), provider=provider
            ),
        )
    state = create_oauth_state(provider)
    url = OAuthService.build_authorization_url(
        provider=provider,
        client_id=_CLIENT_IDS[provider],
        redirect_uri=_redirect_uri(provider),
        state=state,
    )
    return RedirectResponse(url=url, status_code=302)


@router.get("/{provider}/callback")
async def oauth_callback(
    request: Request,
    provider: str,
    code: str = Query(...),
    state: str = Query(...),
    session: AsyncSession = Depends(get_session),
) -> RedirectResponse:
    """Handle the OAuth2 provider callback and redirect to the front (SEC-05).

    Validates the state JWT, exchanges the authorization code for provider
    tokens, fetches the user profile, then creates or links the account.

    The browser is navigated here, so the outcome is always a 302 redirect to
    the front-end callback page:
      - success (no 2FA): refresh token set as an HttpOnly cookie, no token in
        the URL — the front bootstraps its access token via /auth/refresh;
      - 2FA enabled: redirect with ?mfa_token & ?mfa_method;
      - failure: redirect with ?error.

    Args:
        provider: 'google' or 'facebook'.
        code: The authorization code from the provider.
        state: The CSRF state JWT generated at authorize time.
        session: Async database session.

    Returns:
        A 302 RedirectResponse to the front-end callback page.
    """
    locale = get_locale(request)
    if not OAuthService.is_valid_provider(provider):
        return _error_redirect(
            t.get("oauth.unsupported_provider", locale, provider=provider)
        )
    try:
        state_provider = verify_oauth_state(state)
        if state_provider != provider:
            raise ValueError("Provider mismatch in state")
    except ValueError:
        return _error_redirect(t.get("oauth.invalid_state", locale))

    try:
        token_data = await OAuthService.exchange_code(
            provider=provider,
            client_id=_CLIENT_IDS[provider],
            client_secret=_CLIENT_SECRETS[provider],
            redirect_uri=_redirect_uri(provider),
            code=code,
        )
        raw_user = await OAuthService.fetch_user_info(
            provider=provider,
            access_token=token_data["access_token"],
        )
    except httpx.HTTPStatusError as exc:
        # Provider rejected the token exchange / userinfo call: the real reason
        # (invalid_client, redirect_uri_mismatch, …) is in the response body.
        logger.exception(
            "OAuth2 %s call failed for provider %s (status=%s, redirect_uri=%s): %s",
            exc.request.url,
            provider,
            exc.response.status_code,
            _redirect_uri(provider),
            exc.response.text,
        )
        return _error_redirect(t.get("oauth.userinfo_failed", locale))
    except Exception:
        logger.exception(
            "OAuth2 code exchange / userinfo failed for provider %s "
            "(redirect_uri=%s)",
            provider,
            _redirect_uri(provider),
        )
        return _error_redirect(t.get("oauth.userinfo_failed", locale))

    provider_user_id, provider_email = OAuthService.extract_user_info(
        provider, raw_user
    )
    if not provider_email:
        return _error_redirect(t.get("oauth.no_email", locale))

    # Look for existing OAuth account link
    link_result = await session.execute(
        select(OAuthAccount)
        .where(OAuthAccount.provider == provider)
        .where(OAuthAccount.provider_user_id == provider_user_id)
    )
    oauth_account: OAuthAccount | None = link_result.scalar_one_or_none()

    if oauth_account:
        user_result = await session.execute(
            select(User).where(User.id == oauth_account.user_id)
        )
        user: User | None = user_result.scalar_one_or_none()
    else:
        # Try to find existing user by email for account unification
        email_result = await session.execute(
            select(User).where(User.email == provider_email)
        )
        user = email_result.scalar_one_or_none()

        if not user:
            user = User(email=provider_email, hashed_password=None)
            session.add(user)
            await session.flush()

        oauth_account = OAuthAccount(
            user_id=user.id,
            provider=provider,
            provider_user_id=provider_user_id,
            provider_email=provider_email,
        )
        session.add(oauth_account)
        await session.commit()

    if not user or not user.is_active:
        return _error_redirect(t.get("oauth.account_inactive", locale))

    if user.two_factor_enabled:
        return RedirectResponse(
            url=_front_callback_url(
                mfa_token=create_mfa_token(str(user.id)),
                mfa_method=user.two_factor_method or "totp",
            ),
            status_code=302,
        )

    # The callback host (a bare `localhost` redirect URI, the only kind Google
    # accepts) differs from the API host the front uses for `/auth/refresh`, so a
    # refresh cookie set here would never be sent back. Hand a short-lived token
    # to the front instead; it exchanges it via `/auth/oauth/bootstrap` on the
    # API host, which then sets the cookie on the correct host.
    return RedirectResponse(
        url=_front_callback_url(bootstrap=create_oauth_bootstrap_token(str(user.id))),
        status_code=302,
    )


@router.post("/bootstrap", response_model=TokenResponse)
async def oauth_bootstrap(
    request: Request,
    data: OAuthBootstrapRequest,
    response: Response,
    session: AsyncSession = Depends(get_session),
) -> TokenResponse:
    """Exchange an OAuth bootstrap token for a session (refresh cookie + access).

    Called by the front right after the OAuth callback redirect. Because this
    request hits the API host directly, the refresh cookie is set on the host the
    front actually reads from, fixing the cross-host cookie mismatch.

    Args:
        request: Incoming request (carries the locale).
        data: The bootstrap token handed to the front by the callback.
        response: Response used to set the refresh cookie.
        session: Async database session.

    Returns:
        A TokenResponse with a fresh access token (refresh travels in the cookie).

    Raises:
        HTTPException: 401 if the bootstrap token is invalid/expired or the user
            is missing or inactive.
    """
    locale = get_locale(request)
    try:
        user_id = verify_oauth_bootstrap_token(data.bootstrap_token)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=t.get("oauth.bootstrap_invalid", locale),
        )

    user = await UserRepository(session).get_by_id(uuid.UUID(user_id))
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=t.get("oauth.bootstrap_invalid", locale),
        )

    set_refresh_cookie(response, create_refresh_token(user_id))
    return TokenResponse(
        access_token=create_access_token(user_id, UserService.build_token_claims(user)),
    )
