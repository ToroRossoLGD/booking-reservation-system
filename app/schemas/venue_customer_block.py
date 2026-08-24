from datetime import datetime

from pydantic import BaseModel, EmailStr, Field, model_validator


class VenueCustomerBlockCreate(BaseModel):
    customer_email: EmailStr
    reason: str = Field(min_length=3, max_length=1000)
    blocked_until: datetime | None = None

    @model_validator(mode="after")
    def validate_timezone(self):
        if self.blocked_until is not None and self.blocked_until.tzinfo is None:
            raise ValueError("blocked_until must include timezone information")
        return self


class VenueCustomerBlockRead(BaseModel):
    id: int
    venue_id: int
    customer_id: int
    customer_email: EmailStr
    reason: str
    blocked_at: datetime
    blocked_until: datetime | None
    blocked_by_id: int
    unblocked_at: datetime | None
    unblocked_by_id: int | None
    is_active: bool


class MyVenueBlockRead(BaseModel):
    id: int
    venue_id: int
    venue_name: str
    reason: str
    blocked_at: datetime
    blocked_until: datetime | None
