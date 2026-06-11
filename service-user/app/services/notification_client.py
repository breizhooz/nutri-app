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

    @staticmethod
    async def send_password_reset_email(
        user_id: str,
        recipient_email: str,
        reset_url: str,
        notification_url: str,
        notification_token: str,
    ) -> bool:
        """Send a password-reset link email via the notification service."""
        payload: dict = {
            "user_slug": user_id,
            "type": "password_reset",
            "title": "Réinitialisation de votre mot de passe",
            "body": f"Cliquez sur le lien pour réinitialiser votre mot de passe : {reset_url}",
            "data": {"reset_url": reset_url, "expires_in": 1800},
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
            logger.error("Failed to send password reset notification: %s", exc)
            return False

    @staticmethod
    async def send_invitation_email(
        recipient_email: str,
        account_name: str,
        role_code: str,
        accept_url: str,
        notification_url: str,
        notification_token: str,
    ) -> bool:
        """Send an account-share invitation email via the notification service."""
        payload: dict = {
            "user_slug": recipient_email,
            "type": "account_invitation",
            "title": f"Invitation à rejoindre le dossier « {account_name} »",
            "body": (
                f"Vous êtes invité(e) à rejoindre le dossier « {account_name} » "
                f"en tant que {role_code}. Cliquez pour accepter : {accept_url}"
            ),
            "data": {"accept_url": accept_url, "role": role_code},
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
            logger.error("Failed to send invitation notification: %s", exc)
            return False
