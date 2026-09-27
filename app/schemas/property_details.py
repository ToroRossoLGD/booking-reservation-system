from typing import Literal

from pydantic import BaseModel, Field


class PropertyDetails(BaseModel):
    property_type: Literal["apartment", "house"] | None = None
    neighborhood: str | None = Field(default=None, max_length=100)
    floor: int | None = Field(default=None, ge=-2, le=200)
    heating: (
        Literal["district", "electric", "gas", "heat_pump", "solid_fuel", "other"]
        | None
    ) = None
    furnishing: Literal["furnished", "partial", "unfurnished"] | None = None
    has_elevator: bool | None = None
    has_parking: bool | None = None
    has_terrace: bool | None = None
