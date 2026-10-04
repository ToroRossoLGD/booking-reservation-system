from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.rental_message import RentalMessageRead


class SaleInquiryCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    request_id: UUID
    message: str = Field(min_length=10, max_length=3000)


class SaleInquiryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    property_id: int
    title: str
    asking_price_cents: int
    currency: str
    message: str
    owner_reply: str
    viewing_at: datetime | None
    status: Literal[
        "open", "viewing_proposed", "viewing_confirmed", "closed", "withdrawn"
    ]
    version: int
    created_at: datetime
    unread_count: int = 0


class SaleInquiryPage(BaseModel):
    items: list[SaleInquiryRead]
    total: int
    has_next: bool


class SaleMessageRead(RentalMessageRead):
    sender: Literal["owner", "buyer"]


class SaleMessagePage(BaseModel):
    items: list[SaleMessageRead]
    has_more: bool
    next_before_id: int | None
    unread_count: int
