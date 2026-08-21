from datetime import datetime

from pydantic import BaseModel, Field


class CalendarFeedCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    resource_id: int | None = Field(default=None, gt=0)
    include_pending: bool = False
    model_config = {"str_strip_whitespace": True}


class CalendarFeedRead(BaseModel):
    id: int
    venue_id: int
    resource_id: int | None
    name: str
    token_prefix: str
    include_pending: bool
    created_by_id: int | None
    created_at: datetime
    last_accessed_at: datetime | None
    revoked_at: datetime | None
    model_config = {"from_attributes": True}


class CalendarFeedCreated(CalendarFeedRead):
    feed_token: str
    feed_path: str
