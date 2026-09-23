from pydantic import BaseModel, ConfigDict, Field, PositiveInt


class PropertyPhotoRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    property_id: int
    position: int
    width: int
    height: int


class PropertyPhotoOrder(BaseModel):
    model_config = ConfigDict(extra="forbid")
    photo_ids: list[PositiveInt] = Field(max_length=12)
