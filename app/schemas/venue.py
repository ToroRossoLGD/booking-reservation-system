from pydantic import BaseModel, Field


class VenueCreate(BaseModel):
    name: str = Field(min_length=2, max_length=255)
    description: str | None = None
    address: str = Field(min_length=2, max_length=255)


class VenueRead(BaseModel):
    id: int
    name: str
    description: str | None
    address: str
    owner_id: int

    model_config = {"from_attributes": True}
