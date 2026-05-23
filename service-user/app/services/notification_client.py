"""HTTP client for inter-service calls to service-notification."""

import logging

import httpx

logger: logging.Logger = logging.getLogger(__name__)


class NotificationClient:
    """Wraps calls to the service-notification /api/v1/notify endpoint."""

    @staticmethod
    async def send_mfa_code(
        user_id: str,
        code: str,
        recipient_email: str,
        notification_url: str,
        notification_token: str,
    ) -> bool:
        """Send a 2FA email code via the notification service.

        Args:
            user_id: The user's UUID string (used as user_slug).
            code: The plain-text OTP code to deliver.
            recipient_email: The destination email address.
            notification_url: Base URL of service-notification.
            notification_token: Inter-service auth token.

        Returns:
            True if the notification service responded with 2xx, False otherwise.
        """
        payload: dict = {
            "user_slug": user_id,
            "type": "mfa_code",
            "title": "Votre code de connexion",
            "body": f"Votre code de vérification : {code}",
            "data": {"code": code, "expires_in": 300},
            "recipient_email": recipient_email,
        }
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(
                    f"{notification_url}/api/v1/notify",
                    json=payload,
                    headers={"Authorization": f"Bearer {notification_token}"},
                )
                return resp.status_code < 300
        except Exception as exc:
            logger.error("Failed to send MFA notification: %s", exc)
            return False