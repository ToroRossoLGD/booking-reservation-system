from datetime import datetime

from pydantic import BaseModel


class ResourceAvailabilityCheck(BaseModel):
    resource_id: int
    start_time: datetime
    end_time: datetime
    is_available: bool
    reason: str | None = None
