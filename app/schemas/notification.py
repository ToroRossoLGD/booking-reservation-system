from datetime import datetime

from pydantic import BaseModel


class NotificationRead(BaseModel):
    id: int
    user_id: int
    title: str
    message: str
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
