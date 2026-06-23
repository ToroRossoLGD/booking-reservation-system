from datetime import datetime

from pydantic import BaseModel


class ReservationCreate(BaseModel):
    resource_id: int
    start_time: datetime
    end_time: datetime


class ReservationRead(BaseModel):
    id: int
    start_time: datetime
    end_time: datetime
    status: str
    user_id: int
    resource_id: int

    model_config = {"from_attributes": True}


class AvailabilityRead(BaseModel):
    resource_id: int
    start_time: datetime
    end_time: datetime
    available: bool


class AvailableSlotRead(BaseModel):
    start_time: datetime
    end_time: datetime
    available: bool


class ReservationListRead(BaseModel):
    items: list[ReservationRead]
    total: int
    limit: int
    offset: int
    has_next: bool
