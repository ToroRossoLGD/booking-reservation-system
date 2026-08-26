from datetime import datetime

from pydantic import BaseModel, Field


class MediaAssetRead(BaseModel):
    id: int
    venue_id: int | None
    resource_id: int | None
    original_filename: str
    content_type: str
    size_bytes: int
    caption: str | None
    sort_order: int
    created_at: datetime
    url: str


class MediaAssetUpdate(BaseModel):
    caption: str | None = Field(default=None, max_length=500)
    sort_order: int = Field(default=0, ge=0, le=10_000)
