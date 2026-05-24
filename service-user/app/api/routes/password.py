"""Password reset workflow: request a reset link, then confirm with token."""

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.session import get_session
from app.models.user import User
from app.schemas.password import (
    PasswordResetConfirmSchema,
    PasswordResetMessage,
    PasswordResetRequestSchema,
)
from app.services.notification_client import NotificationClient
from app.services.password_reset_service import PasswordResetService

logger: logging.Logger = logging.getLogger(__name__)

router: APIRouter = APIRouter()


@router.post(
    "/reset-request",
    response_model=PasswordResetMessage,
    status_code=status.HTTP_202_ACCEPTED,
)
async def request_password_reset(
    data: PasswordResetRequestSchema,
    session: AsyncSession = Depends(get_session),
) -> PasswordResetMessage:
    """Initiate a password reset by emailing a one-time link.

    Always returns 202 to avoid user-enumeration attacks.
    """
    result = await session.execute(select(User).where(User.email == data.email))
    user: User | None = result.scalar_one_or_none()

    if user and user.hashed_password and user.is_active:
        service = PasswordResetService(session)
        plain_token = await service.create_reset_token(
            user, settings.PASSWORD_RESET_TOKEN_EXPIRE_MINUTES
        )
        reset_url = f"{settings.PASSWORD_RESET_BASE_URL}/reset?token={plain_token}"
        sent = await NotificationClient.send_password_reset_email(
            user_id=str(user.id),
            recipient_email=user.email,
            reset_url=reset_url,
            notification_url=settings.NOTIFICATION_SERVICE_URL,
            notification_token=settings.NOTIFICATION_SERVICE_TOKEN,
        )
        if not sent:
            logger.warning("Password reset email failed for user %s", user.id)

    return PasswordResetMessage(
        message="Si un compte existe avec cette adresse, un lien de réinitialisation a été envoyé."
    )


@router.post(
    "/reset",
    response_model=PasswordResetMessage,
    status_code=status.HTTP_200_OK,
)
async def confirm_password_reset(
    data: PasswordResetConfirmSchema,
    session: AsyncSession = Depends(get_session),
) -> PasswordResetMessage:
    """Validate the reset token and apply the new password.

    Raises:
        HTTPException 400: token invalid / expired / already used.
        HTTPException 409: new password matches one of the last 5.
    """
    service = PasswordResetService(session)

    try:
        user = await service.validate_and_consume_token(data.token)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    if await service.is_password_reused(
        user, data.new_password, settings.PASSWORD_HISTORY_COUNT
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Le nouveau mot de passe doit être différent des 5 derniers mots de passe utilisés.",
        )

    await service.update_password(user, data.new_password)
    return PasswordResetMessage(message="Mot de passe mis à jour avec succès.")
