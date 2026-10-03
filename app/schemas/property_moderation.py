from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class PropertyReportCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    request_id: UUID
    category: Literal["misleading", "fraud", "inappropriate", "duplicate", "other"]
    details: str = Field(min_length=10, max_length=2000)


class ReportSnapshot(BaseModel):
    title: str
    description: str
    city: str
    offer_type: str
    price_cents: int
    currency: str


class PropertyReportRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    property_id: int
    category: str
    details: str
    snapshot: ReportSnapshot
    status: str
    created_at: datetime
    resolved_at: datetime | None


class ModerationAction(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    request_id: UUID
    version: int = Field(ge=0)
    note: str = Field(min_length=10, max_length=2000)
    action: Literal["dismiss", "hide", "appeal", "restore", "uphold"]


class ModerationCase(BaseModel):
    id: int
    title: str
    state: str
    version: int
    note: str
    appeal: str
    is_published: bool


class ReportItem(PropertyReportRead):
    listing: ModerationCase


class ReportPage(BaseModel):
    items: list[ReportItem]
    total: int
    has_next: bool


class ModerationPage(BaseModel):
    items: list[ModerationCase]
    total: int
    has_next: bool


class ModerationEventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    action: str
    note: str
    version: int
    created_at: datetime


class ModerationHistory(BaseModel):
    items: list[ModerationEventRead]
    total: int
    has_next: bool
