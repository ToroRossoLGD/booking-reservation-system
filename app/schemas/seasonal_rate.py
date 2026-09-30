from datetime import date

from pydantic import BaseModel, ConfigDict, Field, model_validator


class SeasonalRate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    start: date
    end: date
    price_cents: int = Field(ge=1, le=1000000000000)
    label: str = Field(default="", max_length=80)

    @model_validator(mode="after")
    def ordered_dates(self):
        if self.end <= self.start:
            raise ValueError("Season end must be after start (end is exclusive)")
        return self


class NightlyPrice(BaseModel):
    model_config = ConfigDict(extra="forbid")
    date: date
    price_cents: int = Field(ge=1, le=1000000000000)
