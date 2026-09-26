from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.stay_times import StayTime


class StayDates(BaseModel):
    model_config = ConfigDict(extra="forbid")
    check_in: date
    check_out: date
    guests: int = Field(ge=1, le=100)

    @model_validator(mode="after")
    def valid_duration(self):
        if not 1 <= (self.check_out - self.check_in).days <= 90:
            raise ValueError("Choose a stay of 1 to 90 nights")
        return self


class StayCreate(StayDates):
    expected_check_in_time: StayTime | None = None
    expected_check_out_time: StayTime | None = None
    expected_timezone: str | None = Field(default=None, max_length=64)
    request_id: UUID
    expected_total_cents: int = Field(gt=0, le=90000000000000)
    expected_currency: Literal["EUR", "RSD", "USD"]


class StayQuote(BaseModel):
    check_in_time: StayTime | None = None
    check_out_time: StayTime | None = None
    nights: int
    nightly_rate_cents: int
    total_cents: int
    currency: str
    timezone: str
    payment_method: Literal["pay_on_arrival"] = "pay_on_arrival"


class StayRead(BaseModel):
    check_in_time: StayTime | None = None
    check_out_time: StayTime | None = None
    model_config = ConfigDict(from_attributes=True)
    id: int
    property_id: int
    check_in: date
    check_out: date
    guests: int
    status: str
    title: str
    city: str
    timezone: str
    contact_email: str
    nightly_rate_cents: int
    total_cents: int
    currency: str
    created_at: datetime
    guest_email: str | None = None
    payment_method: Literal["pay_on_arrival"] = "pay_on_arrival"


class StayPage(BaseModel):
    items: list[StayRead]
    total: int
    has_next: bool


class OccupiedDates(BaseModel):
    check_in: date
    check_out: date
    model_config = ConfigDict(from_attributes=True)


class StayCalendar(BaseModel):
    start: date
    end: date
    occupied: list[OccupiedDates]
