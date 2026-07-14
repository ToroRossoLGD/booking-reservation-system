from datetime import datetime

from pydantic import BaseModel, Field


class ResourceCreate(BaseModel):
    name: str = Field(min_length=2, max_length=255)
    resource_type: str = Field(min_length=2, max_length=100)
    capacity: int = Field(default=1, ge=1)


class ResourceRead(BaseModel):
    id: int
    name: str
    resource_type: str
    capacity: int
    venue_id: int

    model_config = {"from_attributes": True}


class ResourceSearchRead(BaseModel):
    id: int
    name: str
    resource_type: str
    capacity: int
    venue_id: int
    venue_name: str
    venue_address: str


class ResourceListRead(BaseModel):
    items: list[ResourceSearchRead]
    total: int
    limit: int
    offset: int
    has_next: bool


class AvailableResourceRead(BaseModel):
    id: int
    name: str
    resource_type: str
    capacity: int
    venue_id: int
    venue_name: str
    venue_address: str


class AvailableResourceListRead(BaseModel):
    items: list[AvailableResourceRead]
    start_time: datetime
    end_time: datetime
    total: int
    limit: int
    offset: int
    has_next: bool
