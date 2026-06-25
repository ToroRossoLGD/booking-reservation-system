from sqlalchemy.ext.asyncio import AsyncSession

from app.models.reservation import ReservationStatus
from app.models.user import User
from app.repositories.owner_repository import OwnerRepository
from app.repositories.reservation_repository import ReservationRepository
from app.repositories.resource_repository import ResourceRepository
from app.repositories.venue_repository import VenueRepository
from app.schemas.owner import (
    OwnerReservationRead,
    OwnerResourceRead,
    OwnerStatsRead,
    OwnerTopResourceRead,
)


class OwnerService:
    def __init__(self, db: AsyncSession):
        self.venue_repository = VenueRepository(db)
        self.resource_repository = ResourceRepository(db)
        self.reservation_repository = ReservationRepository(db)
        self.owner_repository = OwnerRepository(db)

    async def get_my_venues(
        self,
        current_user: User,
    ):
        return await self.venue_repository.get_by_owner_id(current_user.id)

    async def get_my_resources(
        self,
        current_user: User,
    ) -> list[OwnerResourceRead]:
        rows = await self.resource_repository.get_by_owner_id(current_user.id)

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
        rows = await self.reservation_repository.get_by_owner_id(current_user.id)

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

    async def get_owner_stats(
        self,
        current_user: User,
    ) -> OwnerStatsRead:
        reservations_by_status = (
            await self.owner_repository.count_owner_reservations_by_status(
                current_user.id
            )
        )

        normalized_statuses = {
            status.value: reservations_by_status.get(status.value, 0)
            for status in ReservationStatus
        }

        top_resource_rows = await self.owner_repository.get_owner_top_resources(
            owner_id=current_user.id
        )

        top_resources = [
            OwnerTopResourceRead(
                resource_id=resource_id,
                resource_name=resource_name,
                reservation_count=reservation_count,
            )
            for resource_id, resource_name, reservation_count in top_resource_rows
        ]

        return OwnerStatsRead(
            total_venues=await self.owner_repository.count_owner_venues(
                current_user.id
            ),
            total_resources=await self.owner_repository.count_owner_resources(
                current_user.id
            ),
            total_reservations=await self.owner_repository.count_owner_reservations(
                current_user.id
            ),
            reservations_by_status=normalized_statuses,
            total_revenue_cents=(
                await self.owner_repository.get_owner_total_revenue_cents(
                    current_user.id
                )
            ),
            top_resources=top_resources,
        )
