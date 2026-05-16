from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.services.web_service import WebService

router = APIRouter()


class CrawlerSettings(BaseModel):
    js_detection_threshold: int


class CrawlerSettingsUpdate(BaseModel):
    # Note: changing this via the API only affects the FastAPI process.
    # Celery workers read JS_DETECTION_THRESHOLD from the env var at startup.
    js_detection_threshold: int = Field(ge=50, le=10_000)


@router.get("", response_model=CrawlerSettings)
async def get_settings():
    return CrawlerSettings(js_detection_threshold=WebService.get_js_threshold())


@router.patch("", response_model=CrawlerSettings)
async def update_settings(data: CrawlerSettingsUpdate):
    WebService.set_js_threshold(data.js_detection_threshold)
    return CrawlerSettings(js_detection_threshold=WebService.get_js_threshold())
