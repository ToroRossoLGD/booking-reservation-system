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

    model_config = {
        "from_attributes": True
    }