from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.payment import Payment
from app.models.reservation import Reservation
from app.models.resource import Resource


class AnalyticsRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_venue_reservation_rows(
        self,
        venue_id: int,
        start_time: datetime,
        end_time: datetime,
    ):
        result = await self.db.execute(
            select(Reservation, Resource, Payment)
            .join(Resource, Reservation.resource_id == Resource.id)
            .outerjoin(Payment, Payment.reservation_id == Reservation.id)
            .where(
                Resource.venue_id == venue_id,
                Reservation.start_time >= start_time,
                Reservation.start_time < end_time,
            )
            .order_by(Reservation.start_time, Reservation.id)
        )
        return result.all()
