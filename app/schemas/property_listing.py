from datetime import date
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

from app.schemas.property_details import PropertyDetails
from app.schemas.property_photo import PropertyPhotoRead
from app.schemas.rental_terms import RentalTerms
from app.schemas.seasonal_rate import SeasonalRate
from app.schemas.stay_times import StayTime

OfferType = Literal["short_stay", "long_term", "sale"]


class PropertySearch(PropertyDetails):
    city: str = Field(default="", max_length=100)
    offer_type: OfferType | None = None
    currency: Literal["EUR", "RSD", "USD"] | None = None
    min_price_cents: int | None = Field(default=None, ge=0, le=1000000000000)
    max_price_cents: int | None = Field(default=None, ge=0, le=1000000000000)
    min_area_sqm: int | None = Field(default=None, ge=1, le=100000)
    max_area_sqm: int | None = Field(default=None, ge=1, le=100000)
    rooms: int | None = Field(default=None, ge=0, le=100)
    check_in: date | None = None
    check_out: date | None = None
    guests: int | None = Field(default=None, ge=1, le=100)
    sort: Literal["newest", "price_asc", "price_desc", "area_desc"] = "newest"
    limit: int = Field(default=20, ge=1, le=100)
    offset: int = Field(default=0, ge=0)

    @model_validator(mode="after")
    def valid_ranges(self):
        if any(
            value is not None for value in (self.check_in, self.check_out, self.guests)
        ):
            if self.offer_type != "short_stay" or any(
                value is None for value in (self.check_in, self.check_out, self.guests)
            ):
                raise ValueError(
                    "Availability search requires short_stay, "
                    "check_in, check_out and guests"
                )
            if not 1 <= (self.check_out - self.check_in).days <= 90:
                raise ValueError("Choose a stay of 1 to 90 nights")
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


class PropertyListingWrite(PropertyDetails, RentalTerms):
    seasonal_rates: list[SeasonalRate] = Field(default_factory=list, max_length=24)
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
    maximum_nights: int = Field(default=90, ge=1, le=90)
    advance_notice_days: int = Field(default=1, ge=1, le=90)
    booking_window_days: int = Field(default=365, ge=2, le=365)
    timezone: str = Field(default="Europe/Belgrade", max_length=64)
    check_in_time: StayTime | None = None
    check_out_time: StayTime | None = None

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
        if self.seasonal_rates and self.offer_type != "short_stay":
            raise ValueError("Seasonal rates apply only to nightly stays")
        ordered = sorted(self.seasonal_rates, key=lambda rate: rate.start)
        if any(first.end > second.start for first, second in zip(ordered, ordered[1:])):
            raise ValueError("Seasonal rate periods must not overlap")
        self.seasonal_rates = ordered
        if self.advance_notice_days + self.minimum_nights > self.booking_window_days:
            raise ValueError(
                "Booking window must allow advance notice and minimum stay"
            )
        if self.offer_type != "short_stay" and (
            self.advance_notice_days != 1 or self.booking_window_days != 365
        ):
            raise ValueError("Booking windows apply only to nightly stays")
        if self.maximum_nights < self.minimum_nights:
            raise ValueError("Maximum nights must not be below minimum nights")
        if self.offer_type != "long_term" and any(
            getattr(self, field) is not None for field in RentalTerms.model_fields
        ):
            raise ValueError("Rental terms apply only to long-term rentals")
        if (self.check_in_time is None) != (self.check_out_time is None):
            raise ValueError("Provide both arrival and departure times, or neither")
        if self.offer_type != "short_stay" and self.check_in_time is not None:
            raise ValueError("Arrival and departure times apply only to short stays")
        if self.booking_enabled and self.offer_type != "short_stay":
            raise ValueError("Online reservations are only available for short stays")
        return self


class PropertyListingRead(PropertyListingWrite):
    stay_total_cents: int | None = None
    model_config = ConfigDict(from_attributes=True)
    id: int
    photos: list[PropertyPhotoRead] = Field(default_factory=list)


class PropertyListingPage(BaseModel):
    items: list[PropertyListingRead]
    total: int
    limit: int
    offset: int
    has_next: bool
