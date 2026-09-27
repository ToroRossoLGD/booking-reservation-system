from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class PropertyViewCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    visitor_id: UUID


class PropertyAnalyticsMonth(BaseModel):
    month: int
    views: int = 0
    reservations: int = 0
    cancelled: int = 0
    nights: int = 0
    booked_value_cents: dict[str, int] = Field(default_factory=dict)


class AnalyticsProperty(BaseModel):
    id: int
    title: str
    offer_type: str


class PropertyAnalytics(BaseModel):
    year: int
    properties: list[AnalyticsProperty]
    months: list[PropertyAnalyticsMonth]
