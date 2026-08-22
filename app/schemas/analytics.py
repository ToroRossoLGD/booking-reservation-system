from datetime import date

from pydantic import BaseModel


class RevenueAnalytics(BaseModel):
    gross_revenue_cents: int
    refunded_amount_cents: int
    net_revenue_cents: int


class ResourceAnalytics(BaseModel):
    resource_id: int
    resource_name: str
    reservation_count: int
    booked_minutes: int
    booked_capacity_minutes: int
    reservations_by_status: dict[str, int]
    revenue_by_currency: dict[str, RevenueAnalytics]


class DailyAnalytics(BaseModel):
    date: date
    reservation_count: int
    booked_minutes: int
    booked_capacity_minutes: int
    cancelled_count: int
    no_show_count: int
    revenue_by_currency: dict[str, RevenueAnalytics]


class VenueAnalyticsRead(BaseModel):
    venue_id: int
    venue_name: str
    start_date: date
    end_date: date
    total_reservations: int
    reservations_by_status: dict[str, int]
    booked_minutes: int
    booked_capacity_minutes: int
    cancellation_rate_percent: float
    no_show_rate_percent: float
    revenue_by_currency: dict[str, RevenueAnalytics]
    daily: list[DailyAnalytics]
    resources: list[ResourceAnalytics]
