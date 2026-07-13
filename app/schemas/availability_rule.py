from datetime import time

from pydantic import BaseModel, Field, model_validator


class AvailabilityRuleCreate(BaseModel):
    weekday: int = Field(ge=0, le=6)
    start_time: time
    end_time: time

    @model_validator(mode="after")
    def validate_time_interval(self):
        if self.start_time >= self.end_time:
            raise ValueError("start_time must be earlier than end_time")

        return self


class AvailabilityRuleRead(BaseModel):
    id: int
    resource_id: int
    weekday: int
    start_time: time
    end_time: time

    model_config = {
        "from_attributes": True,
    }
