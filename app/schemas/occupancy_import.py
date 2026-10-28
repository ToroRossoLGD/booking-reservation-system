from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class OccupancyImportRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    content: str = Field(min_length=1, max_length=100_000)


class ImportedRange(BaseModel):
    check_in: date
    check_out: date
    status: Literal["ready", "existing", "conflict"]


class OccupancyImportResult(BaseModel):
    ranges: list[ImportedRange]
    ignored: int
    clipped: int
    applied: bool
    created: int


class OccupancyImportRunRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    created_at: datetime
    status: Literal["applied", "conflict"]
    created: int
    existing: int
    conflicts: int
    ignored: int
    clipped: int
