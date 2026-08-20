from datetime import datetime
from typing import Literal

from pydantic import BaseModel, EmailStr, Field


class GuestInvitationCreate(BaseModel):
    email: EmailStr
    guest_name: str = Field(min_length=1, max_length=100)

    model_config = {"str_strip_whitespace": True}


class GuestInvitationResponse(BaseModel):
    token: str = Field(min_length=32, max_length=255)
    response: Literal["accepted", "declined"]


class GuestInvitationRead(BaseModel):
    id: int
    reservation_id: int
    email: EmailStr
    guest_name: str
    status: str
    invited_at: datetime
    expires_at: datetime
    responded_at: datetime | None

    model_config = {"from_attributes": True}
