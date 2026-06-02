from datetime import datetime

from pydantic import BaseModel


class OwnerVenueRead(BaseModel):
    id: int
    name: str
    description: str | None
    address: str
    owner_id: int

    model_config = {
        "from_attributes": True
    }


class OwnerResourceRead(BaseModel):
    id: int
    name: str
    resource_type: str
    capacity: int
    venue_id: int
    venue_name: str


class OwnerReservationRead(BaseModel):
    id: int
    start_time: datetime
    end_time: datetime
    status: str
    user_id: int
    resource_id: int
    resource_name: str
    venue_id: int
    venue_name: str