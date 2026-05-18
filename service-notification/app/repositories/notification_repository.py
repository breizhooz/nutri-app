import uuid
from datetime import datetime, timezone

from slugify import slugify
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import NotificationStatus
from app.models.notification import Notification


class NotificationRepository:
    """Accès DB pour l'historique des notifications."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        user_id: uuid.UUID,
        type: str,
        title: str,
        body: str,
        data: dict | None = None,
    ) -> Notification:
        slug = self._build_slug(type, user_id)
        notif = Notification(
            user_id=user_id,
            slug=slug,
            type=type,
            title=title,
            body=body,
            data=data,
            status=NotificationStatus.PENDING,
        )
        self._session.add(notif)
        await self._session.commit()
        await self._session.refresh(notif)
        return notif

    async def update_status(
        self,
        notification: Notification,
        status: NotificationStatus,
    ) -> Notification:
        notification.status = status
        if status == NotificationStatus.SENT:
            notification.sent_at = datetime.now(timezone.utc)
        await self._session.commit()
        await self._session.refresh(notification)
        return notification

    async def get_by_user_id(
        self,
        user_id: uuid.UUID,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Notification]:
        result = await self._session.execute(
            select(Notification)
            .where(Notification.user_id == user_id)
            .order_by(Notification.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all())

    @staticmethod
    def _build_slug(type: str, user_id: uuid.UUID) -> str:
        """Slug unique basé sur type, user et timestamp microseconde."""
        ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S%f")
        return slugify(f"{type}-{str(user_id)[:8]}-{ts}")