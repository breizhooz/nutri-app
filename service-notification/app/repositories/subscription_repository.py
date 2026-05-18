import uuid

from slugify import slugify
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.subscription import Subscription


class SubscriptionRepository:
    """Accès DB pour les subscriptions."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        user_id: uuid.UUID,
        endpoint: str,
        p256dh_key: str,
        auth_key: str,
        device_label: str | None = None,
    ) -> Subscription:
        slug = await self._unique_slug(user_id, device_label)
        sub = Subscription(
            user_id=user_id,
            slug=slug,
            endpoint=endpoint,
            p256dh_key=p256dh_key,
            auth_key=auth_key,
            device_label=device_label,
        )
        self._session.add(sub)
        await self._session.commit()
        await self._session.refresh(sub)
        return sub

    async def get_by_slug(self, slug: str) -> Subscription | None:
        result = await self._session.execute(
            select(Subscription).where(Subscription.slug == slug)
        )
        return result.scalar_one_or_none()

    async def get_by_endpoint(self, endpoint: str) -> Subscription | None:
        result = await self._session.execute(
            select(Subscription).where(Subscription.endpoint == endpoint)
        )
        return result.scalar_one_or_none()

    async def get_by_user_id(self, user_id: uuid.UUID) -> list[Subscription]:
        result = await self._session.execute(
            select(Subscription).where(Subscription.user_id == user_id)
        )
        return list(result.scalars().all())

    async def delete(self, subscription: Subscription) -> None:
        await self._session.delete(subscription)
        await self._session.commit()

    async def _unique_slug(
        self, user_id: uuid.UUID, device_label: str | None
    ) -> str:
        """Génère un slug unique : <user_prefix>-<device_label>[-N] en cas de collision."""
        base = slugify(f"{str(user_id)[:8]}-{device_label or 'device'}")
        slug, counter = base, 2
        while await self.get_by_slug(slug):
            slug = f"{base}-{counter}"
            counter += 1
        return slug