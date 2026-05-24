"""OAuth2 social login routes for Google and Facebook."""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import (
    create_access_token,
    create_mfa_token,
    create_oauth_state,
    create_refresh_token,
    verify_oauth_state,
)
from app.db.session import get_session
from app.models.oauth_account import OAuthAccount
from app.models.user import User
from app.schemas.auth import PreAuthTokenResponse
from app.schemas.user import TokenResponse
from app.services.oauth_service import OAuthService

router: APIRouter = APIRouter()

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
async def oauth_authorize(provider: str) -> RedirectResponse:
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
            detail=f"Unsupported OAuth2 provider: {provider}",
        )
    state = create_oauth_state(provider)
    url = OAuthService.build_authorization_url(
        provider=provider,
        client_id=_CLIENT_IDS[provider],
        redirect_uri=_redirect_uri(provider),
        state=state,
    )
    return RedirectResponse(url=url, status_code=302)


@router.get(
    "/{provider}/callback",
    response_model=TokenResponse | PreAuthTokenResponse,
)
async def oauth_callback(
    provider: str,
    code: str = Query(...),
    state: str = Query(...),
    session: AsyncSession = Depends(get_session),
) -> TokenResponse | PreAuthTokenResponse:
    """Handle the OAuth2 provider callback and issue tokens.

    Validates the state JWT, exchanges the authorization code for provider
    tokens, fetches the user profile, then creates or links the account.

    Args:
        provider: 'google' or 'facebook'.
        code: The authorization code from the provider.
        state: The CSRF state JWT generated at authorize time.
        session: Async database session.

    Returns:
        TokenResponse for users without 2FA, PreAuthTokenResponse otherwise.

    Raises:
        HTTPException: 400 for invalid state, unsupported provider, or
            if the provider does not return an email address.
    """
    if not OAuthService.is_valid_provider(provider):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported provider: {provider}",
        )
    try:
        state_provider = verify_oauth_state(state)
        if state_provider != provider:
            raise ValueError("Provider mismatch in state")
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired OAuth2 state",
        )

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
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to retrieve user info from provider",
        )

    provider_user_id, provider_email = OAuthService.extract_user_info(
        provider, raw_user
    )
    if not provider_email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Provider did not return an email address",
        )

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
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Account is inactive",
        )

    if user.two_factor_enabled:
        return PreAuthTokenResponse(
            mfa_token=create_mfa_token(str(user.id)),
            mfa_method=user.two_factor_method or "totp",
        )

    return TokenResponse(
        access_token=create_access_token(str(user.id)),
        refresh_token=create_refresh_token(str(user.id)),
    )
