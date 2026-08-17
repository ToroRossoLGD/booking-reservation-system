from pydantic import BaseModel, Field


class VenueCreate(BaseModel):
    name: str = Field(min_length=2, max_length=255)
    description: str | None = None
    address: str = Field(min_length=2, max_length=255)
    free_cancellation_hours: int = Field(default=24, ge=0, le=720)
    late_cancellation_refund_percent: int = Field(default=50, ge=0, le=100)


class VenueCancellationPolicyUpdate(BaseModel):
    free_cancellation_hours: int = Field(ge=0, le=720)
    late_cancellation_refund_percent: int = Field(ge=0, le=100)


class VenueCancellationPolicyRead(BaseModel):
    venue_id: int
    free_cancellation_hours: int
    late_cancellation_refund_percent: int


class VenueRead(BaseModel):
    id: int
    name: str
    description: str | None
    address: str
    owner_id: int
    free_cancellation_hours: int
    late_cancellation_refund_percent: int

    model_config = {"from_attributes": True}


class VenueListRead(BaseModel):
    items: list[VenueRead]
    total: int
    limit: int
    offset: int
    has_next: bool
