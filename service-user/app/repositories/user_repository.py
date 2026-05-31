"""Data-access layer for the users table.

All SQLAlchemy queries touching the User model live here (architecture rule:
no raw queries in routes or services).
"""

import uuid
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User


class UserRepository:
    """Repository encapsulating persistence operations for :class:`User`."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_id(self, user_id: uuid.UUID) -> Optional[User]:
        result = await self.session.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()

    async def get_by_email(self, email: str) -> Optional[User]:
        result = await self.session.execute(select(User).where(User.email == email))
        return result.scalar_one_or_none()

    async def list_all(self) -> list[User]:
        result = await self.session.execute(select(User).order_by(User.email))
        return list(result.scalars().all())

    async def delete(self, user: User) -> None:
        """Permanently remove a user account."""
        await self.session.delete(user)
        await self.session.commit()

    async def update_rights(
        self,
        user: User,
        *,
        user_admin: Optional[bool] = None,
        user_right: Optional[dict[str, Any]] = None,
    ) -> User:
        """Persist a partial update of a user's RBAC fields.

        Only the provided (non-None) fields are modified.
        """
        if user_admin is not None:
            user.user_admin = user_admin
        if user_right is not None:
            user.user_right = user_right
        await self.session.commit()
        await self.session.refresh(user)
        return user
