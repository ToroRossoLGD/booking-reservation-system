from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field

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


class PropertyListingRead(PropertyListingWrite):
    model_config = ConfigDict(from_attributes=True)
    id: int


class PropertyListingPage(BaseModel):
    items: list[PropertyListingRead]
    total: int
    limit: int
    offset: int
    has_next: bool
