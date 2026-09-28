from datetime import date
from typing import Literal

from pydantic import BaseModel, Field


class RentalTerms(BaseModel):
    deposit_cents: int | None = Field(default=None, ge=0, le=1000000000000)
    monthly_bills_cents: int | None = Field(default=None, ge=0, le=1000000000000)
    available_from: date | None = None
    minimum_rental_months: int | None = Field(default=None, ge=1, le=120)
    pets_policy: Literal["allowed", "not_allowed", "by_agreement"] | None = None
