"""Tests for StorageService — mocks the boto3 S3 client, no real server needed."""

from unittest.mock import MagicMock, patch

import pytest

from app.core.exceptions import ImageTooLarge, UnsupportedImageType
from app.services.storage_service import ClientError, StorageService


def _make_service() -> StorageService:
    with patch("app.services.storage_service.boto3"):
        svc = StorageService(
            endpoint="seaweedfs:8333",
            access_key="key",
            secret_key="secret",
            bucket="recipes",
            public_url="http://localhost:8333",
        )
    # boto3.client(...) est mocké → _client est un MagicMock.
    return svc


@pytest.mark.unit
@pytest.mark.asyncio
async def test_upload_returns_url():
    svc = _make_service()
    svc._client.head_bucket = MagicMock()  # bucket présent
    svc._client.put_object = MagicMock()

    url = await svc.upload_image(b"fakeimage", "image/png")

    assert url.startswith("http://localhost:8333/recipes/")
    assert url.endswith(".png")
    svc._client.put_object.assert_called_once()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_upload_creates_bucket_when_missing():
    svc = _make_service()
    svc._client.head_bucket = MagicMock(
        side_effect=ClientError({"Error": {"Code": "404"}}, "HeadBucket")
    )
    svc._client.create_bucket = MagicMock()
    svc._client.put_object = MagicMock()

    await svc.upload_image(b"data", "image/jpeg")

    svc._client.create_bucket.assert_called_once_with(Bucket="recipes")


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
    svc._client.head_bucket = MagicMock()
    svc._client.put_object = MagicMock()

    url = await svc.upload_image(b"data", "image/webp")
    assert url.endswith(".webp")
