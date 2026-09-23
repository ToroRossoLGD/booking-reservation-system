from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, Response, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import require_roles
from app.db.session import get_db
from app.models.user import User
from app.schemas.property_photo import PropertyPhotoOrder, PropertyPhotoRead
from app.services.property_photo_service import PropertyPhotoService

router = APIRouter(tags=["Property photos"])


def image_response(content):
    return Response(
        content,
        media_type="image/jpeg",
        headers={
            "Cache-Control": "private, no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.get("/properties/{property_id}/photos/{photo_id}/image")
async def public_image(
    property_id: int,
    photo_id: int,
    thumbnail: bool = False,
    db: AsyncSession = Depends(get_db),
):
    return image_response(
        await PropertyPhotoService(db).image(property_id, photo_id, thumbnail)
    )


@router.get("/owner/properties/{property_id}/photos/{photo_id}/image")
async def owner_image(
    property_id: int,
    photo_id: int,
    thumbnail: bool = False,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_roles("owner", "admin")),
):
    return image_response(
        await PropertyPhotoService(db).image(property_id, photo_id, thumbnail, user)
    )


@router.get(
    "/owner/properties/{property_id}/photos", response_model=list[PropertyPhotoRead]
)
async def owner_photos(
    property_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_roles("owner", "admin")),
):
    return await PropertyPhotoService(db).list(property_id, user)


@router.post(
    "/owner/properties/{property_id}/photos",
    response_model=PropertyPhotoRead,
    status_code=201,
)
async def upload(
    property_id: int,
    file: UploadFile = File(...),
    request_id: UUID = Form(...),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_roles("owner", "admin")),
):
    return await PropertyPhotoService(db).upload(property_id, file, request_id, user)


@router.put(
    "/owner/properties/{property_id}/photos/order",
    response_model=list[PropertyPhotoRead],
)
async def reorder(
    property_id: int,
    data: PropertyPhotoOrder,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_roles("owner", "admin")),
):
    return await PropertyPhotoService(db).reorder(property_id, data, user)


@router.delete("/owner/properties/{property_id}/photos/{photo_id}", status_code=204)
async def delete(
    property_id: int,
    photo_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_roles("owner", "admin")),
):
    await PropertyPhotoService(db).delete(property_id, photo_id, user)
