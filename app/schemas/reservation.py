from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.payment import PaymentRead


class ReservationCreate(BaseModel):
    resource_id: int
    start_time: datetime
    end_time: datetime
    promotion_code: str | None = Field(default=None, min_length=3, max_length=50)


class ReservationReschedule(BaseModel):
    start_time: datetime
    end_time: datetime


class RecurringReservationCreate(ReservationCreate):
    frequency: Literal["daily", "weekly"]
    occurrence_count: int = Field(ge=2, le=52)


class ReservationRead(BaseModel):
    id: int
    start_time: datetime
    end_time: datetime
    status: str
    user_id: int
    resource_id: int
    recurrence_series_id: str | None = None
    quoted_amount_cents: int
    quoted_currency: str
    base_amount_cents: int
    discount_amount_cents: int
    promotion_code: str | None = None
    promotion_discount_percent: int | None = None

    model_config = {"from_attributes": True}


class RecurringReservationRead(BaseModel):
    recurrence_series_id: str
    occurrence_count: int
    reservations: list[ReservationRead]


class AvailabilityRead(BaseModel):
    resource_id: int
    start_time: datetime
    end_time: datetime
    available: bool


class AvailableSlotRead(BaseModel):
    start_time: datetime
    end_time: datetime
    available: bool


class ReservationListRead(BaseModel):
    items: list[ReservationRead]
    total: int
    limit: int
    offset: int
    has_next: bool


class ReservationCancellationRead(BaseModel):
    reservation: ReservationRead
    payment: PaymentRead | None
    refund_percentage: int
    refund_amount_cents: int
    cancellation_fee_cents: int


class ReservationQuoteRead(BaseModel):
    resource_id: int
    start_time: datetime
    end_time: datetime
    duration_minutes: int
    hourly_rate_cents: int
    amount_cents: int
    currency: str
    base_amount_cents: int
    discount_amount_cents: int
    promotion_code: str | None = None
    promotion_discount_percent: int | None = None
