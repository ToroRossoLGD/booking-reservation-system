from io import BytesIO
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException, UploadFile

from app.core.config import settings
from app.services.media_storage_service import MediaStorageService


def user(user_id=10, role="owner"):
    return SimpleNamespace(id=user_id, role=role)


@pytest.mark.parametrize(
    ("data", "content_type"),
    [
        (b"\xff\xd8\xffrest", "image/jpeg"),
        (b"\x89PNG\r\n\x1a\nrest", "image/png"),
        (b"RIFFxxxxWEBPrest", "image/webp"),
        (b"xxxxftypavifrest", "image/avif"),
    ],
)
def test_media_type_is_detected_from_file_signature(data, content_type):
    assert MediaStorageService._detected_type(data) == content_type


@pytest.mark.asyncio
async def test_upload_rejects_non_image_content_before_s3_call():
    service = MediaStorageService(AsyncMock())
    service.venues.get_by_id = AsyncMock(
        return_value=SimpleNamespace(id=7, owner_id=10)
    )
    file = UploadFile(filename="fake.jpg", file=BytesIO(b"not really an image"))

    with pytest.raises(HTTPException) as error:
        await service.upload(file, user(), venue_id=7)

    assert error.value.status_code == 415


@pytest.mark.asyncio
async def test_upload_rejects_file_above_configured_limit(monkeypatch):
    monkeypatch.setattr(settings, "MEDIA_MAX_UPLOAD_BYTES", 8)
    service = MediaStorageService(AsyncMock())
    service.venues.get_by_id = AsyncMock(
        return_value=SimpleNamespace(id=7, owner_id=10)
    )
    file = UploadFile(filename="large.png", file=BytesIO(b"\x89PNG\r\n\x1a\nmore"))

    with pytest.raises(HTTPException) as error:
        await service.upload(file, user(), venue_id=7)

    assert error.value.status_code == 413


@pytest.mark.asyncio
async def test_upload_requires_parent_owner_or_admin():
    service = MediaStorageService(AsyncMock())
    service.venues.get_by_id = AsyncMock(
        return_value=SimpleNamespace(id=7, owner_id=99)
    )
    file = UploadFile(filename="image.png", file=BytesIO(b"\x89PNG\r\n\x1a\n"))

    with pytest.raises(HTTPException) as error:
        await service.upload(file, user(), venue_id=7)

    assert error.value.status_code == 403
