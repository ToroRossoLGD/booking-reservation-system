from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.payment import Payment, PaymentStatus
from app.models.reservation import Reservation
from app.models.resource import Resource
from app.models.venue import Venue


class OwnerRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def count_owner_venues(
        self,
        owner_id: int,
    ) -> int:
        result = await self.db.execute(
            select(func.count(Venue.id)).where(Venue.owner_id == owner_id)
        )

        return result.scalar_one()

    async def count_owner_resources(
        self,
        owner_id: int,
    ) -> int:
        result = await self.db.execute(
            select(func.count(Resource.id))
            .join(Venue, Resource.venue_id == Venue.id)
            .where(Venue.owner_id == owner_id)
        )

        return result.scalar_one()

    async def count_owner_reservations(
        self,
        owner_id: int,
    ) -> int:
        result = await self.db.execute(
            select(func.count(Reservation.id))
            .join(Resource, Reservation.resource_id == Resource.id)
            .join(Venue, Resource.venue_id == Venue.id)
            .where(Venue.owner_id == owner_id)
        )

        return result.scalar_one()

    async def count_owner_reservations_by_status(
        self,
        owner_id: int,
    ) -> dict[str, int]:
        result = await self.db.execute(
            select(
                Reservation.status,
                func.count(Reservation.id),
            )
            .join(Resource, Reservation.resource_id == Resource.id)
            .join(Venue, Resource.venue_id == Venue.id)
            .where(Venue.owner_id == owner_id)
            .group_by(Reservation.status)
        )

        return {status: count for status, count in result.all()}

    async def get_owner_total_revenue_cents(
        self,
        owner_id: int,
    ) -> int:
        result = await self.db.execute(
            select(
                func.coalesce(
                    func.sum(Payment.amount_cents),
                    0,
                )
            )
            .join(Reservation, Payment.reservation_id == Reservation.id)
            .join(Resource, Reservation.resource_id == Resource.id)
            .join(Venue, Resource.venue_id == Venue.id)
            .where(
                Venue.owner_id == owner_id,
                Payment.status == PaymentStatus.PAID.value,
            )
        )

        return result.scalar_one()

    async def get_owner_top_resources(
        self,
        owner_id: int,
        limit: int = 5,
    ):
        result = await self.db.execute(
            select(
                Resource.id,
                Resource.name,
                func.count(Reservation.id).label("reservation_count"),
            )
            .join(Venue, Resource.venue_id == Venue.id)
            .join(Reservation, Reservation.resource_id == Resource.id)
            .where(Venue.owner_id == owner_id)
            .group_by(Resource.id, Resource.name)
            .order_by(func.count(Reservation.id).desc())
            .limit(limit)
        )

        return result.all()
