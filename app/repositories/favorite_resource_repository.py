from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.favorite_resource import FavoriteResource
from app.models.resource import Resource
from app.models.venue import Venue


class FavoriteResourceRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_user_and_resource(
        self,
        user_id: int,
        resource_id: int,
    ) -> FavoriteResource | None:
        result = await self.db.execute(
            select(FavoriteResource).where(
                FavoriteResource.user_id == user_id,
                FavoriteResource.resource_id == resource_id,
            )
        )

        return result.scalar_one_or_none()

    async def create(
        self,
        favorite: FavoriteResource,
    ) -> FavoriteResource:
        self.db.add(favorite)
        await self.db.commit()
        await self.db.refresh(favorite)
        return favorite

    async def delete(
        self,
        favorite: FavoriteResource,
    ) -> None:
        await self.db.delete(favorite)
        await self.db.commit()

    async def get_user_favorites(
        self,
        user_id: int,
    ):
        result = await self.db.execute(
            select(FavoriteResource, Resource, Venue)
            .join(Resource, FavoriteResource.resource_id == Resource.id)
            .join(Venue, Resource.venue_id == Venue.id)
            .where(FavoriteResource.user_id == user_id)
            .order_by(FavoriteResource.created_at.desc())
        )

        return result.all()
