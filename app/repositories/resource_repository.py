from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.resource import Resource
from app.models.venue import Venue


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
            select(Resource).where(Resource.venue_id == venue_id).order_by(Resource.id)
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

    async def search(
        self,
        query_text: str,
        limit: int,
        offset: int,
        resource_type: str | None = None,
    ):
        search_pattern = f"%{query_text}%"

        query = (
            select(Resource, Venue)
            .join(Venue, Resource.venue_id == Venue.id)
            .where(
                or_(
                    Resource.name.ilike(search_pattern),
                    Resource.resource_type.ilike(search_pattern),
                    Venue.name.ilike(search_pattern),
                    Venue.address.ilike(search_pattern),
                )
            )
        )

        if resource_type is not None:
            query = query.where(Resource.resource_type == resource_type)

        query = query.order_by(Resource.id).limit(limit).offset(offset)

        result = await self.db.execute(query)

        return result.all()

    async def count_search(
        self,
        query_text: str,
        resource_type: str | None = None,
    ) -> int:
        search_pattern = f"%{query_text}%"

        query = (
            select(func.count(Resource.id))
            .join(Venue, Resource.venue_id == Venue.id)
            .where(
                or_(
                    Resource.name.ilike(search_pattern),
                    Resource.resource_type.ilike(search_pattern),
                    Venue.name.ilike(search_pattern),
                    Venue.address.ilike(search_pattern),
                )
            )
        )

        if resource_type is not None:
            query = query.where(Resource.resource_type == resource_type)

        result = await self.db.execute(query)

        return result.scalar_one()
