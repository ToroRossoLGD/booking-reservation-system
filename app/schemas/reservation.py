from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from app.schemas.add_on import AddOnSelection, ReservationAddOnRead
from app.schemas.payment import PaymentRead
from app.schemas.reservation_event import ReservationEventRead


class ReservationCreate(BaseModel):
    resource_id: int
    start_time: datetime
    end_time: datetime
    promotion_code: str | None = Field(default=None, min_length=3, max_length=50)
    party_size: int = Field(default=1, ge=1, le=10_000)
    add_ons: list[AddOnSelection] = Field(default_factory=list, max_length=50)

    @model_validator(mode="after")
    def validate_unique_add_ons(self):
        ids = [item.add_on_id for item in self.add_ons]
        if len(ids) != len(set(ids)):
            raise ValueError("Each add-on may be selected only once")
        return self


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
    hold_expires_at: datetime | None = None
    user_id: int
    resource_id: int
    party_size: int
    recurrence_series_id: str | None = None
    quoted_amount_cents: int
    quoted_currency: str
    base_amount_cents: int
    discount_amount_cents: int
    add_on_total_cents: int = 0
    add_ons: list[ReservationAddOnRead] = Field(default_factory=list)
    promotion_code: str | None = None
    promotion_discount_percent: int | None = None
    attendance_status: str
    checked_in_at: datetime | None = None
    no_show_marked_at: datetime | None = None
    cancellation_free_hours: int
    cancellation_late_refund_percent: int

    model_config = {"from_attributes": True}


class RecurringReservationRead(BaseModel):
    recurrence_series_id: str
    occurrence_count: int
    reservations: list[ReservationRead]


class RecurringSeriesCancellationRequest(BaseModel):
    cancel_from: datetime | None = None

    @model_validator(mode="after")
    def validate_cancel_from_timezone(self):
        if self.cancel_from is not None and self.cancel_from.tzinfo is None:
            raise ValueError("cancel_from must include timezone information")
        return self


class RecurringSeriesCancellationRead(BaseModel):
    recurrence_series_id: str
    occurrence_count: int
    cancelled_count: int
    skipped_count: int
    total_refund_amount_cents: int
    total_cancellation_fee_cents: int
    cancelled_reservations: list[ReservationRead]


class AvailabilityRead(BaseModel):
    resource_id: int
    start_time: datetime
    end_time: datetime
    available: bool
    requested_capacity: int
    remaining_capacity: int


class AvailableSlotRead(BaseModel):
    start_time: datetime
    end_time: datetime
    available: bool
    remaining_capacity: int


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
    applied_free_cancellation_hours: int
    applied_late_refund_percent: int


class ReservationCancellationPreviewRead(BaseModel):
    refund_percentage: int
    refund_amount_cents: int
    cancellation_fee_cents: int
    applied_free_cancellation_hours: int
    applied_late_refund_percent: int


class ReservationResourceSummaryRead(BaseModel):
    id: int
    name: str
    resource_type: str
    capacity: int

    model_config = {"from_attributes": True}


class ReservationVenueSummaryRead(BaseModel):
    id: int
    name: str
    address: str

    model_config = {"from_attributes": True}


class ReservationWorkspaceRead(BaseModel):
    reservation: ReservationRead
    resource: ReservationResourceSummaryRead
    venue: ReservationVenueSummaryRead
    payment: PaymentRead | None
    timeline: list[ReservationEventRead]
    allowed_actions: list[str]
    cancellation_preview: ReservationCancellationPreviewRead | None


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
    add_on_total_cents: int = 0
    add_ons: list[ReservationAddOnRead] = Field(default_factory=list)
    promotion_code: str | None = None
    promotion_discount_percent: int | None = None


class CheckInPassRead(BaseModel):
    reservation_id: int
    token: str
    valid_from: datetime
    expires_at: datetime


class CheckInRequest(BaseModel):
    token: str = Field(min_length=20)


class ReminderDispatchRead(BaseModel):
    candidate_count: int
    sent_count: int
    duplicate_count: int
