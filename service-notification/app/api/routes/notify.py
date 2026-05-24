"""Inter-service notification dispatch endpoint."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import verify_service_token
from app.db.session import get_session
from app.core.config import settings
from app.i18n.loader import t
from app.models.enums import NotificationStatus, NotificationType
from app.repositories.notification_repository import NotificationRepository
from app.repositories.subscription_repository import SubscriptionRepository
from app.schemas.notification import NotifyRequest, NotifyResponse
from app.services.dispatch_service import DispatchService
from app.services.email_service import EmailService
from app.services.push_service import PushService

router: APIRouter = APIRouter()


@router.post("", response_model=NotifyResponse)
async def send_notification(
    payload: NotifyRequest,
    session: AsyncSession = Depends(get_session),
    _: None = Depends(verify_service_token),
) -> NotifyResponse:
    """Dispatch a notification to the user via the appropriate channel.

    For MFA_CODE type: sends via SMTP email using recipient_email.
    For all other types: sends via Web Push to subscribed devices.

    Args:
        payload: The notification request payload.
        session: Async database session.

    Returns:
        A NotifyResponse with delivery status and counts.

    Raises:
        HTTPException: 422 if user_slug is not a valid UUID.
        HTTPException: 422 if recipient_email is missing for mfa_code type.
        HTTPException: 404 if no push subscriptions exist (non-email types).
    """
    try:
        user_id = uuid.UUID(payload.user_slug)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=t.get("errors.invalid_payload"),
        )

    if payload.type == NotificationType.MFA_CODE:
        if not payload.recipient_email:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="recipient_email is required for mfa_code notifications",
            )
        code = (payload.data or {}).get("code", "")
        email_sent = await EmailService.send_mfa_code(
            recipient_email=payload.recipient_email,
            code=code,
        )
        notif_repo = NotificationRepository(session)
        notif = await notif_repo.create(
            user_id=user_id,
            type=payload.type,
            title=payload.title,
            body=payload.body,
            data=payload.data,
        )
        final_status = (
            NotificationStatus.SENT if email_sent else NotificationStatus.FAILED
        )
        updated = await notif_repo.update_status(notif, final_status)
        return NotifyResponse(
            slug=updated.slug,
            status=final_status,
            sent=1 if email_sent else 0,
            failed=0 if email_sent else 1,
        )

    subscriptions = await SubscriptionRepository(session).get_by_user_id(user_id)
    if not subscriptions:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=t.get("errors.user_not_found"),
        )

    push = PushService(
        vapid_private_key=settings.VAPID_PRIVATE_KEY,
        vapid_claims_email=settings.VAPID_CLAIMS_EMAIL,
    )
    result = await DispatchService(session=session, push_service=push).dispatch(
        user_id=user_id,
        type=payload.type,
        title=payload.title,
        body=payload.body,
        data=payload.data,
    )
    return NotifyResponse(
        slug=result.notification_slug,
        status=result.status,
        sent=result.sent,
        failed=result.failed,
    )
