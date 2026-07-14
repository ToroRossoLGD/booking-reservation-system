from datetime import datetime

from pydantic import BaseModel, Field


class PaymentCreate(BaseModel):
    amount_cents: int = Field(gt=0)
    currency: str = Field(default="EUR", min_length=3, max_length=10)


class PaymentRead(BaseModel):
    id: int
    reservation_id: int
    amount_cents: int
    currency: str
    status: str
    provider: str
    created_at: datetime
    refunded_amount_cents: int
    cancellation_fee_cents: int
    refunded_at: datetime | None

    model_config = {"from_attributes": True}
