from datetime import UTC, date, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.services.demand_insights_service import DemandInsightsService


def reservation(
    reservation_id: int,
    start: datetime,
    end: datetime,
    created_at: datetime,
    *,
    user_id: int,
    status: str = "confirmed",
    attendance_status: str = "scheduled",
    party_size: int = 1,
):
    return SimpleNamespace(
        id=reservation_id,
        start_time=start,
        end_time=end,
        created_at=created_at,
        user_id=user_id,
        status=status,
        attendance_status=attendance_status,
        party_size=party_size,
    )


def payment(
    amount_cents: int,
    *,
    currency: str = "EUR",
    status: str = "paid",
    refunded_amount_cents: int = 0,
):
    return SimpleNamespace(
        amount_cents=amount_cents,
        currency=currency,
        status=status,
        refunded_amount_cents=refunded_amount_cents,
    )


RESOURCE = SimpleNamespace(id=20, name="Court")
VENUE = SimpleNamespace(id=7, name="City Sports", owner_id=10)
OWNER = SimpleNamespace(id=10, role="owner")


def current_rows():
    return [
        (
            reservation(
                1,
                datetime(2026, 8, 10, 10, tzinfo=UTC),
                datetime(2026, 8, 10, 11, tzinfo=UTC),
                datetime(2026, 8, 10, 8, tzinfo=UTC),
                user_id=1,
                party_size=2,
            ),
            RESOURCE,
            payment(5000),
        ),
        (
            reservation(
                2,
                datetime(2026, 8, 10, 10, tzinfo=UTC),
                datetime(2026, 8, 10, 11, tzinfo=UTC),
                datetime(2026, 8, 8, 10, tzinfo=UTC),
                user_id=1,
                status="cancelled",
            ),
            RESOURCE,
            payment(
                4000,
                status="partially_refunded",
                refunded_amount_cents=3000,
            ),
        ),
        (
            reservation(
                3,
                datetime(2026, 8, 11, 15, tzinfo=UTC),
                datetime(2026, 8, 11, 17, tzinfo=UTC),
                datetime(2026, 8, 1, 15, tzinfo=UTC),
                user_id=2,
                status="completed",
                attendance_status="no_show",
                party_size=3,
            ),
            RESOURCE,
            payment(2000, currency="USD"),
        ),
    ]


def previous_rows():
    return [
        (
            reservation(
                10,
                datetime(2026, 8, 3, 9, tzinfo=UTC),
                datetime(2026, 8, 3, 10, tzinfo=UTC),
                datetime(2026, 8, 1, 9, tzinfo=UTC),
                user_id=3,
            ),
            RESOURCE,
            payment(1500),
        ),
        (
            reservation(
                11,
                datetime(2026, 8, 4, 9, tzinfo=UTC),
                datetime(2026, 8, 4, 10, tzinfo=UTC),
                datetime(2026, 8, 2, 9, tzinfo=UTC),
                user_id=4,
            ),
            RESOURCE,
            payment(1500),
        ),
    ]


@pytest.mark.asyncio
async def test_demand_insights_compare_with_immediately_preceding_period():
    service = DemandInsightsService(AsyncMock())
    service.analytics_service.load_venue_report_data = AsyncMock(
        side_effect=[(VENUE, current_rows()), (VENUE, previous_rows())]
    )

    result = await service.get_venue_demand_insights(
        venue_id=7,
        start_date=date(2026, 8, 8),
        end_date=date(2026, 8, 14),
        current_user=OWNER,
    )

    assert result.previous_period.start_date == date(2026, 8, 1)
    assert result.previous_period.end_date == date(2026, 8, 7)
    assert result.current_period.total_reservations == 3
    assert result.previous_period.total_reservations == 2
    assert result.comparison.total_reservations.absolute_change == 1
    assert result.comparison.total_reservations.relative_change_percent == 50
    assert service.analytics_service.load_venue_report_data.await_args_list[1].args == (
        7,
        date(2026, 8, 1),
        date(2026, 8, 7),
        OWNER,
    )


