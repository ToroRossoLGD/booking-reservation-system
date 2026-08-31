from datetime import date, datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict


class DailyVenueMetricRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    metric_date: date
    venue_id: int
    reservation_count: int
    unique_customer_count: int
    booked_minutes: int
    booked_capacity_minutes: int
    cancelled_count: int
    no_show_count: int
    reservations_by_status: dict[str, int]
    revenue_by_currency: dict[str, dict[str, int]]
    refreshed_at: datetime


class AnalyticsPipelineRunRead(BaseModel):
    start_date: date
    end_date: date
    source_reservation_count: int
    venue_metric_count: int
    resource_metric_count: int
    quality_checks_passed: int


class AnalyticsPipelineTrigger(str, Enum):
    MANUAL = "manual"
    SCHEDULED = "scheduled"


class AnalyticsPipelineRunHistoryRead(AnalyticsPipelineRunRead):
    model_config = ConfigDict(from_attributes=True)

    id: int
    trigger: AnalyticsPipelineTrigger
    completed_at: datetime


class AnalyticsPipelineRunListRead(BaseModel):
    items: list[AnalyticsPipelineRunHistoryRead]
    total: int
    limit: int
    offset: int
    has_next: bool
