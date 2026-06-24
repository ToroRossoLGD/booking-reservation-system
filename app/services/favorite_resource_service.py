from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.favorite_resource import FavoriteResource
from app.models.user import User
from app.repositories.favorite_resource_repository import FavoriteResourceRepository
from app.repositories.resource_repository import ResourceRepository
from app.schemas.favorite_resource import (
    FavoriteResourceDetailsRead,
)


class FavoriteResourceService:
    def __init__(self, db: AsyncSession):
        self.favorite_repository = FavoriteResourceRepository(db)
        self.resource_repository = ResourceRepository(db)

    async def add_favorite(
        self,
        resource_id: int,
        current_user: User,
    ) -> FavoriteResource:
        resource = await self.resource_repository.get_by_id(resource_id)

        if resource is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Resource not found",
            )

        existing_favorite = await self.favorite_repository.get_by_user_and_resource(
            user_id=current_user.id,
            resource_id=resource_id,
        )

        if existing_favorite is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Resource is already in favorites",
            )

        favorite = FavoriteResource(
            user_id=current_user.id,
            resource_id=resource_id,
        )

        return await self.favorite_repository.create(favorite)

    async def remove_favorite(
        self,
        resource_id: int,
        current_user: User,
    ) -> None:
        favorite = await self.favorite_repository.get_by_user_and_resource(
            user_id=current_user.id,
            resource_id=resource_id,
        )

        if favorite is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Favorite resource not found",
            )

        await self.favorite_repository.delete(favorite)

    async def get_my_favorites(
        self,
        current_user: User,
    ) -> list[FavoriteResourceDetailsRead]:
        rows = await self.favorite_repository.get_user_favorites(current_user.id)

        return [
            FavoriteResourceDetailsRead(
                favorite_id=favorite.id,
                resource_id=resource.id,
                resource_name=resource.name,
                resource_type=resource.resource_type,
                capacity=resource.capacity,
                venue_id=venue.id,
                venue_name=venue.name,
                venue_address=venue.address,
                created_at=favorite.created_at,
            )
            for favorite, resource, venue in rows
        ]
