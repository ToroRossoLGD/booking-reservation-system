from datetime import datetime

from pydantic import BaseModel, Field, field_validator


class PromotionCreate(BaseModel):
    code: str = Field(min_length=3, max_length=50, pattern=r"^[A-Za-z0-9_-]+$")
    discount_percent: int = Field(ge=1, le=100)
    valid_from: datetime
    valid_until: datetime
    max_redemptions: int | None = Field(default=None, ge=1)

    @field_validator("code")
    @classmethod
    def normalize_code(cls, value: str) -> str:
        return value.upper()


class PromotionRead(BaseModel):
    id: int
    code: str
    venue_id: int
    discount_percent: int
    valid_from: datetime
    valid_until: datetime
    max_redemptions: int | None
    redemption_count: int
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}
