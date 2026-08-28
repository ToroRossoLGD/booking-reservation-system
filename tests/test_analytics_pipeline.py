from datetime import UTC, date, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException

from app.services.analytics_pipeline_service import AnalyticsPipelineService


def source_row(
    reservation_id: int,
    *,
    resource_id: int = 20,
    venue_id: int = 7,
    user_id: int = 10,
    status: str = "confirmed",
    attendance_status: str = "scheduled",
    payment_status: str = "paid",
    currency: str = "EUR",
    amount_cents: int = 5000,
    refunded_amount_cents: int = 0,
):
    reservation = SimpleNamespace(
        id=reservation_id,
        user_id=user_id,
        start_time=datetime(2026, 8, 27, 10, tzinfo=UTC),
        end_time=datetime(2026, 8, 27, 11, 30, tzinfo=UTC),
        status=status,
        attendance_status=attendance_status,
        party_size=2,
    )
    resource = SimpleNamespace(id=resource_id, venue_id=venue_id)
    payment = SimpleNamespace(
        status=payment_status,
        currency=currency,
        amount_cents=amount_cents,
        refunded_amount_cents=refunded_amount_cents,
    )
    return reservation, resource, payment


@pytest.mark.asyncio
async def test_refresh_builds_reconciled_daily_metrics():
    service = AnalyticsPipelineService(AsyncMock())
    service.repository.get_source_rows = AsyncMock(
        return_value=[
            source_row(1),
            source_row(
                2,
                resource_id=21,
                user_id=10,
                status="cancelled",
                payment_status="partially_refunded",
                amount_cents=4000,
                refunded_amount_cents=3000,
            ),
            source_row(
                3,
                resource_id=21,
                user_id=11,
                status="completed",
                attendance_status="no_show",
                currency="usd",
                amount_cents=2000,
            ),
        ]
    )
    service.repository.replace_range = AsyncMock()

    result = await service.refresh(date(2026, 8, 27), date(2026, 8, 27))

    assert result.source_reservation_count == 3
    assert result.venue_metric_count == 1
    assert result.resource_metric_count == 2
    assert result.quality_checks_passed == 11
    args = service.repository.replace_range.await_args.args
    venue = args[2][0]
    assert venue.unique_customer_count == 2
    assert venue.booked_minutes == 180
    assert venue.booked_capacity_minutes == 360
    assert venue.cancelled_count == 1
    assert venue.no_show_count == 1
    assert venue.revenue_by_currency == {
        "EUR": {"gross": 9000, "refunded": 3000, "net": 6000},
        "USD": {"gross": 2000, "refunded": 0, "net": 2000},
    }


@pytest.mark.asyncio
async def test_refresh_is_idempotent_at_repository_boundary():
    service = AnalyticsPipelineService(AsyncMock())
    service.repository.get_source_rows = AsyncMock(return_value=[source_row(1)])
    service.repository.replace_range = AsyncMock()

    for _ in range(2):
        await service.refresh(date(2026, 8, 27), date(2026, 8, 27))

    assert service.repository.replace_range.await_count == 2
    for call in service.repository.replace_range.await_args_list:
        assert call.args[0:2] == (date(2026, 8, 27), date(2026, 8, 27))
        assert len(call.args[2]) == 1
        assert len(call.args[3]) == 1


@pytest.mark.asyncio
async def test_empty_backfill_replaces_range_with_no_metrics():
    service = AnalyticsPipelineService(AsyncMock())
    service.repository.get_source_rows = AsyncMock(return_value=[])
    service.repository.replace_range = AsyncMock()

    result = await service.refresh(date(2026, 8, 20), date(2026, 8, 21))

    assert result.source_reservation_count == 0
    service.repository.replace_range.assert_awaited_once_with(
        date(2026, 8, 20), date(2026, 8, 21), [], []
    )


def test_backfill_range_is_bounded():
    with pytest.raises(ValueError, match="cannot exceed 366 days"):
        AnalyticsPipelineService._validate_range(date(2025, 1, 1), date(2026, 1, 2))


@pytest.mark.asyncio
async def test_owner_cannot_read_another_venue_warehouse():
    service = AnalyticsPipelineService(AsyncMock())
    service.venue_repository.get_by_id = AsyncMock(
        return_value=SimpleNamespace(id=7, owner_id=99)
    )

    with pytest.raises(HTTPException) as exc_info:
        await service.get_venue_metrics(
            7,
            date(2026, 8, 1),
            date(2026, 8, 2),
            SimpleNamespace(id=10, role="owner"),
        )

    assert exc_info.value.status_code == 403
