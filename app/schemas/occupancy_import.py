from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class OccupancyImportRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    content: str = Field(min_length=1, max_length=100_000)
    source_id: int | None = Field(default=None, gt=0)
    source_revision: int | None = Field(default=None, ge=0)


class OccupancyUrlRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    url: str = Field(min_length=1, max_length=2048, repr=False)


class OccupancyConflict(BaseModel):
    check_in: date
    check_out: date
    kind: Literal["reservation", "block"]


class ImportedRange(BaseModel):
    check_in: date
    check_out: date
    status: Literal["ready", "existing", "conflict"]
    conflicts: list[OccupancyConflict] = Field(default_factory=list)


class RemovedRange(BaseModel):
    check_in: date
    check_out: date


class OccupancyImportResult(BaseModel):
    ranges: list[ImportedRange]
    ignored: int
    clipped: int
    applied: bool
    created: int
    removed: int = 0
    source_revision: int | None = None
    removed_ranges: list[RemovedRange] = Field(default_factory=list)


class OccupancySourceCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    name: str = Field(min_length=1, max_length=80)


class OccupancySourceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    revision: int
    last_attempt_at: datetime | None
    last_success_at: datetime | None
    last_status: Literal["applied", "conflict"] | None


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
