from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator


class RentalInquiryCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    request_id: UUID
    move_in: date
    duration_months: int = Field(ge=1, le=120)
    message: str = Field(min_length=10, max_length=3000)


class RentalInquiryUpdate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    version: int = Field(ge=1)
    action: Literal["reply", "propose", "confirm", "decline", "close", "withdraw"]
    owner_reply: str = Field(default="", max_length=3000)
    viewing_at: AwareDatetime | None = None

    @model_validator(mode="after")
    def validate_action(self):
        if self.action in {"reply", "propose"} and not self.owner_reply:
            raise ValueError("A reply is required")
        if (self.action == "propose") != (self.viewing_at is not None):
            raise ValueError("A viewing time is required only when proposing a viewing")
        if self.action not in {"reply", "propose"} and self.owner_reply:
            raise ValueError("This action does not accept a reply")
        return self


class RentalInquiryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    property_id: int
    title: str
    monthly_price_cents: int
    currency: str
    move_in: date
    duration_months: int
    message: str
    owner_reply: str
    viewing_at: datetime | None
    status: Literal[
        "open", "viewing_proposed", "viewing_confirmed", "closed", "withdrawn"
    ]
    version: int
    created_at: datetime
    unread_count: int = 0


class RentalInquiryPage(BaseModel):
    items: list[RentalInquiryRead]
    total: int
    has_next: bool
