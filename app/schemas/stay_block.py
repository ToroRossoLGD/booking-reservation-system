from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


class StayBlockCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    check_in: date
    check_out: date
    reason: str = Field(default="", max_length=300)
    request_id: UUID

    @model_validator(mode="after")
    def duration(self):
        if not 1 <= (self.check_out - self.check_in).days <= 365:
            raise ValueError("Block must cover 1 to 365 nights")
        return self


class StayBlockRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    venue_id: int
    check_in: date
    check_out: date
    reason: str
    active: bool
    created_at: datetime


class StayBlockPage(BaseModel):
    items: list[StayBlockRead]
    total: int
    has_next: bool
