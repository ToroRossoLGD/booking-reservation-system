from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.payment import Payment, PaymentStatus
from app.models.reservation import Reservation
from app.models.resource import Resource
from app.models.user import User
from app.models.venue import Venue


class AdminRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def count_users(self) -> int:
        result = await self.db.execute(
            select(func.count(User.id))
        )
        return result.scalar_one()

    async def count_venues(self) -> int:
        result = await self.db.execute(
            select(func.count(Venue.id))
        )
        return result.scalar_one()

    async def count_resources(self) -> int:
        result = await self.db.execute(
            select(func.count(Resource.id))
        )
        return result.scalar_one()

    async def count_reservations(self) -> int:
        result = await self.db.execute(
            select(func.count(Reservation.id))
        )
        return result.scalar_one()

    async def count_reservations_by_status(self) -> dict[str, int]:
        result = await self.db.execute(
            select(
                Reservation.status,
                func.count(Reservation.id),
            )
            .group_by(Reservation.status)
        )

        return {
            status: count
            for status, count in result.all()
        }

    async def count_payments(self) -> int:
        result = await self.db.execute(
            select(func.count(Payment.id))
        )
        return result.scalar_one()

    async def get_total_revenue_cents(self) -> int:
        result = await self.db.execute(
            select(
                func.coalesce(
                    func.sum(Payment.amount_cents),
                    0,
                )
            ).where(
                Payment.status == PaymentStatus.PAID.value
            )
        )

        return result.scalar_one()