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

from app.schemas.property_photo import PropertyPhotoRead

OfferType = Literal["short_stay", "long_term", "sale"]


class PropertySearch(BaseModel):
    city: str = Field(default="", max_length=100)
    offer_type: OfferType | None = None
    currency: Literal["EUR", "RSD", "USD"] | None = None
    min_price_cents: int | None = Field(default=None, ge=0, le=1000000000000)
    max_price_cents: int | None = Field(default=None, ge=0, le=1000000000000)
    min_area_sqm: int | None = Field(default=None, ge=1, le=100000)
    max_area_sqm: int | None = Field(default=None, ge=1, le=100000)
    rooms: int | None = Field(default=None, ge=0, le=100)
    sort: Literal["newest", "price_asc", "price_desc", "area_desc"] = "newest"
    limit: int = Field(default=20, ge=1, le=100)
    offset: int = Field(default=0, ge=0)

    @model_validator(mode="after")
    def valid_ranges(self):
        for lower, upper in (
            (self.min_price_cents, self.max_price_cents),
            (self.min_area_sqm, self.max_area_sqm),
        ):
            if lower is not None and upper is not None and lower > upper:
                raise ValueError("Minimum must not exceed maximum")
        if (
            self.min_price_cents is not None
            or self.max_price_cents is not None
            or self.sort.startswith("price_")
        ) and (self.offer_type is None or self.currency is None):
            raise ValueError(
                "Price filters and sorting require offer_type and currency"
            )
        return self


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
    photos: list[PropertyPhotoRead] = Field(default_factory=list)


class PropertyListingPage(BaseModel):
    items: list[PropertyListingRead]
    total: int
    limit: int
    offset: int
    has_next: bool
