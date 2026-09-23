import asyncio
import hashlib
import logging
from io import BytesIO
from uuid import uuid4

import boto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError
from fastapi import HTTPException
from PIL import Image, ImageOps, UnidentifiedImageError
from sqlalchemy import select

from app.core.config import settings
from app.models.property_listing import PropertyListing
from app.models.property_photo import PropertyPhoto
from app.models.venue import Venue
from app.schemas.property_listing import PropertyListingPage, PropertyListingRead
from app.schemas.property_photo import PropertyPhotoRead

logger = logging.getLogger(__name__)
MAX_PHOTOS = 12
MAX_PIXELS = 20_000_000


def prepare_photo(data):
    try:
        with Image.open(BytesIO(data)) as image:
            if (
                image.format not in {"JPEG", "PNG", "WEBP"}
                or getattr(image, "n_frames", 1) != 1
            ):
                raise HTTPException(415, "Use a still JPEG, PNG or WebP image")
            if image.width * image.height > MAX_PIXELS:
                raise HTTPException(413, "Image exceeds 20 megapixels")
            image.load()
            oriented = ImageOps.exif_transpose(image).convert("RGBA")
            oriented.thumbnail((2560, 2560), Image.Resampling.LANCZOS)
            # New pixels discard EXIF/GPS and other uploaded metadata.
            clean = Image.new("RGB", oriented.size, "white")
            clean.paste(oriented, mask=oriented.getchannel("A"))
            full = BytesIO()
            clean.save(full, "JPEG", quality=85)
            width, height = clean.size
            clean.thumbnail((640, 640), Image.Resampling.LANCZOS)
            thumbnail = BytesIO()
            clean.save(thumbnail, "JPEG", quality=80)
            return full.getvalue(), thumbnail.getvalue(), width, height
    except Image.DecompressionBombError as exc:
        raise HTTPException(413, "Image exceeds the pixel limit") from exc
    except (UnidentifiedImageError, OSError, ValueError, SyntaxError) as exc:
        raise HTTPException(415, "Image is invalid or damaged") from exc


