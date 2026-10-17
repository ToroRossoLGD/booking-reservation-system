from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class OwnerAccessCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    request_id: UUID
    details: str = Field(min_length=20, max_length=2000)


class OwnerAccessDecision(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    action: Literal["approved", "rejected"]
    note: str = Field(min_length=10, max_length=2000)


class OwnerAccessRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    user_id: int
    email: str
    details: str
    status: Literal["pending", "approved", "rejected"]
    created_at: datetime
    decided_at: datetime | None
    decision_note: str | None


class OwnerAccessPage(BaseModel):
    items: list[OwnerAccessRead]
    has_next: bool
