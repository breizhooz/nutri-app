from pydantic import BaseModel, Field

from app.models.enums import PushChannel


class PushSubscribeRequest(BaseModel):
    channel: PushChannel
    # Web Push : JSON sérialisé du PushSubscription navigateur
    # Expo     : ExponentPushToken[...]
    token: str = Field(..., min_length=1)


class PushUnsubscribeRequest(BaseModel):
    token: str = Field(..., min_length=1)


class PushSubscribeResponse(BaseModel):
    message: str