from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.schemas.stay import StayDates, StayQuote, StayRead


class StayDateChangeCreate(StayDates):
    request_id: UUID
    quote: StayQuote


class StayDateChangeDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")
    action: Literal["accept", "decline", "withdraw"]


class StayDateChangeRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    stay_id: int
    check_in: date
    check_out: date
    original: StayRead
    quote: StayQuote
    status: Literal["pending", "accepted", "declined", "withdrawn", "expired"]
    created_at: datetime
    resolved_at: datetime | None


class StayDateChangePage(BaseModel):
    items: list[StayDateChangeRead]
    total: int
    has_next: bool
