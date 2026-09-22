from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class RentalMessageCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    request_id: UUID
    body: str = Field(min_length=1, max_length=3000)


class RentalMessageRead(BaseModel):
    id: int
    sender: Literal["owner", "tenant"]
    kind: Literal[
        "message", "legacy_reply", "propose", "confirm", "decline", "close", "withdraw"
    ]
    body: str
    viewing_at: datetime | None
    created_at: datetime | None
    read_at: datetime | None


class RentalMessagePage(BaseModel):
    items: list[RentalMessageRead]
    has_more: bool
    next_before_id: int | None
    unread_count: int


class RentalMessagesRead(BaseModel):
    model_config = ConfigDict(extra="forbid")
    message_ids: list[int] = Field(min_length=1, max_length=50)


class RentalUnreadCount(BaseModel):
    unread_count: int
