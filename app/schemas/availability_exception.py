from datetime import datetime

from pydantic import BaseModel, Field, model_validator


class AvailabilityExceptionCreate(BaseModel):
    start_time: datetime
    end_time: datetime
    reason: str | None = Field(
        default=None,
        max_length=500,
    )

    @model_validator(mode="after")
    def validate_time_interval(self):
        if self.start_time >= self.end_time:
            raise ValueError("start_time must be earlier than end_time")

        if self.start_time.tzinfo is None:
            raise ValueError("start_time must include timezone information")

        if self.end_time.tzinfo is None:
            raise ValueError("end_time must include timezone information")

        return self


class AvailabilityExceptionRead(BaseModel):
    id: int
    resource_id: int
    start_time: datetime
    end_time: datetime
    reason: str | None

    model_config = {
        "from_attributes": True,
    }
