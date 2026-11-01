from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, StrictBool, StrictInt, field_validator


class StayReminderPreferences(BaseModel):
    model_config = ConfigDict(extra="forbid")
    enabled: StrictBool


class PropertyEmailDigestRead(BaseModel):
    interval_hours: Literal[1, 24]
    next_run_at: datetime | None
    enabled: bool
    available: bool
    verified: bool
    last_status: Literal["unconfigured", "pending", "accepted", "failed", "unverified"]
    last_attempt_at: datetime | None
    last_accepted_at: datetime | None


class PropertyEmailDigestWrite(StayReminderPreferences):
    interval_hours: StrictInt | None = None

    @field_validator("interval_hours")
    @classmethod
    def allowed_interval(cls, value):
        if value is not None and value not in (1, 24):
            raise ValueError("Choose 1 or 24 hours")
        return value


class ReminderDeliveryRead(BaseModel):
    id: int
    kind: Literal["arrival", "departure", "rental_viewing", "sale_viewing"]
    reference_id: int
    scheduled_for: str
    created_at: datetime


class ReminderHistoryRead(BaseModel):
    items: list[ReminderDeliveryRead]
    offset: int
    has_next: bool


class NotificationRead(BaseModel):
    id: int
    user_id: int
    title: str
    message: str
    action_path: str | None = None
    is_read: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class UnreadNotificationCount(BaseModel):
    unread_count: int


class DismissedNotificationCount(BaseModel):
    dismissed_count: int


class NotificationListRead(BaseModel):
    items: list[NotificationRead]
    total: int
    limit: int
    offset: int
    has_next: bool
