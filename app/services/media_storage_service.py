import asyncio
from io import BytesIO
from pathlib import Path
from uuid import uuid4

import boto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError
from fastapi import HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.media_asset import MediaAsset
from app.models.user import User
from app.repositories.media_asset_repository import MediaAssetRepository
from app.repositories.resource_repository import ResourceRepository
from app.repositories.venue_repository import VenueRepository


class MediaStorageService:
    allowed_types = {
        "image/jpeg": ".jpg",
        "image/png": ".png",
        "image/webp": ".webp",
        "image/avif": ".avif",
    }

    def __init__(self, db: AsyncSession):
        self.assets = MediaAssetRepository(db)
        self.venues = VenueRepository(db)
        self.resources = ResourceRepository(db)

    def _client(self):
        if not settings.S3_BUCKET:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Media storage is not configured",
            )
        kwargs = {
            "service_name": "s3",
            "region_name": settings.S3_REGION,
            "config": Config(signature_version="s3v4", s3={"addressing_style": "path"}),
        }
        if settings.S3_ENDPOINT_URL:
            kwargs["endpoint_url"] = settings.S3_ENDPOINT_URL
        if settings.S3_ACCESS_KEY_ID:
            kwargs["aws_access_key_id"] = settings.S3_ACCESS_KEY_ID
            kwargs["aws_secret_access_key"] = settings.S3_SECRET_ACCESS_KEY
        return boto3.client(**kwargs)

    @staticmethod
    def _detected_type(data: bytes) -> str | None:
        if data.startswith(b"\xff\xd8\xff"):
            return "image/jpeg"
        if data.startswith(b"\x89PNG\r\n\x1a\n"):
            return "image/png"
        if data.startswith(b"RIFF") and data[8:12] == b"WEBP":
            return "image/webp"
        if (
            len(data) >= 12
            and data[4:8] == b"ftyp"
            and data[8:12] in {b"avif", b"avis"}
        ):
            return "image/avif"
        return None

    @staticmethod
    def _assert_owner(owner_id: int, current_user: User) -> None:
        if owner_id != current_user.id and current_user.role != "admin":
            raise HTTPException(status_code=403, detail="You do not manage this media")

    async def _parent_owner(self, venue_id: int | None, resource_id: int | None) -> int:
        if venue_id is not None:
            venue = await self.venues.get_by_id(venue_id)
        else:
            resource = await self.resources.get_by_id(resource_id or 0)
            venue = await self.venues.get_by_id(resource.venue_id) if resource else None
        if venue is None:
            raise HTTPException(status_code=404, detail="Venue or resource not found")
        return venue.owner_id

    def _url(self, object_key: str) -> str:
        if settings.S3_PUBLIC_BASE_URL:
            return f"{settings.S3_PUBLIC_BASE_URL.rstrip('/')}/{object_key}"
        return self._client().generate_presigned_url(
            "get_object",
            Params={"Bucket": settings.S3_BUCKET, "Key": object_key},
            ExpiresIn=settings.S3_PRESIGNED_URL_EXPIRE_SECONDS,
        )

    def serialize(self, asset: MediaAsset) -> dict:
        return {
            "id": asset.id,
            "venue_id": asset.venue_id,
            "resource_id": asset.resource_id,
            "original_filename": asset.original_filename,
            "content_type": asset.content_type,
            "size_bytes": asset.size_bytes,
            "caption": asset.caption,
            "sort_order": asset.sort_order,
            "created_at": asset.created_at,
            "url": self._url(asset.object_key),
        }

    async def upload(
        self,
        file: UploadFile,
        current_user: User,
        *,
        venue_id: int | None = None,
        resource_id: int | None = None,
        caption: str | None = None,
        sort_order: int = 0,
    ) -> dict:
        owner_id = await self._parent_owner(venue_id, resource_id)
        self._assert_owner(owner_id, current_user)
        data = await file.read(settings.MEDIA_MAX_UPLOAD_BYTES + 1)
        if len(data) > settings.MEDIA_MAX_UPLOAD_BYTES:
            raise HTTPException(
                status_code=413, detail="Image exceeds the upload limit"
            )
        detected_type = self._detected_type(data)
        if detected_type is None or detected_type not in self.allowed_types:
            raise HTTPException(
                status_code=415,
                detail="Only JPEG, PNG, WebP, and AVIF images are supported",
            )
        parent = (
            f"venues/{venue_id}" if venue_id is not None else f"resources/{resource_id}"
        )
        object_key = f"{parent}/{uuid4().hex}{self.allowed_types[detected_type]}"
        try:
            await asyncio.to_thread(
                self._client().upload_fileobj,
                BytesIO(data),
                settings.S3_BUCKET,
                object_key,
                ExtraArgs={"ContentType": detected_type},
            )
        except (BotoCoreError, ClientError) as exc:
            raise HTTPException(
                status_code=502, detail="Media storage upload failed"
            ) from exc
        asset = await self.assets.create(
            MediaAsset(
                venue_id=venue_id,
                resource_id=resource_id,
                object_key=object_key,
                original_filename=Path(file.filename or "image").name[:255],
                content_type=detected_type,
                size_bytes=len(data),
                caption=caption,
                sort_order=sort_order,
            )
        )
        return self.serialize(asset)

    async def list(
        self, *, venue_id: int | None = None, resource_id: int | None = None
    ) -> list[dict]:
        assets = (
            await self.assets.list_for_venue(venue_id)
            if venue_id is not None
            else await self.assets.list_for_resource(resource_id or 0)
        )
        return [self.serialize(asset) for asset in assets]

    async def delete(self, asset_id: int, current_user: User) -> None:
        asset = await self.assets.get_by_id(asset_id)
        if asset is None:
            raise HTTPException(status_code=404, detail="Media asset not found")
        owner_id = await self._parent_owner(asset.venue_id, asset.resource_id)
        self._assert_owner(owner_id, current_user)
        try:
            await asyncio.to_thread(
                self._client().delete_object,
                Bucket=settings.S3_BUCKET,
                Key=asset.object_key,
            )
        except (BotoCoreError, ClientError) as exc:
            raise HTTPException(
                status_code=502, detail="Media storage deletion failed"
            ) from exc
        await self.assets.delete(asset)
