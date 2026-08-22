from collections import Counter
from datetime import UTC, date, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.reservation import AttendanceStatus, ReservationStatus
from app.models.user import User
from app.schemas.demand_insights import (
    DemandBucket,
    DemandComparison,
    DemandPeriodSummary,
    HourlyDemand,
    MetricComparison,
    VenueDemandInsightsRead,
    WeekdayDemand,
)
from app.services.analytics_service import AnalyticsService


class DemandInsightsService:
    WEEKDAY_NAMES = (
        "Monday",
        "Tuesday",
        "Wednesday",
        "Thursday",
        "Friday",
        "Saturday",
        "Sunday",
    )
    LEAD_TIME_BUCKETS = (
        ("same_day", 24),
        ("1_to_3_days", 24 * 4),
        ("4_to_7_days", 24 * 8),
        ("8_to_30_days", 24 * 31),
        ("31_plus_days", None),
    )

    def __init__(self, db: AsyncSession):
        self.analytics_service = AnalyticsService(db)

    async def get_venue_demand_insights(
        self,
        venue_id: int,
        start_date: date,
        end_date: date,
        current_user: User,
    ) -> VenueDemandInsightsRead:
        venue, current_rows = await self.analytics_service.load_venue_report_data(
            venue_id, start_date, end_date, current_user
        )
        period_days = (end_date - start_date).days + 1
        previous_end = start_date - timedelta(days=1)
        previous_start = previous_end - timedelta(days=period_days - 1)
        _, previous_rows = await self.analytics_service.load_venue_report_data(
            venue_id, previous_start, previous_end, current_user
        )

        current = self._summarize(start_date, end_date, current_rows)
        previous = self._summarize(previous_start, previous_end, previous_rows)
        return VenueDemandInsightsRead(
            venue_id=venue.id,
            venue_name=venue.name,
            current_period=current,
            previous_period=previous,
            comparison=self._compare(current, previous),
        )

    @staticmethod
    def _rounded_average(total: float, count: int) -> float:
        return round(total / count, 2) if count else 0.0

    @classmethod
    def _summarize(cls, start_date: date, end_date: date, rows):
        customer_counts = Counter()
        weekday_counts = [0] * 7
        weekday_party_sizes = [0] * 7
        hour_counts = [0] * 24
        hour_party_sizes = [0] * 24
        lead_counts = {label: 0 for label, _ in cls.LEAD_TIME_BUCKETS}
        lead_hours_total = 0.0
        duration_minutes_total = 0
        party_size_total = 0
        booked_minutes = 0
        cancelled_count = 0
        no_show_count = 0
        net_revenue = Counter()

        for reservation, _resource, payment in rows:
            start_time = reservation.start_time.astimezone(UTC)
            weekday = start_time.weekday()
            hour = start_time.hour
            customer_counts[reservation.user_id] += 1
            weekday_counts[weekday] += 1
            weekday_party_sizes[weekday] += reservation.party_size
            hour_counts[hour] += 1
            hour_party_sizes[hour] += reservation.party_size
            party_size_total += reservation.party_size

            duration_minutes = max(
                0,
                int(
                    (reservation.end_time - reservation.start_time).total_seconds() / 60
                ),
            )
            duration_minutes_total += duration_minutes
            if reservation.status in AnalyticsService.BOOKED_STATUSES:
                booked_minutes += duration_minutes
            if reservation.status == ReservationStatus.CANCELLED.value:
                cancelled_count += 1
            if reservation.attendance_status == AttendanceStatus.NO_SHOW.value:
                no_show_count += 1

            created_at = reservation.created_at.astimezone(UTC)
            lead_hours = max(0.0, (start_time - created_at).total_seconds() / 3600)
            lead_hours_total += lead_hours
            for label, upper_bound in cls.LEAD_TIME_BUCKETS:
                if upper_bound is None or lead_hours < upper_bound:
                    lead_counts[label] += 1
                    break

            if (
                payment is not None
                and payment.status in AnalyticsService.REVENUE_PAYMENT_STATUSES
            ):
                net_revenue[payment.currency.upper()] += (
                    payment.amount_cents - payment.refunded_amount_cents
                )

        total = len(rows)
        unique_customers = len(customer_counts)
        repeat_customers = sum(count >= 2 for count in customer_counts.values())
        peak_weekday_index = cls._peak_index(weekday_counts)
        peak_hour = cls._peak_index(hour_counts)
        return DemandPeriodSummary(
            start_date=start_date,
            end_date=end_date,
            total_reservations=total,
            booked_minutes=booked_minutes,
            unique_customers=unique_customers,
            repeat_customers=repeat_customers,
            repeat_customer_rate_percent=cls._percentage(
                repeat_customers, unique_customers
            ),
            cancellation_rate_percent=cls._percentage(cancelled_count, total),
            no_show_rate_percent=cls._percentage(no_show_count, total),
            average_booking_lead_hours=cls._rounded_average(lead_hours_total, total),
            average_duration_minutes=cls._rounded_average(
                duration_minutes_total, total
            ),
            average_party_size=cls._rounded_average(party_size_total, total),
            peak_weekday=(
                cls.WEEKDAY_NAMES[peak_weekday_index]
                if peak_weekday_index is not None
                else None
            ),
            peak_hour_utc=peak_hour,
            net_revenue_by_currency=dict(sorted(net_revenue.items())),
            lead_time_distribution=[
                DemandBucket(
                    label=label,
                    reservation_count=lead_counts[label],
                    percentage=cls._percentage(lead_counts[label], total),
                )
                for label, _ in cls.LEAD_TIME_BUCKETS
            ],
            demand_by_weekday=[
                WeekdayDemand(
                    weekday=index,
                    weekday_name=name,
                    reservation_count=weekday_counts[index],
                    party_size_total=weekday_party_sizes[index],
                )
                for index, name in enumerate(cls.WEEKDAY_NAMES)
            ],
            demand_by_hour=[
                HourlyDemand(
                    hour_utc=hour,
                    reservation_count=hour_counts[hour],
                    party_size_total=hour_party_sizes[hour],
                )
                for hour in range(24)
            ],
        )

    @staticmethod
    def _peak_index(values: list[int]) -> int | None:
        if not values or max(values) == 0:
            return None
        return max(range(len(values)), key=values.__getitem__)

    @staticmethod
    def _percentage(numerator: int, denominator: int) -> float:
        return round(numerator / denominator * 100, 2) if denominator else 0.0

    @staticmethod
    def _metric(current: float, previous: float) -> MetricComparison:
        return MetricComparison(
            current=round(current, 2),
            previous=round(previous, 2),
            absolute_change=round(current - previous, 2),
            relative_change_percent=(
                round((current - previous) / previous * 100, 2)
                if previous != 0
                else None
            ),
        )

    @classmethod
    def _compare(
        cls, current: DemandPeriodSummary, previous: DemandPeriodSummary
    ) -> DemandComparison:
        currencies = sorted(
            set(current.net_revenue_by_currency) | set(previous.net_revenue_by_currency)
        )
        return DemandComparison(
            total_reservations=cls._metric(
                current.total_reservations, previous.total_reservations
            ),
            booked_minutes=cls._metric(current.booked_minutes, previous.booked_minutes),
            unique_customers=cls._metric(
                current.unique_customers, previous.unique_customers
            ),
            repeat_customer_rate_percent=cls._metric(
                current.repeat_customer_rate_percent,
                previous.repeat_customer_rate_percent,
            ),
            cancellation_rate_percent=cls._metric(
                current.cancellation_rate_percent,
                previous.cancellation_rate_percent,
            ),
            no_show_rate_percent=cls._metric(
                current.no_show_rate_percent, previous.no_show_rate_percent
            ),
            average_booking_lead_hours=cls._metric(
                current.average_booking_lead_hours,
                previous.average_booking_lead_hours,
            ),
            average_duration_minutes=cls._metric(
                current.average_duration_minutes,
                previous.average_duration_minutes,
            ),
            average_party_size=cls._metric(
                current.average_party_size, previous.average_party_size
            ),
            net_revenue_by_currency={
                currency: cls._metric(
                    current.net_revenue_by_currency.get(currency, 0),
                    previous.net_revenue_by_currency.get(currency, 0),
                )
                for currency in currencies
            },
        )
