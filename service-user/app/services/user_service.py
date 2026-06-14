"""Business logic for user administration (RBAC management)."""

import uuid
from typing import Any, Optional

from app.models.user import User
from app.repositories.user_repository import UserRepository
from app.schemas.user import UserRightsUpdate
from app.services import erasure_service


class UserService:
    """Service holding the business logic for listing and managing users."""

    def __init__(self, repository: UserRepository) -> None:
        self.repository = repository

    async def list_users(self) -> list[User]:
        """Return every user account (admin-only use case)."""
        return await self.repository.list_all()

    async def update_user_rights(
        self, user_id: uuid.UUID, payload: UserRightsUpdate
    ) -> Optional[User]:
        """Apply an admin-driven rights update to the target user.

        Returns the updated user, or ``None`` if no user matches ``user_id``.
        """
        user = await self.repository.get_by_id(user_id)
        if user is None:
            return None

        user_right: Optional[dict[str, Any]] = (
            payload.user_right.model_dump() if payload.user_right is not None else None
        )
        return await self.repository.update_rights(
            user,
            user_admin=payload.user_admin,
            is_coach=payload.is_coach,
            user_right=user_right,
        )

    async def delete_user(self, user_id: uuid.UUID) -> bool:
        """Delete a user account and erase its data across services (RGPD art. 17).

        Records a cross-service erasure request (journal + audit) covering the
        user's personal accounts, deletes the local identity, then schedules the
        asynchronous purge of the other services. Returns ``True`` if a user was
        deleted, ``False`` if none matched ``user_id``.
        """
        user = await self.repository.get_by_id(user_id)
        if user is None:
            return False
        account_ids = await self.repository.list_personal_account_ids(user)
        request_id = await erasure_service.request_erasure(
            self.repository.session, user_id, account_ids
        )
        await self.repository.delete(user)
        erasure_service.schedule_erasure(request_id)
        return True

    @staticmethod
    def build_token_claims(user: User) -> dict[str, Any]:
        """Build the RBAC claims embedded in a user's access token.

        These claims let other services (recipe, crawler) enforce permissions
        locally without an extra round-trip to service-user.
        """
        return {"user_admin": user.user_admin, "user_right": user.user_right}
