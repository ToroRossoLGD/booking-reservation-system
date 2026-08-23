from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator


class WaiverTemplateCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    content: str = Field(min_length=20, max_length=50000)
    is_required: bool = True
    model_config = {"str_strip_whitespace": True}


class WaiverTemplateUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    is_required: bool | None = None

    @model_validator(mode="after")
    def require_change(self):
        if not self.model_fields_set:
            raise ValueError("At least one field must be provided")
        return self

    model_config = {"str_strip_whitespace": True}


class WaiverVersionCreate(BaseModel):
    content: str = Field(min_length=20, max_length=50000)
    model_config = {"str_strip_whitespace": True}


class WaiverVersionRead(BaseModel):
    id: int
    template_id: int
    version: int
    content: str
    content_sha256: str
    published_by_id: int | None
    published_at: datetime
    model_config = {"from_attributes": True}


class WaiverTemplateRead(BaseModel):
    id: int
    venue_id: int
    name: str
    description: str | None
    is_required: bool
    is_active: bool
    current_version: int
    created_at: datetime
    updated_at: datetime
    model_config = {"from_attributes": True}


class WaiverRequirementRead(BaseModel):
    template: WaiverTemplateRead
    version: WaiverVersionRead
    accepted: bool
    acceptance_id: int | None = None


class WaiverAcceptanceCreate(BaseModel):
    waiver_version_id: int = Field(gt=0)
    signer_name: str = Field(min_length=2, max_length=200)
    accepted_terms: Literal[True]
    model_config = {"str_strip_whitespace": True}


class WaiverAcceptanceRead(BaseModel):
    id: int
    reservation_id: int
    waiver_version_id: int
    user_id: int
    signer_name: str
    content_sha256: str
    ip_address: str | None
    user_agent: str | None
    accepted_at: datetime
    model_config = {"from_attributes": True}
