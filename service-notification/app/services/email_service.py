"""Async SMTP email delivery service."""

import logging

import aiosmtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from app.core.config import settings

logger: logging.Logger = logging.getLogger(__name__)


class EmailService:
    """Sends transactional emails via async SMTP (aiosmtplib).

    All methods are static; SMTP settings are read from the application config.
    """

    @staticmethod
    async def send_mfa_code(recipient_email: str, code: str) -> bool:
        """Send a 2FA verification code to the given email address.

        Args:
            recipient_email: The destination email address.
            code: The plain-text OTP code to include in the message.

        Returns:
            True if the email was accepted by the SMTP server, False otherwise.
        """
        if not settings.SMTP_HOST:
            logger.warning("SMTP_HOST not configured — skipping email send")
            return False

        message = EmailService._build_mfa_message(recipient_email, code)
        try:
            await aiosmtplib.send(
                message,
                hostname=settings.SMTP_HOST,
                port=settings.SMTP_PORT,
                username=settings.SMTP_USER or None,
                password=settings.SMTP_PASSWORD or None,
                use_tls=settings.SMTP_USE_TLS,
            )
            return True
        except Exception as exc:
            logger.error("Failed to send MFA email to %s: %s", recipient_email, exc)
            return False

    @staticmethod
    def _build_mfa_message(recipient_email: str, code: str) -> MIMEMultipart:
        """Construct the MIME email message for a 2FA code.

        Args:
            recipient_email: The destination email address.
            code: The plain-text OTP code.

        Returns:
            A MIMEMultipart email message ready for sending.
        """
        msg = MIMEMultipart("alternative")
        msg["Subject"] = "Votre code de connexion NutriApp"
        msg["From"] = settings.SMTP_FROM
        msg["To"] = recipient_email

        text_body = (
            f"Votre code de vérification est : {code}\n\nIl expire dans 5 minutes."
        )
        html_body = f"""
        <html><body>
          <p>Votre code de vérification NutriApp :</p>
          <h2 style="letter-spacing:0.3em">{code}</h2>
          <p>Ce code expire dans <strong>5 minutes</strong>.</p>
        </body></html>
        """
        msg.attach(MIMEText(text_body, "plain", "utf-8"))
        msg.attach(MIMEText(html_body, "html", "utf-8"))
        return msg
