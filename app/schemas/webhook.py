from datetime import datetime
from ipaddress import ip_address
from typing import Literal

from pydantic import BaseModel, Field, HttpUrl, field_validator

WebhookEventType = Literal[
    "created",
    "rescheduled",
    "confirmed",
    "paid",
    "cancelled",
    "completed",
    "expired",
    "reminder_sent",
]


class WebhookCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    target_url: HttpUrl
    event_types: list[WebhookEventType] = Field(min_length=1)

    @field_validator("target_url")
    @classmethod
    def require_public_https(cls, value: HttpUrl) -> HttpUrl:
        if value.scheme != "https":
            raise ValueError("Webhook URLs must use HTTPS")
        host = (value.host or "").lower()
        if (
            host == "localhost"
            or host.endswith(".localhost")
            or host.endswith(".local")
        ):
            raise ValueError("Webhook URLs must use a public host")
        try:
            address = ip_address(host)
        except ValueError:
            address = None
        if address is not None and not address.is_global:
            raise ValueError("Webhook URLs must use a public host")
        return value

    @field_validator("event_types")
    @classmethod
    def unique_events(cls, value: list[str]) -> list[str]:
        if len(value) != len(set(value)):
            raise ValueError("event_types must not contain duplicates")
        return value

    model_config = {"str_strip_whitespace": True}


class WebhookUpdate(WebhookCreate):
    is_active: bool = True


class WebhookRead(BaseModel):
    id: int
    venue_id: int
    name: str
    target_url: str
    event_types: list[str]
    is_active: bool
    created_by_id: int | None
    created_at: datetime
    updated_at: datetime
    model_config = {"from_attributes": True}


class WebhookCreated(WebhookRead):
    signing_secret: str


class WebhookDeliveryRead(BaseModel):
    id: int
    subscription_id: int
    event_id: int
    event_type: str
    status: str
    attempts: int
    next_attempt_at: datetime
    response_status: int | None
    last_error: str | None
    delivered_at: datetime | None
    created_at: datetime
    updated_at: datetime
    model_config = {"from_attributes": True}
