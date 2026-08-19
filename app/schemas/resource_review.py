from datetime import datetime
from typing import Literal

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
    owner_response: str | None = None
    owner_responded_at: datetime | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class ResourceRatingSummaryRead(BaseModel):
    resource_id: int
    average_rating: float
    review_count: int


class OwnerResponseUpdate(BaseModel):
    response: str = Field(min_length=1, max_length=2_000)


class ReviewReportCreate(BaseModel):
    reason: Literal["spam", "harassment", "inappropriate", "false_information", "other"]
    details: str | None = Field(default=None, max_length=2_000)


class ReviewReportRead(BaseModel):
    id: int
    review_id: int
    reporter_id: int
    reason: str
    details: str | None
    status: str
    reviewed_by: int | None
    resolution_note: str | None
    created_at: datetime
    reviewed_at: datetime | None

    model_config = {"from_attributes": True}


class ReviewReportListRead(BaseModel):
    items: list[ReviewReportRead]
    total: int
    limit: int
    offset: int
    has_next: bool


class ReviewReportDecision(BaseModel):
    decision: Literal["dismiss", "hide_review"]
    resolution_note: str = Field(min_length=1, max_length=2_000)


class ReviewModerationUpdate(BaseModel):
    status: Literal["visible", "hidden"]
    reason: str = Field(min_length=1, max_length=2_000)
