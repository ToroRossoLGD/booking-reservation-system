from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.reservation import Reservation, ReservationStatus
from app.models.user import User
from app.repositories.reservation_repository import ReservationRepository
from app.schemas.reservation import ReservationCreate
from app.repositories.resource_repository import ResourceRepository
from app.repositories.venue_repository import VenueRepository
from datetime import date, datetime, time, timedelta, timezone


class ReservationService:
    def __init__(self, db: AsyncSession):
        self.reservation_repository = ReservationRepository(db)
        self.resource_repository = ResourceRepository(db)
        self.venue_repository = VenueRepository(db)

    async def create_reservation(
        self,
        data: ReservationCreate,
        current_user: User,
    ) -> Reservation:

        if data.start_time >= data.end_time:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Start time must be before end time",
            )

        has_conflict = await self.reservation_repository.has_conflicting_reservation(
            resource_id=data.resource_id,
            start_time=data.start_time,
            end_time=data.end_time,
        )

        if has_conflict:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Resource is already booked for this time slot",
            )

        reservation = Reservation(
            start_time=data.start_time,
            end_time=data.end_time,
            user_id=current_user.id,
            resource_id=data.resource_id,
        )

        return await self.reservation_repository.create(reservation)

    async def get_my_reservations(
        self,
        current_user: User,
    ):
        return await self.reservation_repository.get_user_reservations(
            current_user.id
        )
    async def cancel_reservation(
        self,
        reservation_id: int,
        current_user: User,
    ) -> Reservation:
        reservation = await self.reservation_repository.get_by_id(
            reservation_id
        )

        if reservation is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Reservation not found",
            )

        if current_user.role != "admin" and reservation.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can cancel only your own reservations",
            )

        if reservation.status == ReservationStatus.CANCELLED.value:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Reservation is already cancelled",
            )

        reservation.status = ReservationStatus.CANCELLED.value

        return await self.reservation_repository.update(reservation)
    
    async def check_availability(
        self,
        resource_id: int,
        start_time,
        end_time,
    ) -> dict:
        if start_time >= end_time:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Start time must be before end time",
            )

        resource = await self.resource_repository.get_by_id(resource_id)

        if resource is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Resource not found",
            )

        has_conflict = await self.reservation_repository.has_conflicting_reservation(
            resource_id=resource_id,
            start_time=start_time,
            end_time=end_time,
        )

        return {
            "resource_id": resource_id,
            "start_time": start_time,
            "end_time": end_time,
            "available": not has_conflict,
        }
    
    async def _ensure_owner_can_manage_reservation(
        self,
        reservation: Reservation,
        current_user: User,
    ) -> None:
        if current_user.role == "admin":
            return

        resource = await self.resource_repository.get_by_id(
            reservation.resource_id
        )

        if resource is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Resource not found",
            )

        venue = await self.venue_repository.get_by_id(
            resource.venue_id
        )

        if venue is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Venue not found",
            )

        if venue.owner_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can manage only reservations for your own venues",
            )

    async def confirm_reservation(
        self,
        reservation_id: int,
        current_user: User,
    ) -> Reservation:
        reservation = await self.reservation_repository.get_by_id(
            reservation_id
        )

        if reservation is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Reservation not found",
            )

        await self._ensure_owner_can_manage_reservation(
            reservation,
            current_user,
        )

        if reservation.status != ReservationStatus.PENDING.value:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Only pending reservations can be confirmed",
            )

        reservation.status = ReservationStatus.CONFIRMED.value

        return await self.reservation_repository.update(reservation)

    async def complete_reservation(
        self,
        reservation_id: int,
        current_user: User,
    ) -> Reservation:
        reservation = await self.reservation_repository.get_by_id(
            reservation_id
        )

        if reservation is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Reservation not found",
            )

        await self._ensure_owner_can_manage_reservation(
            reservation,
            current_user,
        )

        if reservation.status != ReservationStatus.CONFIRMED.value:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Only confirmed reservations can be completed",
            )

        reservation.status = ReservationStatus.COMPLETED.value

        return await self.reservation_repository.update(reservation)
    
    async def get_available_slots(
        self,
        resource_id: int,
        selected_date: date,
        slot_minutes: int,
    ) -> list[dict]:
        if slot_minutes <= 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="slot_minutes must be greater than 0",
            )

        resource = await self.resource_repository.get_by_id(resource_id)

        if resource is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Resource not found",
            )

        working_start = datetime.combine(
            selected_date,
            time(hour=9, minute=0),
            tzinfo=timezone.utc,
        )

        working_end = datetime.combine(
            selected_date,
            time(hour=17, minute=0),
            tzinfo=timezone.utc,
        )

        slots = []
        current_start = working_start
        slot_delta = timedelta(minutes=slot_minutes)

        while current_start + slot_delta <= working_end:
            current_end = current_start + slot_delta

            has_conflict = await self.reservation_repository.has_conflicting_reservation(
                resource_id=resource_id,
                start_time=current_start,
                end_time=current_end,
            )

            slots.append(
                {
                    "start_time": current_start,
                    "end_time": current_end,
                    "available": not has_conflict,
                }
            )

            current_start = current_end

        return slots