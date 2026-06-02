"""Tests for StorageService — mocks Minio client, no real MinIO needed."""

from unittest.mock import MagicMock, patch

import pytest

from app.core.exceptions import ImageTooLarge, UnsupportedImageType
from app.services.storage_service import StorageService


def _make_service() -> StorageService:
    with patch("app.services.storage_service.Minio"):
        svc = StorageService(
            endpoint="minio:9000",
            access_key="key",
            secret_key="secret",
            bucket="recipes",
            public_url="http://localhost:9000",
        )
    return svc


@pytest.mark.unit
@pytest.mark.asyncio
async def test_upload_returns_url():
    svc = _make_service()
    svc._client.bucket_exists = MagicMock(return_value=True)
    svc._client.put_object = MagicMock()

    url = await svc.upload_image(b"fakeimage", "image/png")

    assert url.startswith("http://localhost:9000/recipes/")
    assert url.endswith(".png")
    svc._client.put_object.assert_called_once()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_upload_creates_bucket_when_missing():
    svc = _make_service()
    svc._client.bucket_exists = MagicMock(return_value=False)
    svc._client.make_bucket = MagicMock()
    svc._client.set_bucket_policy = MagicMock()
    svc._client.put_object = MagicMock()

    await svc.upload_image(b"data", "image/jpeg")

    svc._client.make_bucket.assert_called_once_with("recipes")
    svc._client.set_bucket_policy.assert_called_once()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_invalid_content_type_raises():
    svc = _make_service()
    with pytest.raises(UnsupportedImageType):
        await svc.upload_image(b"data", "application/pdf")


@pytest.mark.unit
@pytest.mark.asyncio
async def test_oversized_file_raises():
    svc = _make_service()
    big = b"x" * (5 * 1024 * 1024 + 1)
    with pytest.raises(ImageTooLarge):
        await svc.upload_image(big, "image/jpeg")


@pytest.mark.unit
@pytest.mark.asyncio
async def test_correct_extension_for_webp():
    svc = _make_service()
    svc._client.bucket_exists = MagicMock(return_value=True)
    svc._client.put_object = MagicMock()

    url = await svc.upload_image(b"data", "image/webp")
    assert url.endswith(".webp")
