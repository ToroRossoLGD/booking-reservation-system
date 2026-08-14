from datetime import datetime

from pydantic import BaseModel


class WaitlistEntryCreate(BaseModel):
    resource_id: int
    start_time: datetime
    end_time: datetime


class WaitlistEntryRead(BaseModel):
    id: int
    user_id: int
    resource_id: int
    start_time: datetime
    end_time: datetime
    status: str
    created_at: datetime
    notified_at: datetime | None

    model_config = {"from_attributes": True}
