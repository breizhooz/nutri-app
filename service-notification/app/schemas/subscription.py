import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class SubscriptionCreate(BaseModel):
    endpoint: str
    p256dh_key: str
    auth_key: str
    device_label: str | None = None


class SubscriptionResponse(BaseModel):
    id: uuid.UUID
    slug: str
    user_id: uuid.UUID
    endpoint: str
    p256dh_key: str
    auth_key: str
    device_label: str | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)