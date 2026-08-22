from datetime import UTC, date, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException

from app.services.analytics_service import AnalyticsService


def reservation(
    reservation_id: int,
    start: datetime,
    end: datetime,
    *,
    status: str = "confirmed",
    party_size: int = 1,
    attendance_status: str = "scheduled",
):
    return SimpleNamespace(
        id=reservation_id,
        start_time=start,
        end_time=end,
        status=status,
        party_size=party_size,
        attendance_status=attendance_status,
    )


def resource(resource_id: int, name: str):
    return SimpleNamespace(id=resource_id, name=name)


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


@pytest.mark.asyncio
async def test_owner_gets_date_filtered_venue_analytics():
    service = AnalyticsService(AsyncMock())
    service.venue_repository.get_by_id = AsyncMock(
        return_value=SimpleNamespace(id=7, name="City Sports", owner_id=10)
    )
    service.repository.get_venue_reservation_rows = AsyncMock(
        return_value=[
            (
                reservation(
                    1,
                    datetime(2026, 8, 1, 10, tzinfo=UTC),
                    datetime(2026, 8, 1, 11, 30, tzinfo=UTC),
                    party_size=2,
                ),
                resource(20, "Court A"),
                payment(5000),
            ),
            (
                reservation(
                    2,
                    datetime(2026, 8, 1, 13, tzinfo=UTC),
                    datetime(2026, 8, 1, 14, tzinfo=UTC),
                    status="cancelled",
                ),
                resource(20, "Court A"),
                payment(
                    4000,
                    status="partially_refunded",
                    refunded_amount_cents=3000,
                ),
            ),
            (
                reservation(
                    3,
                    datetime(2026, 8, 3, 9, tzinfo=UTC),
                    datetime(2026, 8, 3, 10, tzinfo=UTC),
                    status="completed",
                    attendance_status="no_show",
                ),
                resource(21, "Studio"),
                payment(2000, currency="usd"),
            ),
        ]
    )

    result = await service.get_venue_analytics(
        venue_id=7,
        start_date=date(2026, 8, 1),
        end_date=date(2026, 8, 3),
        current_user=SimpleNamespace(id=10, role="owner"),
    )

    assert result.total_reservations == 3
    assert result.reservations_by_status["confirmed"] == 1
    assert result.reservations_by_status["cancelled"] == 1
    assert result.booked_minutes == 150
    assert result.booked_capacity_minutes == 240
    assert result.cancellation_rate_percent == 33.33
    assert result.no_show_rate_percent == 33.33
    assert result.revenue_by_currency["EUR"].gross_revenue_cents == 9000
    assert result.revenue_by_currency["EUR"].refunded_amount_cents == 3000
    assert result.revenue_by_currency["EUR"].net_revenue_cents == 6000
    assert result.revenue_by_currency["USD"].net_revenue_cents == 2000
    assert len(result.daily) == 3
    assert result.daily[1].date == date(2026, 8, 2)
    assert result.daily[1].reservation_count == 0
    assert [item.resource_id for item in result.resources] == [20, 21]
    assert result.resources[0].reservation_count == 2
    service.repository.get_venue_reservation_rows.assert_awaited_once_with(
        7,
        datetime(2026, 8, 1, tzinfo=UTC),
        datetime(2026, 8, 4, tzinfo=UTC),
    )


@pytest.mark.asyncio
async def test_analytics_excludes_pending_payment_from_revenue():
    service = AnalyticsService(AsyncMock())
    service.venue_repository.get_by_id = AsyncMock(
        return_value=SimpleNamespace(id=7, name="Venue", owner_id=10)
    )
    service.repository.get_venue_reservation_rows = AsyncMock(
        return_value=[
            (
                reservation(
                    1,
                    datetime(2026, 8, 1, 10, tzinfo=UTC),
                    datetime(2026, 8, 1, 11, tzinfo=UTC),
                    status="pending",
                ),
                resource(20, "Court"),
                payment(5000, status="pending"),
            )
        ]
    )

    result = await service.get_venue_analytics(
        7,
        date(2026, 8, 1),
        date(2026, 8, 1),
        SimpleNamespace(id=10, role="owner"),
    )

    assert result.revenue_by_currency == {}
    assert result.booked_minutes == 60


@pytest.mark.asyncio
async def test_admin_can_view_any_venue_analytics():
    service = AnalyticsService(AsyncMock())
    service.venue_repository.get_by_id = AsyncMock(
        return_value=SimpleNamespace(id=7, name="Venue", owner_id=10)
    )
    service.repository.get_venue_reservation_rows = AsyncMock(return_value=[])

    result = await service.get_venue_analytics(
        7,
        date(2026, 8, 1),
        date(2026, 8, 1),
        SimpleNamespace(id=99, role="admin"),
    )

    assert result.total_reservations == 0
    assert result.cancellation_rate_percent == 0
    assert result.no_show_rate_percent == 0


@pytest.mark.asyncio
async def test_owner_cannot_view_another_owners_analytics():
    service = AnalyticsService(AsyncMock())
    service.venue_repository.get_by_id = AsyncMock(
        return_value=SimpleNamespace(id=7, name="Venue", owner_id=10)
    )
    service.repository.get_venue_reservation_rows = AsyncMock()

    with pytest.raises(HTTPException) as error:
        await service.get_venue_analytics(
            7,
            date(2026, 8, 1),
            date(2026, 8, 1),
            SimpleNamespace(id=11, role="owner"),
        )

    assert error.value.status_code == 403
    service.repository.get_venue_reservation_rows.assert_not_awaited()


@pytest.mark.asyncio
async def test_missing_venue_returns_not_found():
    service = AnalyticsService(AsyncMock())
    service.venue_repository.get_by_id = AsyncMock(return_value=None)

    with pytest.raises(HTTPException) as error:
        await service.get_venue_analytics(
            404,
            date(2026, 8, 1),
            date(2026, 8, 1),
            SimpleNamespace(id=10, role="owner"),
        )

    assert error.value.status_code == 404


@pytest.mark.parametrize(
    ("start_date", "end_date", "detail"),
    [
        (
            date(2026, 8, 2),
            date(2026, 8, 1),
            "end_date must be on or after start_date",
        ),
        (
            date(2025, 1, 1),
            date(2026, 1, 2),
            "Date range cannot exceed 366 days",
        ),
    ],
)
def test_analytics_rejects_invalid_date_ranges(start_date, end_date, detail):
    with pytest.raises(HTTPException) as error:
        AnalyticsService._validate_date_range(start_date, end_date)

    assert error.value.status_code == 400
    assert error.value.detail == detail
