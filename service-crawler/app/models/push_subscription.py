import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum as SQLEnum, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_class import Base
from app.models.enums import PushChannel


class PushSubscription(Base):
    """Enregistrement d'un appareil pour les notifications push."""

    __tablename__ = "push_subscriptions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, index=True
    )
    channel: Mapped[PushChannel] = mapped_column(
        SQLEnum(PushChannel, native_enum=False, length=20), nullable=False
    )
    # WEB_PUSH : JSON sérialisé {endpoint, keys: {p256dh, auth}}
    # EXPO     : token ExponentPushToken[...]
    token: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        UniqueConstraint("user_id", "token", name="uq_push_sub_user_token"),
    )