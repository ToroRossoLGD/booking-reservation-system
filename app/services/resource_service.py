from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.resource import Resource
from app.models.user import User
from app.repositories.resource_repository import ResourceRepository
from app.repositories.venue_repository import VenueRepository
from app.schemas.resource import ResourceCreate


class ResourceService:
    def __init__(self, db: AsyncSession):
        self.resource_repository = ResourceRepository(db)
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