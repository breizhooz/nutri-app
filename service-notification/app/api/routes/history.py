import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user_id
from app.db.session import get_session
from app.i18n.loader import t
from app.repositories.notification_repository import NotificationRepository
from app.schemas.notification import NotificationResponse

router = APIRouter()


@router.get("/{user_slug}/history", response_model=list[NotificationResponse])
async def get_history(
    user_slug: str,
    session: AsyncSession = Depends(get_session),
    current_user_id: uuid.UUID = Depends(get_current_user_id),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> list[NotificationResponse]:
    """Retourne l'historique des notifications du user (pageable)."""
    try:
        user_id = uuid.UUID(user_slug)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=t.get("errors.invalid_payload"),
        )
    if user_id != current_user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=t.get("errors.forbidden"),
        )
    return await NotificationRepository(session).get_by_user_id(
        user_id=user_id, limit=limit, offset=offset
    )