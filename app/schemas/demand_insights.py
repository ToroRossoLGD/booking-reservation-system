from datetime import date

from pydantic import BaseModel


class MetricComparison(BaseModel):
    current: float
    previous: float
    absolute_change: float
    relative_change_percent: float | None


class DemandBucket(BaseModel):
    label: str
    reservation_count: int
    percentage: float


class WeekdayDemand(BaseModel):
    weekday: int
    weekday_name: str
    reservation_count: int
    party_size_total: int


class HourlyDemand(BaseModel):
    hour_utc: int
    reservation_count: int
    party_size_total: int


class DemandPeriodSummary(BaseModel):
    start_date: date
    end_date: date
    total_reservations: int
    booked_minutes: int
    unique_customers: int
    repeat_customers: int
    repeat_customer_rate_percent: float
    cancellation_rate_percent: float
    no_show_rate_percent: float
    average_booking_lead_hours: float
    average_duration_minutes: float
    average_party_size: float
    peak_weekday: str | None
    peak_hour_utc: int | None
    net_revenue_by_currency: dict[str, int]
    lead_time_distribution: list[DemandBucket]
    demand_by_weekday: list[WeekdayDemand]
    demand_by_hour: list[HourlyDemand]


class DemandComparison(BaseModel):
    total_reservations: MetricComparison
    booked_minutes: MetricComparison
    unique_customers: MetricComparison
    repeat_customer_rate_percent: MetricComparison
    cancellation_rate_percent: MetricComparison
    no_show_rate_percent: MetricComparison
    average_booking_lead_hours: MetricComparison
    average_duration_minutes: MetricComparison
    average_party_size: MetricComparison
    net_revenue_by_currency: dict[str, MetricComparison]


class VenueDemandInsightsRead(BaseModel):
    venue_id: int
    venue_name: str
    current_period: DemandPeriodSummary
    previous_period: DemandPeriodSummary
    comparison: DemandComparison
