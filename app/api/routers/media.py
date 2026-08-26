from fastapi import APIRouter, Depends, File, Form, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.media_asset import MediaAssetRead
from app.services.media_storage_service import MediaStorageService

router = APIRouter(tags=["Media"])


@router.get("/venues/{venue_id}/media", response_model=list[MediaAssetRead])
async def list_venue_media(venue_id: int, db: AsyncSession = Depends(get_db)):
    return await MediaStorageService(db).list(venue_id=venue_id)


@router.post(
    "/venues/{venue_id}/media",
    response_model=MediaAssetRead,
    status_code=status.HTTP_201_CREATED,
)
async def upload_venue_media(
    venue_id: int,
    file: UploadFile = File(...),
    caption: str | None = Form(default=None, max_length=500),
    sort_order: int = Form(default=0, ge=0, le=10_000),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await MediaStorageService(db).upload(
        file, current_user, venue_id=venue_id, caption=caption, sort_order=sort_order
    )


@router.get("/resources/{resource_id}/media", response_model=list[MediaAssetRead])
async def list_resource_media(resource_id: int, db: AsyncSession = Depends(get_db)):
    return await MediaStorageService(db).list(resource_id=resource_id)


@router.post(
    "/resources/{resource_id}/media",
    response_model=MediaAssetRead,
    status_code=status.HTTP_201_CREATED,
)
async def upload_resource_media(
    resource_id: int,
    file: UploadFile = File(...),
    caption: str | None = Form(default=None, max_length=500),
    sort_order: int = Form(default=0, ge=0, le=10_000),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await MediaStorageService(db).upload(
        file,
        current_user,
        resource_id=resource_id,
        caption=caption,
        sort_order=sort_order,
    )


@router.delete("/media/{asset_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_media(
    asset_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await MediaStorageService(db).delete(asset_id, current_user)
