from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.payment import PaymentRead


class ReservationCreate(BaseModel):
    resource_id: int
    start_time: datetime
    end_time: datetime


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
