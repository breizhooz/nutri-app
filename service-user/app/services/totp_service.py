"""TOTP and OTP generation/verification utilities."""

import base64
import io
import secrets

import pyotp
import qrcode
from qrcode.image.pil import PilImage


class TotpService:
    """Static helpers for TOTP (RFC 6238) operations."""

    @staticmethod
    def generate_secret() -> str:
        """Generate a new cryptographically secure base32 TOTP secret.

        Returns:
            A random base32 string compatible with Google Authenticator.
        """
        return pyotp.random_base32()

    @staticmethod
    def verify_code(secret: str, code: str, valid_window: int = 1) -> bool:
        """Verify a TOTP code against a secret with a time window.

        Args:
            secret: The base32 TOTP secret.
            code: The 6-digit code provided by the user.
            valid_window: Number of 30-second windows to allow on either side.

        Returns:
            True if the code is valid within the window, False otherwise.
        """
        return pyotp.TOTP(secret).verify(code, valid_window=valid_window)

    @staticmethod
    def get_provisioning_uri(
        secret: str,
        email: str,
        issuer: str = "NutriApp",
    ) -> str:
        """Build the otpauth:// URI for QR code display.

        Args:
            secret: The base32 TOTP secret.
            email: The user's email address (shown in the authenticator app).
            issuer: The application name shown in the authenticator app.

        Returns:
            An otpauth:// URI string.
        """
        return pyotp.TOTP(secret).provisioning_uri(
            name=email,
            issuer_name=issuer,
        )

    @staticmethod
    def generate_qr_code_base64(provisioning_uri: str) -> str:
        """Generate a PNG QR code from an otpauth:// URI and return it as base64.

        The result can be embedded directly in an HTML img tag:
            <img src="data:image/png;base64,{result}" />

        Args:
            provisioning_uri: The otpauth:// URI produced by get_provisioning_uri().

        Returns:
            A base64-encoded PNG image string.
        """
        img: PilImage = qrcode.make(provisioning_uri)
        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        return base64.b64encode(buffer.getvalue()).decode()


class CodeGenerator:
    """Generates cryptographically secure OTP codes for email-based 2FA."""

    @staticmethod
    def generate_otp(length: int = 6) -> str:
        """Generate a zero-padded numeric OTP of the given length.

        Args:
            length: Number of digits (default 6).

        Returns:
            A zero-padded numeric string of the requested length.
        """
        return str(secrets.randbelow(10**length)).zfill(length)