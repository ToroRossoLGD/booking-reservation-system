from datetime import datetime

from sqlalchemy import exists, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.availability_exception import AvailabilityException
from app.models.availability_rule import AvailabilityRule
from app.models.reservation import Reservation
from app.models.resource import Resource
from app.models.venue import Venue


class ResourceRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    def _available_resource_conditions(
        self,
        start_time: datetime,
        end_time: datetime,
        minimum_capacity: int,
        query_text: str | None,
        resource_type: str | None,
    ) -> list:
        weekday = start_time.weekday()
        requested_start = start_time.time()
        requested_end = end_time.time()

        availability_rule_exists = exists(
            select(AvailabilityRule.id).where(
                AvailabilityRule.resource_id == Resource.id,
                AvailabilityRule.weekday == weekday,
                AvailabilityRule.start_time <= requested_start,
                AvailabilityRule.end_time >= requested_end,
            )
        )

        blocking_exception_exists = exists(
            select(AvailabilityException.id).where(
                AvailabilityException.resource_id == Resource.id,
                AvailabilityException.start_time < end_time,
                AvailabilityException.end_time > start_time,
            )
        )

        blocking_reservation_exists = exists(
            select(Reservation.id).where(
                Reservation.resource_id == Resource.id,
                Reservation.status.in_(["pending", "confirmed"]),
                Reservation.start_time < end_time,
                Reservation.end_time > start_time,
            )
        )

        conditions = [
            Resource.capacity >= minimum_capacity,
            availability_rule_exists,
            ~blocking_exception_exists,
            ~blocking_reservation_exists,
        ]

        if resource_type is not None:
            conditions.append(Resource.resource_type == resource_type)

        if query_text is not None:
            search_pattern = f"%{query_text}%"

            conditions.append(
                or_(
                    Resource.name.ilike(search_pattern),
                    Resource.resource_type.ilike(search_pattern),
                    Venue.name.ilike(search_pattern),
                    Venue.address.ilike(search_pattern),
                )
            )

        return conditions

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

    async def search_available(
        self,
        start_time: datetime,
        end_time: datetime,
        minimum_capacity: int,
        limit: int,
        offset: int,
        query_text: str | None = None,
        resource_type: str | None = None,
    ):
        conditions = self._available_resource_conditions(
            start_time=start_time,
            end_time=end_time,
            minimum_capacity=minimum_capacity,
            query_text=query_text,
            resource_type=resource_type,
        )

        query = (
            select(Resource, Venue)
            .join(Venue, Resource.venue_id == Venue.id)
            .where(*conditions)
            .order_by(Resource.id)
            .limit(limit)
            .offset(offset)
        )

        result = await self.db.execute(query)

        return result.all()

    async def count_available(
        self,
        start_time: datetime,
        end_time: datetime,
        minimum_capacity: int,
        query_text: str | None = None,
        resource_type: str | None = None,
    ) -> int:
        conditions = self._available_resource_conditions(
            start_time=start_time,
            end_time=end_time,
            minimum_capacity=minimum_capacity,
            query_text=query_text,
            resource_type=resource_type,
        )

        query = (
            select(func.count(Resource.id))
            .join(Venue, Resource.venue_id == Venue.id)
            .where(*conditions)
        )

        result = await self.db.execute(query)

        return result.scalar_one()
