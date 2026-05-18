import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.deps import verify_service_token
from app.db.session import get_session
from app.i18n.loader import t
from app.repositories.subscription_repository import SubscriptionRepository
from app.schemas.notification import NotifyRequest, NotifyResponse
from app.services.dispatch_service import DispatchService
from app.services.push_service import PushService

router = APIRouter()


@router.post("", response_model=NotifyResponse)
async def send_notification(
    payload: NotifyRequest,
    session: AsyncSession = Depends(get_session),
    _: None = Depends(verify_service_token),
) -> NotifyResponse:
    """
    Endpoint inter-service : envoie une notification à tous les devices abonnés
    du user identifié par user_slug (UUID sous forme de string).
    """
    try:
        user_id = uuid.UUID(payload.user_slug)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=t.get("errors.invalid_payload"),
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