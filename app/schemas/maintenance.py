from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator

Priority = Literal["low", "medium", "high", "urgent"]
Status = Literal["open", "in_progress", "on_hold", "resolved", "cancelled"]


class WorkOrderCreate(BaseModel):
    resource_id: int | None = Field(default=None, gt=0)
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(min_length=1, max_length=5000)
    priority: Priority = "medium"
    due_at: datetime | None = None
    model_config = {"str_strip_whitespace": True}


class WorkOrderUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, min_length=1, max_length=5000)
    priority: Priority | None = None
    due_at: datetime | None = None

    @model_validator(mode="after")
    def require_change(self):
        if not self.model_fields_set:
            raise ValueError("At least one field must be provided")
        return self

    model_config = {"str_strip_whitespace": True}


class WorkOrderAssignment(BaseModel):
    assigned_to_id: int | None = Field(default=None, gt=0)


class WorkOrderTransition(BaseModel):
    status: Status
    note: str | None = Field(default=None, max_length=1000)
    model_config = {"str_strip_whitespace": True}


class WorkOrderComment(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    model_config = {"str_strip_whitespace": True}


class WorkOrderRead(BaseModel):
    id: int
    venue_id: int
    resource_id: int | None
    title: str
    description: str
    priority: str
    status: str
    reported_by_id: int | None
    assigned_to_id: int | None
    due_at: datetime | None
    resolved_at: datetime | None
    created_at: datetime
    updated_at: datetime
    model_config = {"from_attributes": True}


class WorkOrderActivityRead(BaseModel):
    id: int
    work_order_id: int
    actor_id: int | None
    activity_type: str
    message: str | None
    details: dict
    created_at: datetime
    model_config = {"from_attributes": True}
