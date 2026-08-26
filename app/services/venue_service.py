from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.models.venue import Venue
from app.repositories.venue_repository import VenueRepository
from app.schemas.venue import (
    VenueBookingRulesUpdate,
    VenueCancellationPolicyUpdate,
    VenueCreate,
)


class VenueService:
    def __init__(self, db: AsyncSession):
        self.venue_repository = VenueRepository(db)

    async def create_venue(
        self,
        data: VenueCreate,
        current_user: User,
    ) -> Venue:
        venue = Venue(
            name=data.name,
            description=data.description,
            address=data.address,
            latitude=data.latitude,
            longitude=data.longitude,
            owner_id=current_user.id,
            free_cancellation_hours=data.free_cancellation_hours,
            late_cancellation_refund_percent=(data.late_cancellation_refund_percent),
            minimum_booking_notice_minutes=data.minimum_booking_notice_minutes,
            maximum_advance_booking_days=data.maximum_advance_booking_days,
            minimum_booking_duration_minutes=data.minimum_booking_duration_minutes,
            maximum_booking_duration_minutes=data.maximum_booking_duration_minutes,
            max_active_reservations_per_customer=(
                data.max_active_reservations_per_customer
            ),
        )

        return await self.venue_repository.create(venue)

    async def update_cancellation_policy(
        self,
        venue_id: int,
        data: VenueCancellationPolicyUpdate,
        current_user: User,
    ) -> Venue:
        venue = await self.venue_repository.get_by_id(venue_id)
        if venue is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Venue not found",
            )
        if current_user.role != "admin" and venue.owner_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can update policies only for your own venues",
            )

        venue.free_cancellation_hours = data.free_cancellation_hours
        venue.late_cancellation_refund_percent = data.late_cancellation_refund_percent
        return await self.venue_repository.update(venue)

    async def update_booking_rules(
        self,
        venue_id: int,
        data: VenueBookingRulesUpdate,
        current_user: User,
    ) -> Venue:
        venue = await self.venue_repository.get_by_id(venue_id)
        if venue is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Venue not found",
            )
        if current_user.role != "admin" and venue.owner_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can update booking rules only for your own venues",
            )

        venue.minimum_booking_notice_minutes = data.minimum_booking_notice_minutes
        venue.maximum_advance_booking_days = data.maximum_advance_booking_days
        venue.minimum_booking_duration_minutes = data.minimum_booking_duration_minutes
        venue.maximum_booking_duration_minutes = data.maximum_booking_duration_minutes
        venue.max_active_reservations_per_customer = (
            data.max_active_reservations_per_customer
        )
        return await self.venue_repository.update(venue)

    async def get_all_venues(self) -> list[Venue]:
        return await self.venue_repository.get_all()

    async def get_venue_by_id(self, venue_id: int) -> Venue:
        venue = await self.venue_repository.get_by_id(venue_id)

        if venue is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Venue not found",
            )

        return venue

    async def search_venues(
        self,
        query_text: str,
        limit: int,
        offset: int,
    ) -> dict:
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

        items = await self.venue_repository.search(
            query_text=query_text.strip(),
            limit=limit,
            offset=offset,
        )

        total = await self.venue_repository.count_search(query_text=query_text.strip())

        return {
            "items": items,
            "total": total,
            "limit": limit,
            "offset": offset,
            "has_next": offset + limit < total,
        }
