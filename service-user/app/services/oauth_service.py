"""OAuth2 provider integration for Google and Facebook."""

import urllib.parse
from typing import Optional

import httpx


class OAuthService:
    """Handles OAuth2 authorization flows for Google and Facebook.

    All methods are static to allow easy mocking in tests and to avoid
    unnecessary instantiation for stateless operations.
    """

    _PROVIDERS: dict[str, dict] = {
        "google": {
            "authorize_url": "https://accounts.google.com/o/oauth2/auth",
            "token_url": "https://oauth2.googleapis.com/token",  # nosec B105
            "userinfo_url": "https://www.googleapis.com/oauth2/v3/userinfo",
            "scopes": "openid email profile",
        },
        "facebook": {
            "authorize_url": "https://www.facebook.com/dialog/oauth",
            "token_url": "https://graph.facebook.com/oauth/access_token",  # nosec B105
            "userinfo_url": "https://graph.facebook.com/me?fields=id,email,name",
            "scopes": "email,public_profile",
        },
    }

    @staticmethod
    def is_valid_provider(provider: str) -> bool:
        """Check whether the given provider is supported.

        Args:
            provider: Provider name to check.

        Returns:
            True if the provider is configured.
        """
        return provider in OAuthService._PROVIDERS

    @staticmethod
    def build_authorization_url(
        provider: str,
        client_id: str,
        redirect_uri: str,
        state: str,
    ) -> str:
        """Build the full OAuth2 authorization redirect URL.

        Args:
            provider: 'google' or 'facebook'.
            client_id: The application's OAuth2 client ID.
            redirect_uri: The callback URL registered with the provider.
            state: A CSRF-protection state token.

        Returns:
            The full authorization URL to redirect the user to.

        Raises:
            KeyError: If provider is not in _PROVIDERS.
        """
        config = OAuthService._PROVIDERS[provider]
        params: dict[str, str] = {
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "scope": config["scopes"],
            "response_type": "code",
            "state": state,
        }
        if provider == "google":
            params["access_type"] = "offline"
            params["prompt"] = "consent"
        return f"{config['authorize_url']}?{urllib.parse.urlencode(params)}"

    @staticmethod
    async def exchange_code(
        provider: str,
        client_id: str,
        client_secret: str,
        redirect_uri: str,
        code: str,
        http_client: Optional[httpx.AsyncClient] = None,
    ) -> dict:
        """Exchange an authorization code for provider access tokens.

        Args:
            provider: 'google' or 'facebook'.
            client_id: OAuth2 client ID.
            client_secret: OAuth2 client secret.
            redirect_uri: Must match the URI used in the authorization request.
            code: The authorization code received from the provider.
            http_client: Optional injected client (used in tests).

        Returns:
            A dict containing at minimum 'access_token'.

        Raises:
            httpx.HTTPStatusError: On non-2xx responses from the provider.
        """
        config = OAuthService._PROVIDERS[provider]
        data = {
            "client_id": client_id,
            "client_secret": client_secret,
            "redirect_uri": redirect_uri,
            "code": code,
            "grant_type": "authorization_code",
        }
        if http_client is not None:
            resp = await http_client.post(config["token_url"], data=data)
            resp.raise_for_status()
            return dict(resp.json())

        async with httpx.AsyncClient() as client:
            resp = await client.post(config["token_url"], data=data)
            resp.raise_for_status()
            return dict(resp.json())

    @staticmethod
    async def fetch_user_info(
        provider: str,
        access_token: str,
        http_client: Optional[httpx.AsyncClient] = None,
    ) -> dict:
        """Fetch the authenticated user's profile from the provider.

        Args:
            provider: 'google' or 'facebook'.
            access_token: The provider access token from exchange_code().
            http_client: Optional injected client (used in tests).

        Returns:
            A dict with provider-specific user profile fields.

        Raises:
            httpx.HTTPStatusError: On non-2xx responses from the provider.
        """
        config = OAuthService._PROVIDERS[provider]
        headers = {"Authorization": f"Bearer {access_token}"}
        if http_client is not None:
            resp = await http_client.get(config["userinfo_url"], headers=headers)
            resp.raise_for_status()
            return dict(resp.json())

        async with httpx.AsyncClient() as client:
            resp = await client.get(config["userinfo_url"], headers=headers)
            resp.raise_for_status()
            return dict(resp.json())

    @staticmethod
    def extract_user_info(
        provider: str,
        raw: dict,
    ) -> tuple[str, Optional[str]]:
        """Extract (provider_user_id, email) from a provider user-info payload.

        Args:
            provider: 'google' or 'facebook'.
            raw: The raw dict returned by fetch_user_info().

        Returns:
            A tuple of (provider_user_id, email_or_None).

        Raises:
            ValueError: If the provider is not supported.
        """
        if provider == "google":
            return str(raw["sub"]), raw.get("email")
        if provider == "facebook":
            return str(raw["id"]), raw.get("email")
        raise ValueError(f"Unsupported provider: {provider}")
