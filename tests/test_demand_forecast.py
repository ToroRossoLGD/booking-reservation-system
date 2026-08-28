from datetime import date, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException

from app.schemas.demand_forecast import ForecastMetric
from app.services.demand_forecast_service import DemandForecastService


def metric_row(metric_date: date, value: int, *, net_revenue: int = 0):
    return SimpleNamespace(
        metric_date=metric_date,
        reservation_count=value,
        booked_minutes=value * 60,
        cancelled_count=value,
        no_show_count=value,
        revenue_by_currency={
            "EUR": {"gross": net_revenue, "refunded": 0, "net": net_revenue}
        },
    )


def owner(user_id: int = 10):
    return SimpleNamespace(id=user_id, role="owner")


def service_with_rows(rows):
    service = DemandForecastService(AsyncMock())
    service.venue_repository.get_by_id = AsyncMock(
        return_value=SimpleNamespace(id=7, owner_id=10)
    )
    service.repository.get_venue_metric_history = AsyncMock(return_value=rows)
    return service


@pytest.mark.asyncio
async def test_forecast_learns_weekday_seasonality_without_future_leakage():
    start = date(2026, 6, 1)
    rows = [
        metric_row(start + timedelta(days=index), 10 if index % 7 == 0 else 2)
        for index in range(56)
    ]
    service = service_with_rows(rows)

    result = await service.forecast(
        venue_id=7,
        metric=ForecastMetric.RESERVATIONS,
        as_of_date=start + timedelta(days=55),
        horizon_days=7,
        history_days=56,
        current_user=owner(),
    )

    assert result.model == "weekday-seasonal-trend-v1"
    assert result.forecasts[0].predicted == 10
    assert [point.predicted for point in result.forecasts[1:]] == [2] * 6
    assert result.accuracy.backtest_points == 42
    assert result.accuracy.mean_absolute_error == 0
    assert result.accuracy.mean_absolute_percentage_error == 0


@pytest.mark.asyncio
async def test_forecast_materializes_missing_dates_as_zero_activity():
    start = date(2026, 7, 1)
    rows = [metric_row(start, 7), metric_row(start + timedelta(days=13), 4)]
    service = service_with_rows(rows)

    result = await service.forecast(
        venue_id=7,
        metric=ForecastMetric.RESERVATIONS,
        as_of_date=start + timedelta(days=13),
        horizon_days=1,
        history_days=14,
        current_user=owner(),
    )

    assert result.history_days == 14
    # The missing observation for this weekday is included as zero: (7 + 0) / 2.
    assert result.forecasts[0].predicted == 3.5
    service.repository.get_venue_metric_history.assert_awaited_once_with(
        7, start, start + timedelta(days=13)
    )


@pytest.mark.asyncio
async def test_net_revenue_forecast_keeps_currency_explicit():
    start = date(2026, 7, 1)
    rows = [
        metric_row(start + timedelta(days=index), 1, net_revenue=1000)
        for index in range(28)
    ]
    service = service_with_rows(rows)

    result = await service.forecast(
        venue_id=7,
        metric=ForecastMetric.NET_REVENUE,
        currency="eur",
        as_of_date=start + timedelta(days=27),
        horizon_days=1,
        history_days=28,
        current_user=owner(),
    )

    assert result.currency == "EUR"
    assert result.forecasts[0].predicted == 1000


@pytest.mark.asyncio
async def test_recent_outlier_is_reported_as_anomaly():
    start = date(2026, 6, 1)
    values = [10 + index % 2 for index in range(42)]
    values[-1] = 100
    service = service_with_rows(
        [
            metric_row(start + timedelta(days=index), value)
            for index, value in enumerate(values)
        ]
    )

    result = await service.forecast(
        venue_id=7,
        metric=ForecastMetric.RESERVATIONS,
        as_of_date=start + timedelta(days=41),
        horizon_days=1,
        history_days=42,
        current_user=owner(),
    )

    assert result.anomalies[-1].date == start + timedelta(days=41)
    assert result.anomalies[-1].direction == "above_expected"
    assert result.anomalies[-1].z_score >= 2


@pytest.mark.parametrize(
    ("metric", "horizon", "history", "currency", "detail"),
    [
        (ForecastMetric.RESERVATIONS, 31, 84, None, "horizon_days"),
        (ForecastMetric.RESERVATIONS, 7, 13, None, "history_days"),
        (ForecastMetric.NET_REVENUE, 7, 84, None, "currency is required"),
        (ForecastMetric.NET_REVENUE, 7, 84, "EU", "3-letter"),
    ],
)
def test_forecast_request_validation(metric, horizon, history, currency, detail):
    with pytest.raises(HTTPException, match=detail):
        DemandForecastService._validate_request(metric, horizon, history, currency)


@pytest.mark.asyncio
async def test_owner_cannot_forecast_another_venue():
    service = service_with_rows([])
    service.venue_repository.get_by_id = AsyncMock(
        return_value=SimpleNamespace(id=7, owner_id=99)
    )

    with pytest.raises(HTTPException) as exc_info:
        await service.forecast(
            venue_id=7,
            metric=ForecastMetric.RESERVATIONS,
            as_of_date=date(2026, 8, 28),
            horizon_days=7,
            history_days=84,
            current_user=owner(),
        )

    assert exc_info.value.status_code == 403