class PropertyPhotoService:
    def __init__(self, db):
        self.db = db

    def storage(self):
        if not settings.PROPERTY_PHOTO_BUCKET:
            raise HTTPException(503, "Property photo storage is not configured")
        kwargs = dict(
            service_name="s3",
            region_name=settings.S3_REGION,
            config=Config(
                signature_version="s3v4",
                s3={"addressing_style": "path"},
                connect_timeout=5,
                read_timeout=20,
                retries={"max_attempts": 2},
            ),
        )
        if settings.S3_ENDPOINT_URL:
            kwargs["endpoint_url"] = settings.S3_ENDPOINT_URL
        if settings.S3_ACCESS_KEY_ID:
            kwargs.update(
                aws_access_key_id=settings.S3_ACCESS_KEY_ID,
                aws_secret_access_key=settings.S3_SECRET_ACCESS_KEY,
            )
        return boto3.client(**kwargs)

    async def listing(self, property_id, user=None, lock=False):
        query = select(PropertyListing).where(PropertyListing.id == property_id)
        if lock:
            query = query.with_for_update().execution_options(populate_existing=True)
        listing = await self.db.scalar(query)
        if listing is None:
            raise HTTPException(404, "Property not found")
        if user is None:
            if not listing.is_published:
                raise HTTPException(404, "Property not found")
        else:
            owner_id = await self.db.scalar(
                select(Venue.owner_id).where(Venue.id == listing.venue_id)
            )
            if user.role not in {"owner", "admin"} or (
                owner_id != user.id and user.role != "admin"
            ):
                raise HTTPException(403, "You do not manage this property")
        return listing

    async def rows(self, property_id):
        return list(
            await self.db.scalars(
                select(PropertyPhoto)
                .where(PropertyPhoto.property_id == property_id)
                .order_by(PropertyPhoto.position, PropertyPhoto.id)
            )
        )

    async def list(self, property_id, user=None):
        await self.listing(property_id, user)
        return await self.rows(property_id)

    async def enrich_page(self, page):
        page = PropertyListingPage.model_validate(page)
        if not page.items:
            return page
        photos = await self.db.scalars(
            select(PropertyPhoto)
            .where(PropertyPhoto.property_id.in_([item.id for item in page.items]))
            .order_by(PropertyPhoto.position, PropertyPhoto.id)
        )
        grouped = {}
        for photo in photos:
            grouped.setdefault(photo.property_id, []).append(
                PropertyPhotoRead.model_validate(photo)
            )
        page.items = [
            item.model_copy(update={"photos": grouped.get(item.id, [])})
            for item in page.items
        ]
        return page

    async def enrich_one(self, listing):
        return PropertyListingRead.model_validate(listing).model_copy(
            update={
                "photos": [
                    PropertyPhotoRead.model_validate(photo)
                    for photo in await self.rows(listing.id)
                ]
            }
        )

    async def cleanup(self, key):
        try:
            client = self.storage()
            for name in (key, key + ".thumb"):
                await asyncio.to_thread(
                    client.delete_object,
                    Bucket=settings.PROPERTY_PHOTO_BUCKET,
                    Key=name,
                )
        except (BotoCoreError, ClientError, HTTPException):
            logger.exception("Property photo cleanup failed for key %s", key)

    async def upload(self, property_id, file, request_id, user):
        await self.listing(property_id, user, lock=True)
        data = await file.read(
            min(settings.MEDIA_MAX_UPLOAD_BYTES, 10 * 1024 * 1024) + 1
        )
        if len(data) > min(settings.MEDIA_MAX_UPLOAD_BYTES, 10 * 1024 * 1024):
            raise HTTPException(413, "Image exceeds the upload limit")
        source_hash = hashlib.sha256(data).hexdigest()
        photos = await self.rows(property_id)
        previous = next(
            (photo for photo in photos if photo.request_id == str(request_id)), None
        )
        if previous:
            if previous.source_hash != source_hash:
                raise HTTPException(
                    409, "Request identifier already used for another image"
                )
            return previous
        if len(photos) >= MAX_PHOTOS:
            raise HTTPException(409, "A property can have at most 12 photos")
        full, thumb, width, height = await asyncio.to_thread(prepare_photo, data)
        client = self.storage()
        key = f"properties/{property_id}/{uuid4().hex}.jpg"
        try:
            for name, content in ((key, full), (key + ".thumb", thumb)):
                await asyncio.to_thread(
                    client.put_object,
                    Bucket=settings.PROPERTY_PHOTO_BUCKET,
                    Key=name,
                    Body=content,
                    ContentType="image/jpeg",
                )
        except (BotoCoreError, ClientError) as exc:
            await self.cleanup(key)
            raise HTTPException(502, "Photo upload failed") from exc
        photo = PropertyPhoto(
            property_id=property_id,
            request_id=str(request_id),
            source_hash=source_hash,
            object_key=key,
            position=max((photo.position for photo in photos), default=-1) + 1,
            width=width,
            height=height,
        )
        self.db.add(photo)
        try:
            await self.db.commit()
        except Exception:
            await self.db.rollback()
            await self.cleanup(key)
            raise
        await self.db.refresh(photo)
        return photo

    async def reorder(self, property_id, data, user):
        await self.listing(property_id, user, lock=True)
        photos = await self.rows(property_id)
        if len(data.photo_ids) != len(photos) or set(data.photo_ids) != {
            photo.id for photo in photos
        }:
            raise HTTPException(409, "Photo list changed. Refresh before reordering")
        positions = {photo_id: index for index, photo_id in enumerate(data.photo_ids)}
        for photo in photos:
            photo.position = positions[photo.id]
        await self.db.commit()
        return sorted(photos, key=lambda photo: photo.position)

    async def delete(self, property_id, photo_id, user):
        await self.listing(property_id, user, lock=True)
        photo = await self.db.scalar(
            select(PropertyPhoto).where(
                PropertyPhoto.id == photo_id, PropertyPhoto.property_id == property_id
            )
        )
        if photo is None:
            return
        key = photo.object_key
        await self.db.delete(photo)
        await self.db.commit()
        # Removing the row immediately revokes API access even if storage is down.
        await self.cleanup(key)

    async def image(self, property_id, photo_id, thumbnail=False, user=None):
        await self.listing(property_id, user)
        photo = await self.db.scalar(
            select(PropertyPhoto).where(
                PropertyPhoto.id == photo_id, PropertyPhoto.property_id == property_id
            )
        )
        if photo is None:
            raise HTTPException(404, "Photo not found")
        key = photo.object_key + (".thumb" if thumbnail else "")

        def download():
            response = self.storage().get_object(
                Bucket=settings.PROPERTY_PHOTO_BUCKET, Key=key
            )
            try:
                return response["Body"].read()
            finally:
                response["Body"].close()

        try:
            return await asyncio.to_thread(download)
        except ClientError as exc:
            if exc.response.get("Error", {}).get("Code") in {"NoSuchKey", "404"}:
                raise HTTPException(404, "Photo not found") from exc
            raise HTTPException(502, "Photo storage is unavailable") from exc
        except BotoCoreError as exc:
            raise HTTPException(502, "Photo storage is unavailable") from exc
