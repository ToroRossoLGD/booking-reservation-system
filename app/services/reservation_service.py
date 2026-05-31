from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.reservation import Reservation
from app.models.user import User
from app.repositories.reservation_repository import ReservationRepository
from app.schemas.reservation import ReservationCreate


class ReservationService:
    def __init__(self, db: AsyncSession):
        self.reservation_repository = ReservationRepository(db)

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