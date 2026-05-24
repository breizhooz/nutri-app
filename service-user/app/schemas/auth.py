"""Pydantic schemas for OAuth2 and MFA authentication flows."""

from pydantic import BaseModel


class PreAuthTokenResponse(BaseModel):
    """Returned by /login when the user has 2FA enabled.

    The client must call /auth/2fa/verify with this token and a valid OTP
    to receive full access and refresh tokens.
    """

    mfa_token: str
    mfa_method: str
    token_type: str = "Bearer"


class MfaVerifyRequest(BaseModel):
    """Payload for the /auth/2fa/verify endpoint."""

    mfa_token: str
    code: str


class TotpSetupResponse(BaseModel):
    """Returned by /auth/2fa/setup/totp.

    provisioning_uri can be used by the client to build its own QR code.
    qr_code_base64 is a ready-to-use PNG image encoded in base64 — display
    it directly with: <img src="data:image/png;base64,{qr_code_base64}" />
    """

    provisioning_uri: str
    qr_code_base64: str


class TotpConfirmRequest(BaseModel):
    """Payload for /auth/2fa/confirm/totp — proves the user scanned the QR."""

    code: str


class OAuthCallbackQuery(BaseModel):
    """Query parameters received at /auth/oauth/{provider}/callback."""

    code: str
    state: str
