from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class PropertyReviewCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    rating: int = Field(ge=1, le=5, strict=True)
    comment: str = Field(min_length=10, max_length=2000)


class PropertyReviewRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    rating: int
    comment: str
    created_at: datetime


class PropertyReviewPage(BaseModel):
    items: list[PropertyReviewRead]
    total: int
    average_rating: float | None
    has_next: bool
