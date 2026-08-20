from datetime import datetime
from typing import Literal

from pydantic import BaseModel, EmailStr

VenueStaffRoleValue = Literal["manager", "check_in_agent"]


class VenueStaffCreate(BaseModel):
    email: EmailStr
    role: VenueStaffRoleValue


class VenueStaffUpdate(BaseModel):
    role: VenueStaffRoleValue


class VenueStaffRead(BaseModel):
    id: int
    venue_id: int
    user_id: int
    role: str
    assigned_at: datetime
    assigned_by_id: int | None
    revoked_at: datetime | None

    model_config = {"from_attributes": True}


class MyVenueAssignmentRead(VenueStaffRead):
    venue_name: str
