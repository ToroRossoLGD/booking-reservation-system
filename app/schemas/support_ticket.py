from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator


class SupportTicketCreate(BaseModel):
    subject: str = Field(min_length=3, max_length=255)
    category: Literal["technical", "billing", "account", "feedback", "other"]
    message: str = Field(min_length=1, max_length=10_000)


class SupportMessageCreate(BaseModel):
    message: str = Field(min_length=1, max_length=10_000)


class AdminSupportMessageCreate(SupportMessageCreate):
    is_internal: bool = False


class SupportMessageRead(BaseModel):
    id: int
    ticket_id: int
    author_id: int
    body: str
    is_internal: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class SupportTicketRead(BaseModel):
    id: int
    creator_id: int
    assigned_admin_id: int | None
    subject: str
    category: str
    priority: str
    status: str
    created_at: datetime
    updated_at: datetime
    resolved_at: datetime | None
    closed_at: datetime | None

    model_config = {"from_attributes": True}


class SupportTicketDetailRead(SupportTicketRead):
    messages: list[SupportMessageRead]


class SupportTicketListRead(BaseModel):
    items: list[SupportTicketRead]
    total: int
    limit: int
    offset: int
    has_next: bool


class SupportTicketAdminUpdate(BaseModel):
    status: (
        Literal["open", "in_progress", "waiting_customer", "resolved", "closed"] | None
    ) = None
    priority: Literal["low", "normal", "high", "urgent"] | None = None
    assigned_admin_id: int | None = None

    @model_validator(mode="after")
    def require_change(self):
        if not self.model_fields_set:
            raise ValueError("At least one ticket field must be provided")
        return self
