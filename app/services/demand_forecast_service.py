from datetime import date, timedelta
from math import sqrt
from statistics import fmean, stdev

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.repositories.analytics_pipeline_repository import AnalyticsPipelineRepository
from app.repositories.venue_repository import VenueRepository
from app.schemas.demand_forecast import (
    DemandAnomaly,
    ForecastAccuracy,
    ForecastMetric,
    ForecastPoint,
    VenueDemandForecastRead,
)


class DemandForecastService:
    MODEL_NAME = "weekday-seasonal-trend-v1"
    MIN_HISTORY_DAYS = 14
    MAX_HISTORY_DAYS = 365
    MAX_HORIZON_DAYS = 30
    TREND_WINDOW_DAYS = 14
    ANOMALY_Z_THRESHOLD = 2.0

    def __init__(self, db: AsyncSession):
        self.repository = AnalyticsPipelineRepository(db)
        self.venue_repository = VenueRepository(db)

    async def forecast(
        self,
        venue_id: int,
        metric: ForecastMetric,
        as_of_date: date,
        horizon_days: int,
        history_days: int,
        current_user: User,
        currency: str | None = None,
    ) -> VenueDemandForecastRead:
        self._validate_request(metric, horizon_days, history_days, currency)
        await self._authorize(venue_id, current_user)
        start_date = as_of_date - timedelta(days=history_days - 1)
        rows = await self.repository.get_venue_metric_history(
            venue_id, start_date, as_of_date
        )
        series = self._continuous_series(rows, start_date, as_of_date, metric, currency)
        values = [value for _, value in series]
        forecasts, error_scale = self._future_forecasts(
            values, as_of_date, horizon_days
        )
        accuracy, anomalies = self._backtest(series)
        if error_scale == 0 and accuracy.mean_absolute_error is not None:
            error_scale = accuracy.mean_absolute_error
            forecasts = self._apply_intervals(forecasts, error_scale)
        return VenueDemandForecastRead(
            venue_id=venue_id,
            metric=metric,
            currency=currency.upper() if currency else None,
            as_of_date=as_of_date,
            history_days=history_days,
            model=self.MODEL_NAME,
            forecasts=forecasts,
            accuracy=accuracy,
            anomalies=anomalies,
        )

    async def _authorize(self, venue_id: int, current_user: User) -> None:
        venue = await self.venue_repository.get_by_id(venue_id)
        if venue is None:
            raise HTTPException(status_code=404, detail="Venue not found")
        if current_user.role != "admin" and venue.owner_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can view forecasts only for your own venues",
            )

    @classmethod
    def _validate_request(
        cls,
        metric: ForecastMetric,
        horizon_days: int,
        history_days: int,
        currency: str | None,
    ) -> None:
        if not 1 <= horizon_days <= cls.MAX_HORIZON_DAYS:
            raise HTTPException(
                status_code=400,
                detail=f"horizon_days must be between 1 and {cls.MAX_HORIZON_DAYS}",
            )
        if not cls.MIN_HISTORY_DAYS <= history_days <= cls.MAX_HISTORY_DAYS:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"history_days must be between {cls.MIN_HISTORY_DAYS} "
                    f"and {cls.MAX_HISTORY_DAYS}"
                ),
            )
        if metric == ForecastMetric.NET_REVENUE and not currency:
            raise HTTPException(
                status_code=400,
                detail="currency is required when metric is net_revenue",
            )
        if currency and (len(currency) != 3 or not currency.isalpha()):
            raise HTTPException(
                status_code=400, detail="currency must be a 3-letter code"
            )

    @classmethod
    def _continuous_series(
        cls, rows, start_date: date, end_date: date, metric, currency
    ) -> list[tuple[date, float]]:
        by_date = {row.metric_date: row for row in rows}
        series = []
        current = start_date
        while current <= end_date:
            row = by_date.get(current)
            series.append((current, cls._value(row, metric, currency)))
            current += timedelta(days=1)
        return series

    @staticmethod
    def _value(row, metric: ForecastMetric, currency: str | None) -> float:
        if row is None:
            return 0.0
        fields = {
            ForecastMetric.RESERVATIONS: "reservation_count",
            ForecastMetric.BOOKED_MINUTES: "booked_minutes",
            ForecastMetric.CANCELLATIONS: "cancelled_count",
            ForecastMetric.NO_SHOWS: "no_show_count",
        }
        if metric in fields:
            return float(getattr(row, fields[metric]))
        revenue = row.revenue_by_currency.get(currency.upper(), {})
        return float(revenue.get("net", 0))

    @classmethod
    def _predict(cls, history: list[float], target_index: int) -> float:
        weekday_values = [
            history[index] for index in range(target_index % 7, len(history), 7)
        ]
        baseline = fmean(weekday_values[-8:]) if weekday_values else fmean(history)
        if len(history) < cls.TREND_WINDOW_DAYS * 2:
            return max(0.0, baseline)
        recent = fmean(history[-cls.TREND_WINDOW_DAYS :])
        previous = fmean(history[-cls.TREND_WINDOW_DAYS * 2 : -cls.TREND_WINDOW_DAYS])
        trend = recent / previous if previous > 0 else 1.0
        trend = min(1.5, max(0.5, trend))
        return max(0.0, baseline * trend)

    @classmethod
    def _future_forecasts(cls, history, as_of_date, horizon_days):
        working = list(history)
        raw_points = []
        for offset in range(1, horizon_days + 1):
            predicted = cls._predict(working, len(working))
            raw_points.append((as_of_date + timedelta(days=offset), predicted))
            working.append(predicted)
        errors = cls._walk_forward_errors(history)
        error_scale = fmean(abs(item) for item in errors) if errors else 0.0
        points = [
            ForecastPoint(
                date=point_date,
                predicted=round(predicted, 2),
                lower_bound=round(max(0.0, predicted - 1.96 * error_scale), 2),
                upper_bound=round(predicted + 1.96 * error_scale, 2),
            )
            for point_date, predicted in raw_points
        ]
        return points, error_scale

    @staticmethod
    def _apply_intervals(points, error_scale):
        return [
            point.model_copy(
                update={
                    "lower_bound": round(
                        max(0.0, point.predicted - 1.96 * error_scale), 2
                    ),
                    "upper_bound": round(point.predicted + 1.96 * error_scale, 2),
                }
            )
            for point in points
        ]

    @classmethod
    def _walk_forward_errors(cls, values: list[float]):
        return [
            values[index] - cls._predict(values[:index], index)
            for index in range(cls.MIN_HISTORY_DAYS, len(values))
        ]

    @classmethod
    def _backtest(cls, series):
        values = [value for _, value in series]
        errors = cls._walk_forward_errors(values)
        if not errors:
            return ForecastAccuracy(
                backtest_points=0,
                mean_absolute_error=None,
                mean_absolute_percentage_error=None,
            ), []
        absolute_errors = [abs(error) for error in errors]
        percentage_errors = [
            abs(error) / values[index] * 100
            for index, error in enumerate(errors, start=cls.MIN_HISTORY_DAYS)
            if values[index] > 0
        ]
        accuracy = ForecastAccuracy(
            backtest_points=len(errors),
            mean_absolute_error=round(fmean(absolute_errors), 2),
            mean_absolute_percentage_error=(
                round(fmean(percentage_errors), 2) if percentage_errors else None
            ),
        )
        anomalies = cls._detect_anomalies(series, errors)
        return accuracy, anomalies

    @classmethod
    def _detect_anomalies(cls, series, errors):
        if len(errors) < 8:
            return []
        baseline_errors = errors[:-7]
        if len(baseline_errors) < 2:
            return []
        center = fmean(baseline_errors)
        deviation = stdev(baseline_errors)
        if deviation == 0:
            deviation = sqrt(fmean(error * error for error in baseline_errors))
        if deviation == 0:
            return []
        anomalies = []
        recent_start = len(series) - min(7, len(errors))
        values = [value for _, value in series]
        for index in range(recent_start, len(series)):
            expected = cls._predict(values[:index], index)
            residual = values[index] - expected
            z_score = (residual - center) / deviation
            if abs(z_score) >= cls.ANOMALY_Z_THRESHOLD:
                anomalies.append(
                    DemandAnomaly(
                        date=series[index][0],
                        actual=round(values[index], 2),
                        expected=round(expected, 2),
                        residual=round(residual, 2),
                        z_score=round(z_score, 2),
                        direction="above_expected"
                        if residual > 0
                        else "below_expected",
                    )
                )
        return anomalies
