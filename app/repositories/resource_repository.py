from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.venue import Venue
from app.models.resource import Resource


class ResourceRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, resource: Resource) -> Resource:
        self.db.add(resource)
        await self.db.commit()
        await self.db.refresh(resource)
        return resource

    async def get_by_id(self, resource_id: int) -> Resource | None:
        result = await self.db.execute(
            select(Resource).where(Resource.id == resource_id)
        )
        return result.scalar_one_or_none()

    async def get_by_venue_id(self, venue_id: int) -> list[Resource]:
        result = await self.db.execute(
            select(Resource)
            .where(Resource.venue_id == venue_id)
            .order_by(Resource.id)
        )
        return list(result.scalars().all())

    async def delete(self, resource: Resource) -> None:
        await self.db.delete(resource)
        await self.db.commit()

    async def get_by_owner_id(
        self,
        owner_id: int,
    ):
        result = await self.db.execute(
            select(Resource, Venue)
            .join(Venue, Resource.venue_id == Venue.id)
            .where(Venue.owner_id == owner_id)
            .order_by(Resource.id)
        )

        return result.all()