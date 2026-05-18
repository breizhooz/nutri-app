import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user_id
from app.db.session import get_session
from app.i18n.loader import t
from app.repositories.subscription_repository import SubscriptionRepository
from app.schemas.subscription import SubscriptionCreate, SubscriptionResponse

router = APIRouter()


@router.post("", response_model=SubscriptionResponse, status_code=status.HTTP_201_CREATED)
async def register_subscription(
    data: SubscriptionCreate,
    session: AsyncSession = Depends(get_session),
    current_user_id: uuid.UUID = Depends(get_current_user_id),
) -> SubscriptionResponse:
    """Enregistre un device pour les push notifications (idempotent sur l'endpoint)."""
    repo = SubscriptionRepository(session)
    existing = await repo.get_by_endpoint(data.endpoint)
    if existing:
        return existing
    return await repo.create(
        user_id=current_user_id,
        endpoint=data.endpoint,
        p256dh_key=data.p256dh_key,
        auth_key=data.auth_key,
        device_label=data.device_label,
    )


@router.get("/{slug}", response_model=SubscriptionResponse)
async def get_subscription(
    slug: str,
    session: AsyncSession = Depends(get_session),
    current_user_id: uuid.UUID = Depends(get_current_user_id),
) -> SubscriptionResponse:
    """Retourne le détail d'une subscription."""
    repo = SubscriptionRepository(session)
    sub = await repo.get_by_slug(slug)
    if not sub:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=t.get("subscription.not_found"),
        )
    if sub.user_id != current_user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=t.get("errors.forbidden"),
        )
    return sub


@router.delete("/{slug}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_subscription(
    slug: str,
    session: AsyncSession = Depends(get_session),
    current_user_id: uuid.UUID = Depends(get_current_user_id),
) -> None:
    """Se désabonne d'un device."""
    repo = SubscriptionRepository(session)
    sub = await repo.get_by_slug(slug)
    if not sub:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=t.get("subscription.not_found"),
        )
    if sub.user_id != current_user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=t.get("errors.forbidden"),
        )
    await repo.delete(sub)