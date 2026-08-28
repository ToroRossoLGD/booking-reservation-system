from collections import defaultdict
from datetime import UTC, date, datetime, timedelta

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.analytics_metric import DailyResourceMetric, DailyVenueMetric
from app.models.reservation import AttendanceStatus, ReservationStatus
from app.models.user import User
from app.repositories.analytics_pipeline_repository import AnalyticsPipelineRepository
from app.repositories.venue_repository import VenueRepository
from app.schemas.analytics_pipeline import AnalyticsPipelineRunRead
from app.services.analytics_service import AnalyticsService


class AnalyticsPipelineService:
    MAX_BACKFILL_DAYS = 366
    ADDITIVE_FIELDS = (
        "reservation_count",
        "booked_minutes",
        "booked_capacity_minutes",
        "cancelled_count",
        "no_show_count",
    )

    def __init__(self, db: AsyncSession):
        self.repository = AnalyticsPipelineRepository(db)
        self.venue_repository = VenueRepository(db)

    async def refresh(
        self, start_date: date, end_date: date
    ) -> AnalyticsPipelineRunRead:
        self._validate_range(start_date, end_date)
        rows = await self.repository.get_source_rows(start_date, end_date)
        venue_metrics, resource_metrics = self._aggregate(rows)
        checks = self._validate_reconciliation(venue_metrics, resource_metrics)
        await self.repository.replace_range(
            start_date, end_date, venue_metrics, resource_metrics
        )
        return AnalyticsPipelineRunRead(
            start_date=start_date,
            end_date=end_date,
            source_reservation_count=len(rows),
            venue_metric_count=len(venue_metrics),
            resource_metric_count=len(resource_metrics),
            quality_checks_passed=checks,
        )

    async def get_venue_metrics(
        self,
        venue_id: int,
        start_date: date,
        end_date: date,
        current_user: User,
    ) -> list[DailyVenueMetric]:
        AnalyticsService._validate_date_range(start_date, end_date)
        venue = await self.venue_repository.get_by_id(venue_id)
        if venue is None:
            raise HTTPException(status_code=404, detail="Venue not found")
        if current_user.role != "admin" and venue.owner_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can view analytics only for your own venues",
            )
        return await self.repository.get_venue_metrics(
            venue_id, start_date, end_date
        )

    @classmethod
    def _validate_range(cls, start_date: date, end_date: date) -> None:
        if end_date < start_date:
            raise ValueError("end_date must be on or after start_date")
        if (end_date - start_date).days + 1 > cls.MAX_BACKFILL_DAYS:
            raise ValueError(
                f"Analytics backfills cannot exceed {cls.MAX_BACKFILL_DAYS} days"
            )

    @staticmethod
    def _bucket(metric_date: date, venue_id: int, resource_id: int | None = None):
        return {
            "metric_date": metric_date,
            "venue_id": venue_id,
            "resource_id": resource_id,
            "reservation_count": 0,
            "customers": set(),
            "booked_minutes": 0,
            "booked_capacity_minutes": 0,
            "cancelled_count": 0,
            "no_show_count": 0,
            "reservations_by_status": {
                item.value: 0 for item in ReservationStatus
            },
            "revenue_by_currency": {},
        }

    @classmethod
    def _aggregate(cls, rows):
        venue_buckets = defaultdict(lambda: None)
        resource_buckets = defaultdict(lambda: None)
        for reservation, resource, payment in rows:
            metric_date = reservation.start_time.astimezone(UTC).date()
            venue_key = (metric_date, resource.venue_id)
            resource_key = (metric_date, resource.id)
            if venue_buckets[venue_key] is None:
                venue_buckets[venue_key] = cls._bucket(metric_date, resource.venue_id)
            if resource_buckets[resource_key] is None:
                resource_buckets[resource_key] = cls._bucket(
                    metric_date, resource.venue_id, resource.id
                )
            for bucket in (venue_buckets[venue_key], resource_buckets[resource_key]):
                cls._add_reservation(bucket, reservation, payment)

        refreshed_at = datetime.now(UTC)
        venues = [
            DailyVenueMetric(
                **cls._model_values(values), refreshed_at=refreshed_at
            )
            for values in venue_buckets.values()
        ]
        resources = [
            DailyResourceMetric(
                **cls._model_values(values), refreshed_at=refreshed_at
            )
            for values in resource_buckets.values()
        ]
        return venues, resources

    @classmethod
    def _add_reservation(cls, bucket: dict, reservation, payment) -> None:
        bucket["reservation_count"] += 1
        bucket["customers"].add(reservation.user_id)
        statuses = bucket["reservations_by_status"]
        statuses[reservation.status] = statuses.get(reservation.status, 0) + 1
        if reservation.status in AnalyticsService.BOOKED_STATUSES:
            minutes = max(
                0,
                int(
                    (reservation.end_time - reservation.start_time).total_seconds()
                    / 60
                ),
            )
            bucket["booked_minutes"] += minutes
            bucket["booked_capacity_minutes"] += minutes * reservation.party_size
        if reservation.status == ReservationStatus.CANCELLED.value:
            bucket["cancelled_count"] += 1
        if reservation.attendance_status == AttendanceStatus.NO_SHOW.value:
            bucket["no_show_count"] += 1
        if payment and payment.status in AnalyticsService.REVENUE_PAYMENT_STATUSES:
            currency = payment.currency.upper()
            revenue = bucket["revenue_by_currency"].setdefault(
                currency, {"gross": 0, "refunded": 0, "net": 0}
            )
            revenue["gross"] += payment.amount_cents
            revenue["refunded"] += payment.refunded_amount_cents
            revenue["net"] += payment.amount_cents - payment.refunded_amount_cents

    @staticmethod
    def _model_values(values: dict) -> dict:
        result = {key: value for key, value in values.items() if key != "customers"}
        result["unique_customer_count"] = len(values["customers"])
        if result["resource_id"] is None:
            result.pop("resource_id")
        return result

    @classmethod
    def _validate_reconciliation(cls, venues, resources) -> int:
        resource_groups = defaultdict(list)
        for metric in resources:
            resource_groups[(metric.metric_date, metric.venue_id)].append(metric)
        checks = 0
        for venue in venues:
            children = resource_groups[(venue.metric_date, venue.venue_id)]
            for field in cls.ADDITIVE_FIELDS:
                resource_total = sum(
                    getattr(item, field) for item in children
                )
                if getattr(venue, field) != resource_total:
                    raise ValueError(
                        f"Analytics reconciliation failed for {field} on "
                        f"venue {venue.venue_id}, {venue.metric_date}"
                    )
                checks += 1
            currencies = set(venue.revenue_by_currency)
            currencies.update(
                currency
                for child in children
                for currency in child.revenue_by_currency
            )
            for currency in currencies:
                for field in ("gross", "refunded", "net"):
                    venue_value = venue.revenue_by_currency.get(currency, {}).get(
                        field, 0
                    )
                    resource_value = sum(
                        child.revenue_by_currency.get(currency, {}).get(field, 0)
                        for child in children
                    )
                    if venue_value != resource_value:
                        raise ValueError(
                            f"Revenue reconciliation failed for {currency} {field}"
                        )
                    checks += 1
        return checks

    async def refresh_yesterday(self) -> AnalyticsPipelineRunRead:
        yesterday = datetime.now(UTC).date() - timedelta(days=1)
        return await self.refresh(yesterday, yesterday)
