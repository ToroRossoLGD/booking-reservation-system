from datetime import UTC, date, datetime, time, timedelta

from fastapi import BackgroundTasks, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.cache import (
    build_available_slots_cache_key,
    delete_available_slots_cache_for_resource,
    get_cache,
    set_cache,
)
from app.core.config import settings
from app.models.reservation import Reservation, ReservationStatus
from app.models.user import User
from app.repositories.reservation_repository import ReservationRepository
from app.repositories.resource_repository import ResourceRepository
from app.repositories.venue_repository import VenueRepository
from app.schemas.reservation import ReservationCreate
from app.services.notification_service import NotificationService


class ReservationService:
    def __init__(self, db: AsyncSession):
        self.reservation_repository = ReservationRepository(db)
        self.resource_repository = ResourceRepository(db)
        self.venue_repository = VenueRepository(db)
        self.notification_service = NotificationService(db)

    async def create_reservation(
        self,
        data: ReservationCreate,
        current_user: User,
        background_tasks: BackgroundTasks | None = None,
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

        created_reservation = await self.reservation_repository.create(reservation)

        await delete_available_slots_cache_for_resource(data.resource_id)

        await self.notification_service.create_notification(
            user_id=current_user.id,
            title="Reservation created",
            message=f"Your reservation #{created_reservation.id} has been created.",
            user_email=current_user.email,
            background_tasks=background_tasks,
        )

        return created_reservation

    async def get_my_reservations(
        self,
        current_user: User,
        limit: int,
        offset: int,
        status_filter: str | None = None,
    ) -> dict:
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

        valid_statuses = {
            ReservationStatus.PENDING.value,
            ReservationStatus.CONFIRMED.value,
            ReservationStatus.CANCELLED.value,
            ReservationStatus.COMPLETED.value,
            ReservationStatus.EXPIRED.value,
        }

        if status_filter is not None and status_filter not in valid_statuses:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid reservation status filter",
            )

        items = await self.reservation_repository.get_user_reservations(
            user_id=current_user.id,
            limit=limit,
            offset=offset,
            status=status_filter,
        )

        total = await self.reservation_repository.count_user_reservations(
            user_id=current_user.id,
            status=status_filter,
        )

        return {
            "items": items,
            "total": total,
            "limit": limit,
            "offset": offset,
            "has_next": offset + limit < total,
        }

    async def cancel_reservation(
        self,
        reservation_id: int,
        current_user: User,
    ) -> Reservation:
        reservation = await self.reservation_repository.get_by_id(reservation_id)

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

        updated_reservation = await self.reservation_repository.update(reservation)

        await self.notification_service.create_notification(
            user_id=reservation.user_id,
            title="Reservation cancelled",
            message=f"Your reservation #{reservation.id} has been cancelled.",
        )

        await delete_available_slots_cache_for_resource(reservation.resource_id)

        return updated_reservation

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

        resource = await self.resource_repository.get_by_id(reservation.resource_id)

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
        reservation = await self.reservation_repository.get_by_id(reservation_id)

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

        updated_reservation = await self.reservation_repository.update(reservation)

        await self.notification_service.create_notification(
            user_id=reservation.user_id,
            title="Reservation confirmed",
            message=f"Your reservation #{reservation.id} has been confirmed.",
        )

        await delete_available_slots_cache_for_resource(reservation.resource_id)

        return updated_reservation

    async def complete_reservation(
        self,
        reservation_id: int,
        current_user: User,
    ) -> Reservation:
        reservation = await self.reservation_repository.get_by_id(reservation_id)

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

        updated_reservation = await self.reservation_repository.update(reservation)

        await self.notification_service.create_notification(
            user_id=reservation.user_id,
            title="Reservation completed",
            message=f"Your reservation #{reservation.id} has been completed.",
        )

        await delete_available_slots_cache_for_resource(reservation.resource_id)

        return updated_reservation

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

        cache_key = build_available_slots_cache_key(
            resource_id=resource_id,
            selected_date=selected_date,
            slot_minutes=slot_minutes,
        )

        cached_slots = await get_cache(cache_key)

        if cached_slots is not None:
            return cached_slots

        resource = await self.resource_repository.get_by_id(resource_id)

        if resource is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Resource not found",
            )

        working_start = datetime.combine(
            selected_date,
            time(hour=9, minute=0),
            tzinfo=UTC,
        )

        working_end = datetime.combine(
            selected_date,
            time(hour=17, minute=0),
            tzinfo=UTC,
        )

        slots = []
        current_start = working_start
        slot_delta = timedelta(minutes=slot_minutes)

        while current_start + slot_delta <= working_end:
            current_end = current_start + slot_delta

            has_conflict = (
                await self.reservation_repository.has_conflicting_reservation(
                    resource_id=resource_id,
                    start_time=current_start,
                    end_time=current_end,
                )
            )

            slots.append(
                {
                    "start_time": current_start,
                    "end_time": current_end,
                    "available": not has_conflict,
                }
            )

            current_start = current_end

        await set_cache(
            key=cache_key,
            value=slots,
        )

        return slots

    async def expire_pending_reservations(self) -> dict:
        cutoff_time = datetime.now(UTC) - timedelta(
            minutes=settings.RESERVATION_EXPIRE_MINUTES
        )

        expired_reservations = (
            await self.reservation_repository.get_expired_pending_reservations(
                older_than=cutoff_time
            )
        )

        expired_count = 0

        for reservation in expired_reservations:
            reservation.status = ReservationStatus.EXPIRED.value

            await self.reservation_repository.update(reservation)

            await delete_available_slots_cache_for_resource(reservation.resource_id)

            expired_count += 1

        return {"expired_count": expired_count}
