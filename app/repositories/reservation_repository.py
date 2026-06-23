from datetime import datetime

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.reservation import Reservation
from app.models.resource import Resource
from app.models.venue import Venue


class ReservationRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(
        self,
        reservation: Reservation,
    ) -> Reservation:
        self.db.add(reservation)
        await self.db.commit()
        await self.db.refresh(reservation)
        return reservation

    async def get_user_reservations(
        self,
        user_id: int,
        limit: int,
        offset: int,
        status: str | None = None,
    ) -> list[Reservation]:
        query = select(Reservation).where(Reservation.user_id == user_id)

        if status is not None:
            query = query.where(Reservation.status == status)

        query = (
            query.order_by(Reservation.start_time.desc()).limit(limit).offset(offset)
        )

        result = await self.db.execute(query)

        return list(result.scalars().all())

    async def has_conflicting_reservation(
        self,
        resource_id: int,
        start_time: datetime,
        end_time: datetime,
    ) -> bool:
        result = await self.db.execute(
            select(Reservation).where(
                and_(
                    Reservation.resource_id == resource_id,
                    Reservation.status.in_(["pending", "confirmed"]),
                    Reservation.start_time < end_time,
                    Reservation.end_time > start_time,
                )
            )
        )

        reservation = result.scalar_one_or_none()

        return reservation is not None

    async def get_by_id(
        self,
        reservation_id: int,
    ) -> Reservation | None:
        result = await self.db.execute(
            select(Reservation).where(Reservation.id == reservation_id)
        )

        return result.scalar_one_or_none()

    async def update(
        self,
        reservation: Reservation,
    ) -> Reservation:
        await self.db.commit()
        await self.db.refresh(reservation)
        return reservation

    async def get_by_owner_id(
        self,
        owner_id: int,
    ):
        result = await self.db.execute(
            select(Reservation, Resource, Venue)
            .join(Resource, Reservation.resource_id == Resource.id)
            .join(Venue, Resource.venue_id == Venue.id)
            .where(Venue.owner_id == owner_id)
            .order_by(Reservation.start_time)
        )

        return result.all()

    async def get_expired_pending_reservations(
        self,
        older_than,
    ) -> list[Reservation]:
        result = await self.db.execute(
            select(Reservation).where(
                Reservation.status == "pending",
                Reservation.created_at < older_than,
            )
        )

        return list(result.scalars().all())

    async def count_user_reservations(
        self,
        user_id: int,
        status: str | None = None,
    ) -> int:
        query = select(func.count(Reservation.id)).where(Reservation.user_id == user_id)

        if status is not None:
            query = query.where(Reservation.status == status)

        result = await self.db.execute(query)

        return result.scalar_one()
