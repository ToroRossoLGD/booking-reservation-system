from datetime import date
from enum import Enum

from pydantic import BaseModel


class ForecastMetric(str, Enum):
    RESERVATIONS = "reservations"
    BOOKED_MINUTES = "booked_minutes"
    CANCELLATIONS = "cancellations"
    NO_SHOWS = "no_shows"
    NET_REVENUE = "net_revenue"


class ForecastPoint(BaseModel):
    date: date
    predicted: float
    lower_bound: float
    upper_bound: float


class ForecastAccuracy(BaseModel):
    backtest_points: int
    mean_absolute_error: float | None
    mean_absolute_percentage_error: float | None


class DemandAnomaly(BaseModel):
    date: date
    actual: float
    expected: float
    residual: float
    z_score: float
    direction: str


class VenueDemandForecastRead(BaseModel):
    venue_id: int
    metric: ForecastMetric
    currency: str | None
    as_of_date: date
    history_days: int
    model: str
    forecasts: list[ForecastPoint]
    accuracy: ForecastAccuracy
    anomalies: list[DemandAnomaly]
