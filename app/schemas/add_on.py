from datetime import datetime

from pydantic import BaseModel, Field


class AddOnCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=500)
    price_cents: int = Field(ge=0, le=100_000_000)
    stock: int = Field(ge=1, le=100_000)


class AddOnUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=500)
    price_cents: int | None = Field(default=None, ge=0, le=100_000_000)
    stock: int | None = Field(default=None, ge=1, le=100_000)
    is_active: bool | None = None


class AddOnRead(BaseModel):
    id: int
    venue_id: int
    name: str
    description: str | None
    price_cents: int
    stock: int
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class AddOnSelection(BaseModel):
    add_on_id: int
    quantity: int = Field(ge=1, le=100_000)


class ReservationAddOnRead(BaseModel):
    add_on_id: int
    name: str
    unit_price_cents: int
    quantity: int

    model_config = {"from_attributes": True}
