from decimal import ROUND_HALF_UP, Decimal

from pydantic import BaseModel, Field, field_validator, model_validator


class PropertyMapLocation(BaseModel):
    # Only the public approximate point is persisted. No precise coordinate copy.
    map_latitude: float | None = Field(default=None, ge=-85, le=85, allow_inf_nan=False)
    map_longitude: float | None = Field(
        default=None, ge=-180, le=180, allow_inf_nan=False
    )

    @field_validator("map_latitude", "map_longitude")
    @classmethod
    def approximate(cls, value):
        if value is None:
            return None
        return float(
            Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        )

    @model_validator(mode="after")
    def coordinate_pair(self):
        if (self.map_latitude is None) != (self.map_longitude is None):
            raise ValueError("Provide both map coordinates, or neither")
        return self
