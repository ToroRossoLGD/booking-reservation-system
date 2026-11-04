from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StrictBool


class AgreementCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    request_id: UUID
    start_date: date
    months: int = Field(ge=1, le=120, strict=True)
    monthly_cents: int = Field(ge=1, le=1_000_000_000_000, strict=True)
    deposit_cents: int = Field(default=0, ge=0, le=1_000_000_000_000, strict=True)
    notes: str = Field(default="", max_length=2000)


class AgreementAction(BaseModel):
    model_config = ConfigDict(extra="forbid")
    version: int = Field(ge=1, strict=True)
    action: Literal["accept", "decline", "withdraw"]


class ChargeUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    version: int = Field(ge=1, strict=True)
    paid: StrictBool


class AgreementRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    inquiry_id: int
    title: str
    currency: str
    timezone: str
    start_date: date
    end_date: date
    months: int
    monthly_cents: int
    deposit_cents: int
    notes: str
    status: Literal["proposed", "accepted", "declined", "withdrawn"]
    version: int
    created_at: datetime
    accepted_at: datetime | None


class ChargeRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    sequence: int
    due_date: date
    amount_cents: int
    paid: bool
    version: int
    updated_at: datetime | None


class ChargeEventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    paid: bool
    version: int
    created_at: datetime
