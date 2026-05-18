from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import NotificationStatus, NotificationType
from app.repositories.notification_repository import NotificationRepository
from app.repositories.subscription_repository import SubscriptionRepository
from app.services.push_service import PushService

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class DispatchResult:
    """Résultat agrégé d'un dispatch vers tous les devices d'un user."""
    notification_slug: str
    status: NotificationStatus
    sent: int
    failed: int


class DispatchService:
    """
    Orchestre l'envoi d'une notification :
      1. Crée l'entrée Notification (status=pending)
      2. Récupère les Subscription du user
      3. Envoie via PushService sur chaque device
      4. Met à jour le status final (sent / failed)
    Précondition : au moins une subscription existe (vérification faite par la route).
    """

    def __init__(self, session: AsyncSession, push_service: PushService) -> None:
        self._sub_repo = SubscriptionRepository(session)
        self._notif_repo = NotificationRepository(session)
        self._push = push_service

    async def dispatch(
        self,
        user_id: uuid.UUID,
        type: NotificationType,
        title: str,
        body: str,
        data: dict | None = None,
    ) -> DispatchResult:
        """Crée la notification et l'envoie à tous les devices abonnés."""
        notification = await self._notif_repo.create(
            user_id=user_id,
            type=type,
            title=title,
            body=body,
            data=data,
        )

        subscriptions = await self._sub_repo.get_by_user_id(user_id)
        sent, failed = 0, 0

        for sub in subscriptions:
            success = await self._push.send(sub, title=title, body=body, data=data)
            if success:
                sent += 1
            else:
                failed += 1

        final_status = NotificationStatus.SENT if sent > 0 else NotificationStatus.FAILED
        updated = await self._notif_repo.update_status(notification, final_status)

        return DispatchResult(
            notification_slug=updated.slug,
            status=final_status,
            sent=sent,
            failed=failed,
        )