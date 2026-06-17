"""TOTP and OTP generation/verification utilities."""

import base64
import io
import secrets
from pathlib import Path

import pyotp
import qrcode
from PIL import Image

# Bundled brand logo embedded at the centre of the QR code by default.
_DEFAULT_LOGO_PATH = (
    Path(__file__).resolve().parent.parent / "assets" / "rostr_logo.png"
)


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
        issuer: str = "Rost.r",
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
    def generate_qr_code_base64(
        provisioning_uri: str, logo_path: str | None = None
    ) -> str:
        """Generate a PNG QR code from an otpauth:// URI and return it as base64.

        When a logo image is available it is embedded at the centre of the QR
        code; a high error-correction level keeps the code scannable despite
        the overlay. If no logo file is found a plain QR code is produced.

        The result can be embedded directly in an HTML img tag:
            <img src="data:image/png;base64,{result}" />

        Args:
            provisioning_uri: The otpauth:// URI produced by get_provisioning_uri().
            logo_path: Optional path to a logo image; falls back to the bundled
                brand logo when omitted, and to a plain QR when no file exists.

        Returns:
            A base64-encoded PNG image string.
        """
        qr = qrcode.QRCode(
            error_correction=qrcode.constants.ERROR_CORRECT_H,
            box_size=10,
            border=4,
        )
        qr.add_data(provisioning_uri)
        qr.make(fit=True)
        img = (
            qr.make_image(fill_color="black", back_color="white")
            .get_image()
            .convert("RGB")
        )

        logo_file = Path(logo_path) if logo_path else _DEFAULT_LOGO_PATH
        if logo_file.is_file():
            TotpService._embed_logo(img, logo_file)

        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        return base64.b64encode(buffer.getvalue()).decode()

    @staticmethod
    def _embed_logo(qr_img: Image.Image, logo_path: Path) -> None:
        """Paste a logo at the centre of the QR image, on a white pad.

        The logo is capped to ~20% of the QR width and sits on a white
        background so it stays separated from the dark modules and the code
        remains decodable.

        Args:
            qr_img: The RGB QR image to overlay in place.
            logo_path: Path to the logo image file.
        """
        qr_w, qr_h = qr_img.size
        logo = Image.open(logo_path).convert("RGB")
        target = qr_w // 5
        logo.thumbnail((target, target))
        pad = max(qr_w // 40, 6)
        bg = Image.new("RGB", (logo.size[0] + 2 * pad, logo.size[1] + 2 * pad), "white")
        bg.paste(logo, (pad, pad))
        qr_img.paste(bg, ((qr_w - bg.size[0]) // 2, (qr_h - bg.size[1]) // 2))


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
