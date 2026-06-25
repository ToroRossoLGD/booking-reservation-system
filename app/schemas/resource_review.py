from datetime import datetime

from pydantic import BaseModel, Field


class ResourceReviewCreate(BaseModel):
    rating: int = Field(ge=1, le=5)
    comment: str | None = None


class ResourceReviewRead(BaseModel):
    id: int
    user_id: int
    resource_id: int
    rating: int
    comment: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class ResourceRatingSummaryRead(BaseModel):
    resource_id: int
    average_rating: float
    review_count: int
