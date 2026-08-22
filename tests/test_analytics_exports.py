import csv
import io
from datetime import UTC, date, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.services.analytics_export_service import AnalyticsExportService


def reservation(
    reservation_id: int,
    start: datetime,
    end: datetime,
    *,
    status: str = "confirmed",
    attendance_status: str = "scheduled",
    party_size: int = 1,
    user_id: int = 10,
    quoted_amount_cents: int = 5000,
    quoted_currency: str = "EUR",
    promotion_code: str | None = None,
):
    return SimpleNamespace(
        id=reservation_id,
        start_time=start,
        end_time=end,
        status=status,
        attendance_status=attendance_status,
        party_size=party_size,
        user_id=user_id,
        quoted_amount_cents=quoted_amount_cents,
        quoted_currency=quoted_currency,
        promotion_code=promotion_code,
    )


def resource(resource_id: int, name: str):
    return SimpleNamespace(id=resource_id, name=name)


def payment(
    amount_cents: int,
    *,
    currency: str = "EUR",
    status: str = "paid",
    refunded_amount_cents: int = 0,
    cancellation_fee_cents: int = 0,
):
    return SimpleNamespace(
        amount_cents=amount_cents,
        currency=currency,
        status=status,
        refunded_amount_cents=refunded_amount_cents,
        cancellation_fee_cents=cancellation_fee_cents,
        provider="mock",
    )


def parse_csv(content: str):
    return list(csv.DictReader(io.StringIO(content.lstrip("\ufeff"))))


def report_rows():
    return [
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
                datetime(2026, 8, 3, 12, tzinfo=UTC),
                datetime(2026, 8, 3, 13, tzinfo=UTC),
                status="cancelled",
                quoted_currency="USD",
            ),
            resource(21, "Studio"),
            payment(
                4000,
                currency="USD",
                status="partially_refunded",
                refunded_amount_cents=3000,
                cancellation_fee_cents=1000,
            ),
        ),
    ]


def export_service(rows=None):
    service = AnalyticsExportService(AsyncMock())
    service.analytics_service.load_venue_report_data = AsyncMock(
        return_value=(
            SimpleNamespace(id=7, name="City Sports", owner_id=10),
            report_rows() if rows is None else rows,
        )
    )
    return service


@pytest.mark.asyncio
async def test_daily_export_has_zero_activity_days_and_currency_columns():
    service = export_service()

    result = await service.export_csv(
        7,
        date(2026, 8, 1),
        date(2026, 8, 3),
        "daily",
        SimpleNamespace(id=10, role="owner"),
    )
    rows = parse_csv(result.content)

    assert result.filename == "venue-7-daily-2026-08-01-2026-08-03.csv"
    assert result.content.startswith("\ufeff")
    assert len(rows) == 3
    assert rows[1]["date"] == "2026-08-02"
    assert rows[1]["reservation_count"] == "0"
    assert rows[0]["gross_revenue_cents_EUR"] == "5000"
    assert rows[0]["gross_revenue_cents_USD"] == "0"
    assert rows[2]["refunded_amount_cents_USD"] == "3000"
    assert rows[2]["net_revenue_cents_USD"] == "1000"


@pytest.mark.asyncio
async def test_resource_export_contains_status_and_performance_breakdowns():
    service = export_service()

    result = await service.export_csv(
        7,
        date(2026, 8, 1),
        date(2026, 8, 3),
        "resources",
        SimpleNamespace(id=10, role="owner"),
    )
    rows = parse_csv(result.content)

    assert len(rows) == 2
    assert rows[0]["resource_name"] == "Court A"
    assert rows[0]["booked_minutes"] == "90"
    assert rows[0]["booked_capacity_minutes"] == "180"
    assert rows[0]["reservations_confirmed"] == "1"
    assert rows[1]["reservations_cancelled"] == "1"


@pytest.mark.asyncio
async def test_reservation_export_is_a_financial_ledger():
    service = export_service()

    result = await service.export_csv(
        7,
        date(2026, 8, 1),
        date(2026, 8, 3),
        "reservations",
        SimpleNamespace(id=10, role="owner"),
    )
    rows = parse_csv(result.content)

    assert len(rows) == 2
    assert rows[0]["duration_minutes"] == "90"
    assert rows[0]["booked_capacity_minutes"] == "180"
    assert rows[0]["net_payment_cents"] == "5000"
    assert rows[1]["payment_status"] == "partially_refunded"
    assert rows[1]["refunded_amount_cents"] == "3000"
    assert rows[1]["net_payment_cents"] == "1000"
    assert rows[1]["cancellation_fee_cents"] == "1000"


@pytest.mark.asyncio
async def test_reservation_export_handles_reservations_without_payments():
    rows = [
        (
            reservation(
                1,
                datetime(2026, 8, 1, 10, tzinfo=UTC),
                datetime(2026, 8, 1, 11, tzinfo=UTC),
                status="pending",
            ),
            resource(20, "Court"),
            None,
        )
    ]
    service = export_service(rows)

    result = await service.export_csv(
        7,
        date(2026, 8, 1),
        date(2026, 8, 1),
        "reservations",
        SimpleNamespace(id=10, role="owner"),
    )
    row = parse_csv(result.content)[0]

    assert row["payment_status"] == ""
    assert row["payment_amount_cents"] == ""
    assert row["net_payment_cents"] == ""


@pytest.mark.asyncio
async def test_csv_neutralizes_spreadsheet_formula_cells():
    rows = [
        (
            reservation(
                1,
                datetime(2026, 8, 1, 10, tzinfo=UTC),
                datetime(2026, 8, 1, 11, tzinfo=UTC),
                promotion_code='=HYPERLINK("https://example.test")',
            ),
            resource(20, "  +SUM(A1:A2)"),
            None,
        )
    ]
    service = export_service(rows)

    result = await service.export_csv(
        7,
        date(2026, 8, 1),
        date(2026, 8, 1),
        "reservations",
        SimpleNamespace(id=10, role="owner"),
    )
    row = parse_csv(result.content)[0]

    assert row["resource_name"].startswith("'")
    assert row["promotion_code"].startswith("'")


@pytest.mark.asyncio
async def test_export_reuses_analytics_authorization_and_date_validation():
    service = export_service([])
    user = SimpleNamespace(id=10, role="owner")

    await service.export_csv(
        7,
        date(2026, 8, 1),
        date(2026, 8, 3),
        "daily",
        user,
    )

    service.analytics_service.load_venue_report_data.assert_awaited_once_with(
        venue_id=7,
        start_date=date(2026, 8, 1),
        end_date=date(2026, 8, 3),
        current_user=user,
    )
