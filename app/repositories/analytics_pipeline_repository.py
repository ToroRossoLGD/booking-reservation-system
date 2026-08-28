from datetime import UTC, date, datetime, time, timedelta

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.analytics_metric import DailyResourceMetric, DailyVenueMetric
from app.models.payment import Payment
from app.models.reservation import Reservation
from app.models.resource import Resource


class AnalyticsPipelineRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_source_rows(self, start_date: date, end_date: date):
        start_time = datetime.combine(start_date, time.min, tzinfo=UTC)
        end_time = datetime.combine(end_date + timedelta(days=1), time.min, tzinfo=UTC)
        result = await self.db.execute(
            select(Reservation, Resource, Payment)
            .join(Resource, Reservation.resource_id == Resource.id)
            .outerjoin(Payment, Payment.reservation_id == Reservation.id)
            .where(
                Reservation.start_time >= start_time,
                Reservation.start_time < end_time,
            )
            .order_by(Reservation.start_time, Reservation.id)
        )
        return result.all()

    async def replace_range(
        self,
        start_date: date,
        end_date: date,
        venue_metrics: list[DailyVenueMetric],
        resource_metrics: list[DailyResourceMetric],
    ) -> None:
        filters = (
            DailyResourceMetric.metric_date >= start_date,
            DailyResourceMetric.metric_date <= end_date,
        )
        await self.db.execute(delete(DailyResourceMetric).where(*filters))
        await self.db.execute(
            delete(DailyVenueMetric).where(
                DailyVenueMetric.metric_date >= start_date,
                DailyVenueMetric.metric_date <= end_date,
            )
        )
        self.db.add_all([*venue_metrics, *resource_metrics])
        await self.db.commit()

    async def get_venue_metrics(
        self, venue_id: int, start_date: date, end_date: date
    ) -> list[DailyVenueMetric]:
        result = await self.db.execute(
            select(DailyVenueMetric)
            .where(
                DailyVenueMetric.venue_id == venue_id,
                DailyVenueMetric.metric_date >= start_date,
                DailyVenueMetric.metric_date <= end_date,
            )
            .order_by(DailyVenueMetric.metric_date)
        )
        return list(result.scalars().all())
