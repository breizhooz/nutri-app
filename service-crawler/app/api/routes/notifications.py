import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user_id
from app.db.session import get_session
from app.i18n.loader import t
from app.repositories.push_repository import PushRepository

from app.schemas.push_subscription import (
    PushSubscribeRequest,
    PushSubscribeResponse,
    PushUnsubscribeRequest,
)

router = APIRouter()


@router.post("", response_model=PushSubscribeResponse, status_code=status.HTTP_201_CREATED)
async def subscribe(
    data: PushSubscribeRequest,
    session: AsyncSession = Depends(get_session),
    current_user_id: uuid.UUID = Depends(get_current_user_id),
) -> PushSubscribeResponse:
    """Enregistre un appareil pour les notifications push (idempotent)."""
    await PushRepository(session).upsert(
        user_id=current_user_id,
        channel=data.channel,
        token=data.token,
    )
    return PushSubscribeResponse(message=t.get("notifications.subscribed"))


@router.delete("", status_code=status.HTTP_204_NO_CONTENT)
async def unsubscribe(
    data: PushUnsubscribeRequest,
    session: AsyncSession = Depends(get_session),
    current_user_id: uuid.UUID = Depends(get_current_user_id),
) -> None:
    """Désenregistre un appareil (silencieux si le token est inconnu)."""
    await PushRepository(session).delete_by_token(
        user_id=current_user_id,
        token=data.token,
    )