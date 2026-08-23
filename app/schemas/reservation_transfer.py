from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


class ReservationTransferCreate(BaseModel):
    recipient_email: EmailStr
    message: str | None = Field(default=None, max_length=1000)
    model_config = {"str_strip_whitespace": True}


class ReservationTransferToken(BaseModel):
    token: str = Field(min_length=32, max_length=255)


class ReservationTransferRead(BaseModel):
    id: int
    reservation_id: int
    previous_owner_id: int
    recipient_user_id: int | None
    recipient_email: EmailStr
    status: str
    message: str | None
    created_at: datetime
    expires_at: datetime
    responded_at: datetime | None
    model_config = {"from_attributes": True}


class ReservationTransferAcceptRead(BaseModel):
    transfer: ReservationTransferRead
    reservation_id: int
    previous_owner_id: int
    new_owner_id: int
