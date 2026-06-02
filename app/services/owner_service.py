from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.repositories.reservation_repository import ReservationRepository
from app.repositories.resource_repository import ResourceRepository
from app.repositories.venue_repository import VenueRepository
from app.schemas.owner import (
    OwnerReservationRead,
    OwnerResourceRead,
)


class OwnerService:
    def __init__(self, db: AsyncSession):
        self.venue_repository = VenueRepository(db)
        self.resource_repository = ResourceRepository(db)
        self.reservation_repository = ReservationRepository(db)

    async def get_my_venues(
        self,
        current_user: User,
    ):
        return await self.venue_repository.get_by_owner_id(
            current_user.id
        )

    async def get_my_resources(
        self,
        current_user: User,
    ) -> list[OwnerResourceRead]:
        rows = await self.resource_repository.get_by_owner_id(
            current_user.id
        )

        return [
            OwnerResourceRead(
                id=resource.id,
                name=resource.name,
                resource_type=resource.resource_type,
                capacity=resource.capacity,
                venue_id=venue.id,
                venue_name=venue.name,
            )
            for resource, venue in rows
        ]

    async def get_my_reservations(
        self,
        current_user: User,
    ) -> list[OwnerReservationRead]:
        rows = await self.reservation_repository.get_by_owner_id(
            current_user.id
        )

        return [
            OwnerReservationRead(
                id=reservation.id,
                start_time=reservation.start_time,
                end_time=reservation.end_time,
                status=reservation.status,
                user_id=reservation.user_id,
                resource_id=resource.id,
                resource_name=resource.name,
                venue_id=venue.id,
                venue_name=venue.name,
            )
            for reservation, resource, venue in rows
        ]