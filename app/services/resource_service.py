from datetime import datetime

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.resource import Resource
from app.models.user import User
from app.repositories.reservation_repository import ReservationRepository
from app.repositories.resource_repository import ResourceRepository
from app.repositories.venue_repository import VenueRepository
from app.schemas.resource import (
    AvailableResourceListRead,
    AvailableResourceRead,
    ResourceCreate,
    ResourceListRead,
    ResourceSearchRead,
)


class ResourceService:
    def __init__(self, db: AsyncSession):
        self.resource_repository = ResourceRepository(db)
        self.reservation_repository = ReservationRepository(db)
        self.venue_repository = VenueRepository(db)

    async def create_resource(
        self,
        venue_id: int,
        data: ResourceCreate,
        current_user: User,
    ) -> Resource:
        venue = await self.venue_repository.get_by_id(venue_id)

        if venue is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Venue not found",
            )

        if current_user.role != "admin" and venue.owner_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can create resources only for your own venues",
            )

        resource = Resource(
            name=data.name,
            resource_type=data.resource_type,
            capacity=data.capacity,
            hourly_rate_cents=data.hourly_rate_cents,
            currency=data.currency.upper(),
            venue_id=venue_id,
        )

        return await self.resource_repository.create(resource)

    async def get_resources_by_venue(
        self,
        venue_id: int,
    ) -> list[Resource]:
        venue = await self.venue_repository.get_by_id(venue_id)

        if venue is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Venue not found",
            )

        return await self.resource_repository.get_by_venue_id(venue_id)

    async def get_resource_by_id(
        self,
        resource_id: int,
    ) -> Resource:
        resource = await self.resource_repository.get_by_id(resource_id)

        if resource is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Resource not found",
            )

        return resource

    async def delete_resource(
        self,
        resource_id: int,
        current_user: User,
    ) -> None:
        resource = await self.resource_repository.get_by_id(resource_id)

        if resource is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Resource not found",
            )

        venue = await self.venue_repository.get_by_id(resource.venue_id)

        if venue is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Venue not found",
            )

        if current_user.role != "admin" and venue.owner_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can delete resources only from your own venues",
            )

        await self.resource_repository.delete(resource)

    async def search_resources(
        self,
        query_text: str,
        limit: int,
        offset: int,
        resource_type: str | None = None,
    ) -> ResourceListRead:
        if len(query_text.strip()) < 2:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Search query must contain at least 2 characters",
            )

        if limit < 1 or limit > 100:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="limit must be between 1 and 100",
            )

        if offset < 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="offset must be greater than or equal to 0",
            )

        clean_resource_type = (
            resource_type.strip()
            if resource_type is not None and resource_type.strip()
            else None
        )

        rows = await self.resource_repository.search(
            query_text=query_text.strip(),
            limit=limit,
            offset=offset,
            resource_type=clean_resource_type,
        )

        total = await self.resource_repository.count_search(
            query_text=query_text.strip(),
            resource_type=clean_resource_type,
        )

        items = [
            ResourceSearchRead(
                id=resource.id,
                name=resource.name,
                resource_type=resource.resource_type,
                capacity=resource.capacity,
                hourly_rate_cents=resource.hourly_rate_cents,
                currency=resource.currency,
                venue_id=venue.id,
                venue_name=venue.name,
                venue_address=venue.address,
            )
            for resource, venue in rows
        ]

        return ResourceListRead(
            items=items,
            total=total,
            limit=limit,
            offset=offset,
            has_next=offset + limit < total,
        )

    async def search_available_resources(
        self,
        start_time: datetime,
        end_time: datetime,
        minimum_capacity: int,
        limit: int,
        offset: int,
        query_text: str | None = None,
        resource_type: str | None = None,
    ) -> AvailableResourceListRead:
        if start_time.tzinfo is None or end_time.tzinfo is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=("start_time and end_time must include timezone information"),
            )

        if start_time >= end_time:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Start time must be before end time",
            )

        if start_time.date() != end_time.date():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    "Available resource search currently supports "
                    "only same-day intervals"
                ),
            )

        if minimum_capacity < 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="minimum_capacity must be greater than 0",
            )

        if limit < 1 or limit > 100:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="limit must be between 1 and 100",
            )

        if offset < 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="offset must be greater than or equal to 0",
            )

        clean_query = (
            query_text.strip()
            if query_text is not None and query_text.strip()
            else None
        )

        if clean_query is not None and len(clean_query) < 2:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=("Search query must contain at least 2 characters"),
            )

        clean_resource_type = (
            resource_type.strip()
            if resource_type is not None and resource_type.strip()
            else None
        )

        candidate_rows = await self.resource_repository.get_available_candidates(
            start_time=start_time,
            end_time=end_time,
            minimum_capacity=minimum_capacity,
            query_text=clean_query,
            resource_type=clean_resource_type,
        )

        available_rows = []
        for resource, venue in candidate_rows:
            (
                _capacity,
                remaining,
            ) = await self.reservation_repository.get_capacity_availability(
                resource.id, start_time, end_time
            )
            if remaining >= minimum_capacity:
                available_rows.append((resource, venue, remaining))

        total = len(available_rows)
        rows = available_rows[offset : offset + limit]

        items = [
            AvailableResourceRead(
                id=resource.id,
                name=resource.name,
                resource_type=resource.resource_type,
                capacity=resource.capacity,
                hourly_rate_cents=resource.hourly_rate_cents,
                currency=resource.currency,
                venue_id=venue.id,
                venue_name=venue.name,
                venue_address=venue.address,
                remaining_capacity=remaining,
            )
            for resource, venue, remaining in rows
        ]

        return AvailableResourceListRead(
            items=items,
            start_time=start_time,
            end_time=end_time,
            total=total,
            limit=limit,
            offset=offset,
            has_next=offset + limit < total,
        )
