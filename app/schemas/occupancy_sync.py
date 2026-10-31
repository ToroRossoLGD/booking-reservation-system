from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class OccupancySyncWrite(BaseModel):
    model_config = ConfigDict(extra="forbid")
    action: Literal["connect", "pause", "resume", "refresh", "disconnect"]
    url: str | None = Field(default=None, min_length=1, max_length=2048, repr=False)
    allow_empty: bool = False

    @model_validator(mode="after")
    def connect_url(self):
        if self.action == "connect" and not self.url:
            raise ValueError("A calendar URL is required")
        if self.action != "connect" and self.url is not None:
            raise ValueError("URL is only accepted when connecting")
        return self


class OccupancySyncRead(BaseModel):
    available: bool
    configured: bool
    enabled: bool
    allow_empty: bool
    running: bool
    overdue: bool
    next_run_at: datetime | None
    last_attempt_at: datetime | None
    last_success_at: datetime | None
    last_status: Literal[
        "unconfigured",
        "pending",
        "applied",
        "conflict",
        "superseded",
        "inactive",
        "fetch_error",
        "key_error",
        "blocked_empty",
    ]
