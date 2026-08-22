from collections import defaultdict
from datetime import UTC, date, datetime, time, timedelta

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.payment import PaymentStatus
from app.models.reservation import AttendanceStatus, ReservationStatus
from app.models.user import User
from app.repositories.analytics_repository import AnalyticsRepository
from app.repositories.venue_repository import VenueRepository
from app.schemas.analytics import (
    DailyAnalytics,
    ResourceAnalytics,
    RevenueAnalytics,
    VenueAnalyticsRead,
)


class AnalyticsService:
    MAX_DATE_RANGE_DAYS = 366
    REVENUE_PAYMENT_STATUSES = {
        PaymentStatus.PAID.value,
        PaymentStatus.PARTIALLY_REFUNDED.value,
        PaymentStatus.REFUNDED.value,
    }
    BOOKED_STATUSES = {
        ReservationStatus.PENDING.value,
        ReservationStatus.CONFIRMED.value,
        ReservationStatus.COMPLETED.value,
    }

    def __init__(self, db: AsyncSession):
        self.repository = AnalyticsRepository(db)
        self.venue_repository = VenueRepository(db)

    async def get_venue_analytics(
        self,
        venue_id: int,
        start_date: date,
        end_date: date,
        current_user: User,
    ) -> VenueAnalyticsRead:
        venue, rows = await self.load_venue_report_data(
            venue_id=venue_id,
            start_date=start_date,
            end_date=end_date,
            current_user=current_user,
        )
        return self._aggregate(venue, start_date, end_date, rows)

    async def load_venue_report_data(
        self,
        venue_id: int,
        start_date: date,
        end_date: date,
        current_user: User,
    ):
        self._validate_date_range(start_date, end_date)
        venue = await self.venue_repository.get_by_id(venue_id)
        if venue is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Venue not found",
            )
        if current_user.role != "admin" and venue.owner_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can view analytics only for your own venues",
            )

        start_time = datetime.combine(start_date, time.min, tzinfo=UTC)
        end_time = datetime.combine(end_date + timedelta(days=1), time.min, tzinfo=UTC)
        rows = await self.repository.get_venue_reservation_rows(
            venue_id, start_time, end_time
        )
        return venue, rows

    @classmethod
    def _validate_date_range(cls, start_date: date, end_date: date) -> None:
        if end_date < start_date:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="end_date must be on or after start_date",
            )
        if (end_date - start_date).days + 1 > cls.MAX_DATE_RANGE_DAYS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Date range cannot exceed {cls.MAX_DATE_RANGE_DAYS} days",
            )

    @staticmethod
    def _empty_revenue() -> dict[str, int]:
        return {"gross": 0, "refunded": 0, "net": 0}

    @classmethod
    def _add_revenue(cls, target: dict, payment) -> None:
        if payment is None or payment.status not in cls.REVENUE_PAYMENT_STATUSES:
            return
        currency = payment.currency.upper()
        totals = target.setdefault(currency, cls._empty_revenue())
        refunded = payment.refunded_amount_cents
        totals["gross"] += payment.amount_cents
        totals["refunded"] += refunded
        totals["net"] += payment.amount_cents - refunded

    @staticmethod
    def _revenue_models(values: dict) -> dict[str, RevenueAnalytics]:
        return {
            currency: RevenueAnalytics(
                gross_revenue_cents=totals["gross"],
                refunded_amount_cents=totals["refunded"],
                net_revenue_cents=totals["net"],
            )
            for currency, totals in sorted(values.items())
        }

    @classmethod
    def _aggregate(cls, venue, start_date: date, end_date: date, rows):
        statuses = {status.value: 0 for status in ReservationStatus}
        revenue: dict = {}
        daily = {}
        current_date = start_date
        while current_date <= end_date:
            daily[current_date] = {
                "count": 0,
                "booked_minutes": 0,
                "capacity_minutes": 0,
                "cancelled": 0,
                "no_show": 0,
                "revenue": {},
            }
            current_date += timedelta(days=1)

        resources = defaultdict(
            lambda: {
                "name": "",
                "count": 0,
                "booked_minutes": 0,
                "capacity_minutes": 0,
                "statuses": {status.value: 0 for status in ReservationStatus},
                "revenue": {},
            }
        )
        booked_minutes = 0
        booked_capacity_minutes = 0
        cancelled_count = 0
        no_show_count = 0

        for reservation, resource, payment in rows:
            reservation_date = reservation.start_time.astimezone(UTC).date()
            day = daily[reservation_date]
            resource_data = resources[resource.id]
            resource_data["name"] = resource.name

            statuses[reservation.status] = statuses.get(reservation.status, 0) + 1
            day["count"] += 1
            resource_data["count"] += 1
            resource_statuses = resource_data["statuses"]
            resource_statuses[reservation.status] = (
                resource_statuses.get(reservation.status, 0) + 1
            )

            if reservation.status in cls.BOOKED_STATUSES:
                duration = max(
                    0,
                    int(
                        (reservation.end_time - reservation.start_time).total_seconds()
                        / 60
                    ),
                )
                capacity_minutes = duration * reservation.party_size
                booked_minutes += duration
                booked_capacity_minutes += capacity_minutes
                day["booked_minutes"] += duration
                day["capacity_minutes"] += capacity_minutes
                resource_data["booked_minutes"] += duration
                resource_data["capacity_minutes"] += capacity_minutes

            if reservation.status == ReservationStatus.CANCELLED.value:
                cancelled_count += 1
                day["cancelled"] += 1
            if reservation.attendance_status == AttendanceStatus.NO_SHOW.value:
                no_show_count += 1
                day["no_show"] += 1

            cls._add_revenue(revenue, payment)
            cls._add_revenue(day["revenue"], payment)
            cls._add_revenue(resource_data["revenue"], payment)

        total = len(rows)
        daily_models = [
            DailyAnalytics(
                date=day_date,
                reservation_count=values["count"],
                booked_minutes=values["booked_minutes"],
                booked_capacity_minutes=values["capacity_minutes"],
                cancelled_count=values["cancelled"],
                no_show_count=values["no_show"],
                revenue_by_currency=cls._revenue_models(values["revenue"]),
            )
            for day_date, values in daily.items()
        ]
        resource_models = [
            ResourceAnalytics(
                resource_id=resource_id,
                resource_name=values["name"],
                reservation_count=values["count"],
                booked_minutes=values["booked_minutes"],
                booked_capacity_minutes=values["capacity_minutes"],
                reservations_by_status=values["statuses"],
                revenue_by_currency=cls._revenue_models(values["revenue"]),
            )
            for resource_id, values in resources.items()
        ]
        resource_models.sort(
            key=lambda item: (-item.reservation_count, item.resource_id)
        )

        return VenueAnalyticsRead(
            venue_id=venue.id,
            venue_name=venue.name,
            start_date=start_date,
            end_date=end_date,
            total_reservations=total,
            reservations_by_status=statuses,
            booked_minutes=booked_minutes,
            booked_capacity_minutes=booked_capacity_minutes,
            cancellation_rate_percent=round(cancelled_count / total * 100, 2)
            if total
            else 0.0,
            no_show_rate_percent=round(no_show_count / total * 100, 2)
            if total
            else 0.0,
            revenue_by_currency=cls._revenue_models(revenue),
            daily=daily_models,
            resources=resource_models,
        )
