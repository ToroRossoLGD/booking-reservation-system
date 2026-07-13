from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.cache import (
    delete_available_slots_cache_for_resource,
)
from app.models.availability_exception import AvailabilityException
from app.models.user import User, UserRole
from app.repositories.availability_exception_repository import (
    AvailabilityExceptionRepository,
)
from app.repositories.resource_repository import ResourceRepository
from app.repositories.venue_repository import VenueRepository
from app.schemas.availability_exception import (
    AvailabilityExceptionCreate,
)


class AvailabilityExceptionService:
    def __init__(self, db: AsyncSession):
        self.exception_repository = AvailabilityExceptionRepository(db)
        self.resource_repository = ResourceRepository(db)
        self.venue_repository = VenueRepository(db)

    async def _validate_resource_management_permission(
        self,
        resource_id: int,
        current_user: User,
    ):
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

        is_admin = current_user.role == UserRole.ADMIN.value
        is_owner = venue.owner_id == current_user.id

        if not is_admin and not is_owner:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    "You can manage availability exceptions only "
                    "for resources in your own venues"
                ),
            )

        return resource

    async def create_exception(
        self,
        resource_id: int,
        data: AvailabilityExceptionCreate,
        current_user: User,
    ) -> AvailabilityException:
        await self._validate_resource_management_permission(
            resource_id=resource_id,
            current_user=current_user,
        )

        has_overlap = await self.exception_repository.has_overlapping_exception(
            resource_id=resource_id,
            start_time=data.start_time,
            end_time=data.end_time,
        )

        if has_overlap:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=("Availability exception overlaps with an existing exception"),
            )

        exception = AvailabilityException(
            resource_id=resource_id,
            start_time=data.start_time,
            end_time=data.end_time,
            reason=data.reason,
        )

        created_exception = await self.exception_repository.create(exception)

        await delete_available_slots_cache_for_resource(resource_id)

        return created_exception

    async def get_resource_exceptions(
        self,
        resource_id: int,
    ) -> list[AvailabilityException]:
        resource = await self.resource_repository.get_by_id(resource_id)

        if resource is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Resource not found",
            )

        return await self.exception_repository.get_for_resource(resource_id)

    async def delete_exception(
        self,
        resource_id: int,
        exception_id: int,
        current_user: User,
    ) -> None:
        await self._validate_resource_management_permission(
            resource_id=resource_id,
            current_user=current_user,
        )

        exception = await self.exception_repository.get_by_id(exception_id)

        if exception is None or exception.resource_id != resource_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Availability exception not found",
            )

        await self.exception_repository.delete(exception)

        await delete_available_slots_cache_for_resource(resource_id)
