from datetime import datetime

from pydantic import BaseModel


class ReservationEventRead(BaseModel):
    id: int
    reservation_id: int
    event_type: str
    actor_id: int | None
    actor_role: str
    previous_status: str | None
    new_status: str
    details: dict
    occurred_at: datetime

    model_config = {"from_attributes": True}


class ReservationTimelineRead(BaseModel):
    reservation_id: int
    events: list[ReservationEventRead]
