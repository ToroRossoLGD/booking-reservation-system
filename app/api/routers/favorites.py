from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.favorite_resource import (
    FavoriteResourceDetailsRead,
    FavoriteResourceRead,
)
from app.services.favorite_resource_service import FavoriteResourceService

router = APIRouter(
    prefix="/favorites",
    tags=["Favorites"],
)


@router.post(
    "/resources/{resource_id}",
    response_model=FavoriteResourceRead,
    status_code=status.HTTP_201_CREATED,
)
async def add_favorite_resource(
    resource_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = FavoriteResourceService(db)

    return await service.add_favorite(
        resource_id=resource_id,
        current_user=current_user,
    )


@router.get(
    "/resources",
    response_model=list[FavoriteResourceDetailsRead],
)
async def get_my_favorite_resources(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = FavoriteResourceService(db)

    return await service.get_my_favorites(
        current_user=current_user,
    )


@router.delete(
    "/resources/{resource_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def remove_favorite_resource(
    resource_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = FavoriteResourceService(db)

    await service.remove_favorite(
        resource_id=resource_id,
        current_user=current_user,
    )
