"""Pydantic schemas for notification request/response."""

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict

from app.models.enums import NotificationStatus, NotificationType


class NotifyRequest(BaseModel):
    """Payload received by POST /api/v1/notify (inter-service call)."""

    user_slug: str
    type: NotificationType
    title: str
    body: str
    data: Optional[dict] = None
    recipient_email: Optional[str] = None


class NotifyResponse(BaseModel):
    """Response from POST /api/v1/notify."""

    slug: str
    status: NotificationStatus
    sent: int
    failed: int


class NotificationResponse(BaseModel):
    """Full notification record for history endpoint."""

    id: uuid.UUID
    slug: str
    user_id: uuid.UUID
    type: NotificationType
    title: str
    body: str
    data: Optional[dict]
    status: NotificationStatus
    sent_at: Optional[datetime]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
