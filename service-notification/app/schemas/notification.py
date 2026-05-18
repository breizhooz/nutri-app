import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.enums import NotificationStatus, NotificationType


class NotifyRequest(BaseModel):
    """Payload reçu par POST /api/v1/notify (appel inter-service)."""
    user_slug: str
    type: NotificationType
    title: str
    body: str
    data: dict | None = None


class NotifyResponse(BaseModel):
    slug: str
    status: NotificationStatus
    sent: int
    failed: int


class NotificationResponse(BaseModel):
    id: uuid.UUID
    slug: str
    user_id: uuid.UUID
    type: NotificationType
    title: str
    body: str
    data: dict | None
    status: NotificationStatus
    sent_at: datetime | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)