@pytest.mark.asyncio
async def test_demand_summary_exposes_customer_and_peak_patterns():
    service = DemandInsightsService(AsyncMock())
    service.analytics_service.load_venue_report_data = AsyncMock(
        side_effect=[(VENUE, current_rows()), (VENUE, [])]
    )

    result = await service.get_venue_demand_insights(
        7, date(2026, 8, 8), date(2026, 8, 14), OWNER
    )
    summary = result.current_period

    assert summary.unique_customers == 2
    assert summary.repeat_customers == 1
    assert summary.repeat_customer_rate_percent == 50
    assert summary.peak_weekday == "Monday"
    assert summary.peak_hour_utc == 10
    assert summary.average_booking_lead_hours == 96.67
    assert summary.average_duration_minutes == 80
    assert summary.average_party_size == 2
    assert summary.booked_minutes == 180
    assert summary.cancellation_rate_percent == 33.33
    assert summary.no_show_rate_percent == 33.33
    assert len(summary.demand_by_weekday) == 7
    assert len(summary.demand_by_hour) == 24
    assert summary.demand_by_weekday[0].reservation_count == 2
    assert summary.demand_by_hour[10].party_size_total == 3


@pytest.mark.asyncio
async def test_lead_time_distribution_uses_non_overlapping_buckets():
    service = DemandInsightsService(AsyncMock())
    service.analytics_service.load_venue_report_data = AsyncMock(
        side_effect=[(VENUE, current_rows()), (VENUE, [])]
    )

    result = await service.get_venue_demand_insights(
        7, date(2026, 8, 8), date(2026, 8, 14), OWNER
    )
    buckets = {
        bucket.label: bucket for bucket in result.current_period.lead_time_distribution
    }

    assert buckets["same_day"].reservation_count == 1
    assert buckets["1_to_3_days"].reservation_count == 1
    assert buckets["8_to_30_days"].reservation_count == 1
    assert sum(bucket.reservation_count for bucket in buckets.values()) == 3
    assert sum(bucket.percentage for bucket in buckets.values()) == 99.99


@pytest.mark.asyncio
async def test_net_revenue_comparison_preserves_currency_and_refunds():
    service = DemandInsightsService(AsyncMock())
    service.analytics_service.load_venue_report_data = AsyncMock(
        side_effect=[(VENUE, current_rows()), (VENUE, previous_rows())]
    )

    result = await service.get_venue_demand_insights(
        7, date(2026, 8, 8), date(2026, 8, 14), OWNER
    )

    assert result.current_period.net_revenue_by_currency == {
        "EUR": 6000,
        "USD": 2000,
    }
    assert result.comparison.net_revenue_by_currency["EUR"].absolute_change == 3000
    assert (
        result.comparison.net_revenue_by_currency["EUR"].relative_change_percent == 100
    )
    assert result.comparison.net_revenue_by_currency["USD"].previous == 0
    assert (
        result.comparison.net_revenue_by_currency["USD"].relative_change_percent is None
    )


@pytest.mark.asyncio
async def test_empty_period_has_complete_zero_filled_distributions():
    service = DemandInsightsService(AsyncMock())
    service.analytics_service.load_venue_report_data = AsyncMock(
        side_effect=[(VENUE, []), (VENUE, [])]
    )

    result = await service.get_venue_demand_insights(
        7, date(2026, 8, 8), date(2026, 8, 14), OWNER
    )
    summary = result.current_period

    assert summary.total_reservations == 0
    assert summary.peak_weekday is None
    assert summary.peak_hour_utc is None
    assert summary.repeat_customer_rate_percent == 0
    assert len(summary.demand_by_weekday) == 7
    assert len(summary.demand_by_hour) == 24
    assert all(item.reservation_count == 0 for item in summary.demand_by_hour)
    assert result.comparison.total_reservations.relative_change_percent is None


def test_metric_comparison_reports_absolute_and_relative_change():
    increase = DemandInsightsService._metric(125, 100)
    decrease = DemandInsightsService._metric(75, 100)
    new_metric = DemandInsightsService._metric(25, 0)

    assert increase.absolute_change == 25
    assert increase.relative_change_percent == 25
    assert decrease.absolute_change == -25
    assert decrease.relative_change_percent == -25
    assert new_metric.absolute_change == 25
    assert new_metric.relative_change_percent is None
