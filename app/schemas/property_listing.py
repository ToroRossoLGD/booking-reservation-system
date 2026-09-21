from typing import Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    field_validator,
    model_validator,
)

OfferType = Literal["short_stay", "long_term", "sale"]


class PropertyListingWrite(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    venue_id: int = Field(gt=0)
    title: str = Field(min_length=3, max_length=160)
    description: str = Field(min_length=20, max_length=5000)
    city: str = Field(min_length=2, max_length=100)
    offer_type: OfferType
    area_sqm: int = Field(ge=1, le=100000)
    rooms: int = Field(ge=0, le=100)
    price_cents: int = Field(ge=1, le=1000000000000)
    currency: Literal["EUR", "RSD", "USD"] = "EUR"
    contact_email: EmailStr = Field(max_length=254)
    is_published: bool = False
    booking_enabled: bool = False
    max_guests: int = Field(default=2, ge=1, le=100)
    minimum_nights: int = Field(default=1, ge=1, le=30)
    timezone: str = Field(default="Europe/Belgrade", max_length=64)

    @field_validator("timezone")
    @classmethod
    def valid_timezone(cls, value):
        try:
            ZoneInfo(value)
        except (ZoneInfoNotFoundError, ValueError) as exc:
            raise ValueError("Use a valid IANA timezone") from exc
        return value

    @model_validator(mode="after")
    def booking_only_for_short_stays(self):
        if self.booking_enabled and self.offer_type != "short_stay":
            raise ValueError("Online reservations are only available for short stays")
        return self


class PropertyListingRead(PropertyListingWrite):
    model_config = ConfigDict(from_attributes=True)
    id: int


class PropertyListingPage(BaseModel):
    items: list[PropertyListingRead]
    total: int
    limit: int
    offset: int
    has_next: bool
