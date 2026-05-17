import uuid

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import PushChannel
from app.models.push_subscription import PushSubscription


class PushRepository:
    """Accès DB pour les abonnements push."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def upsert(
        self,
        user_id: uuid.UUID,
        channel: PushChannel,
        token: str,
    ) -> PushSubscription:
        """Crée l'abonnement ou retourne l'existant (idempotent sur user_id + token)."""
        result = await self._session.execute(
            select(PushSubscription).where(
                PushSubscription.user_id == user_id,
                PushSubscription.token == token,
            )
        )
        existing = result.scalar_one_or_none()
        if existing:
            return existing

        subscription = PushSubscription(user_id=user_id, channel=channel, token=token)
        self._session.add(subscription)
        await self._session.commit()
        await self._session.refresh(subscription)
        return subscription

    async def delete_by_token(self, user_id: uuid.UUID, token: str) -> bool:
        """Supprime l'abonnement. Retourne True si un enregistrement a été supprimé."""
        result = await self._session.execute(
            delete(PushSubscription).where(
                PushSubscription.user_id == user_id,
                PushSubscription.token == token,
            )
        )
        await self._session.commit()
        return result.rowcount > 0

    async def get_by_user_id(self, user_id: uuid.UUID) -> list[PushSubscription]:
        """Retourne tous les abonnements d'un utilisateur."""
        result = await self._session.execute(
            select(PushSubscription).where(PushSubscription.user_id == user_id)
        )
        return list(result.scalars().all())