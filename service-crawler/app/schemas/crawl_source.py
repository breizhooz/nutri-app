import uuid
from datetime import datetime, time
from typing import Annotated, Literal, Union

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_serializer

from app.models.enums import CrawlType


class WebSourceCreate(BaseModel):
    type: Literal[CrawlType.WEB]
    url: str
    frequency_hours: int = 24
    execution_hour: time = time(3, 0)

    @field_validator("url")
    @classmethod
    def validate_http_url(cls, v: str) -> str:
        from pydantic import AnyHttpUrl, ValidationError as PydanticValidationError

        try:
            AnyHttpUrl(v)
        except PydanticValidationError:
            raise ValueError("L'URL doit être une URL HTTP ou HTTPS valide.")
        return v


class InstagramSourceCreate(BaseModel):
    type: Literal[CrawlType.INSTAGRAM]
    account: str
    frequency_hours: int = 24
    execution_hour: time = time(3, 0)

    @field_validator("account", mode="before")
    @classmethod
    def normalize_account(cls, v: str) -> str:
        if not isinstance(v, str):
            raise ValueError("Le compte Instagram doit être une chaîne de caractères.")
        cleaned = v.lstrip("@").strip()
        if not cleaned:
            raise ValueError("Le nom de compte Instagram ne peut pas être vide.")
        return cleaned

    @model_serializer(mode="wrap")
    def _serialize(self, handler) -> dict:
        data = handler(self)
        data["url"] = data.pop("account")
        return data


CrawlSourceCreate = Annotated[
    Union[WebSourceCreate, InstagramSourceCreate],
    Field(discriminator="type"),
]


class CrawlSourceUpdate(BaseModel):
    actif: bool | None = None
    frequency_hours: int | None = None
    execution_hour: time | None = None


class CrawlSourceResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    type: CrawlType
    url: str
    actif: bool
    frequency_hours: int
    execution_hour: time
    last_crawl: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
