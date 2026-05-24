"""Business logic for the password reset workflow."""

import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password, verify_password
from app.models.password_history import PasswordHistory
from app.models.password_reset_token import PasswordResetToken
from app.models.user import User


class PasswordResetService:
    """Manages token lifecycle, password-history enforcement, and password updates."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    @staticmethod
    def _hash_token(plain_token: str) -> str:
        """Return the SHA-256 hex digest of a plain token."""
        return hashlib.sha256(plain_token.encode()).hexdigest()

    @staticmethod
    def _generate_plain_token() -> str:
        """Return a cryptographically secure URL-safe token string."""
        return secrets.token_urlsafe(32)

    async def create_reset_token(self, user: User, expires_minutes: int) -> str:
        """Persist a hashed reset token and return the plain token."""
        plain_token = self._generate_plain_token()
        token_hash = self._hash_token(plain_token)
        expires_at = datetime.now(timezone.utc) + timedelta(minutes=expires_minutes)

        reset_token = PasswordResetToken(
            user_id=user.id,
            token_hash=token_hash,
            expires_at=expires_at,
        )
        self._session.add(reset_token)
        await self._session.commit()
        return plain_token

    async def validate_and_consume_token(self, plain_token: str) -> User:
        """Validate a reset token, mark it as used, and return the owning user.

        Raises:
            ValueError: If the token is invalid, expired, or already consumed.
        """
        token_hash = self._hash_token(plain_token)
        now = datetime.now(timezone.utc)

        result = await self._session.execute(
            select(PasswordResetToken).where(
                PasswordResetToken.token_hash == token_hash,
                PasswordResetToken.used_at.is_(None),
                PasswordResetToken.expires_at > now,
            )
        )
        reset_token: PasswordResetToken | None = result.scalar_one_or_none()

        if reset_token is None:
            raise ValueError("Invalid, expired, or already used reset token")

        reset_token.used_at = now
        self._session.add(reset_token)

        user_result = await self._session.execute(
            select(User).where(User.id == reset_token.user_id)
        )
        user: User | None = user_result.scalar_one_or_none()
        if user is None:
            raise ValueError("User not found for reset token")

        return user

    async def is_password_reused(
        self, user: User, plain_password: str, history_count: int = 5
    ) -> bool:
        """Return True if the password matches the current or recent history.

        Checks current password + last (history_count - 1) history entries.
        """
        if user.hashed_password and verify_password(
            plain_password, user.hashed_password
        ):
            return True

        result = await self._session.execute(
            select(PasswordHistory)
            .where(PasswordHistory.user_id == user.id)
            .order_by(PasswordHistory.created_at.desc())
            .limit(history_count - 1)
        )
        for entry in result.scalars().all():
            if verify_password(plain_password, entry.hashed_password):
                return True

        return False

    async def update_password(self, user: User, new_plain_password: str) -> None:
        """Archive the current password hash and set the new one."""
        if user.hashed_password:
            self._session.add(
                PasswordHistory(
                    user_id=user.id,
                    hashed_password=user.hashed_password,
                )
            )

        user.hashed_password = hash_password(new_plain_password)
        self._session.add(user)
        await self._session.commit()
