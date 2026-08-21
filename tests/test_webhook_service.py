import hashlib
import hmac
import json
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from app.core.config import settings
from app.models.webhook import WebhookDeliveryStatus
from app.schemas.webhook import WebhookCreate
from app.services.webhook_service import WebhookService


def owner(user_id=10, role="owner"):
    return MagicMock(id=user_id, role=role)


def create_data(**changes):
    values = {
        "name": "CRM sync",
        "target_url": "https://integrations.example.com/bookings",
        "event_types": ["created", "cancelled"],
    }
    values.update(changes)
    return WebhookCreate(**values)


def subscription(**changes):
    values = {
        "id": 2,
        "venue_id": 7,
        "name": "CRM sync",
        "target_url": "https://integrations.example.com/bookings",
        "event_types": ["created"],
        "signing_key": "public-random-signing-key",
        "is_active": True,
        "created_by_id": 10,
        "created_at": datetime.now(UTC),
        "updated_at": datetime.now(UTC),
    }
    values.update(changes)
    return MagicMock(**values)


def delivery(**changes):
    values = {
        "id": 9,
        "subscription_id": 2,
        "event_id": 4,
        "event_type": "created",
        "payload": {"id": 4, "type": "reservation.created"},
        "status": "pending",
        "attempts": 0,
        "next_attempt_at": datetime.now(UTC),
        "response_status": None,
        "last_error": None,
        "delivered_at": None,
        "updated_at": datetime.now(UTC),
    }
    values.update(changes)
    return MagicMock(**values)


@pytest.mark.parametrize(
    "url",
    [
        "http://example.com/hook",
        "https://localhost/hook",
        "https://127.0.0.1/hook",
        "https://10.0.0.2/hook",
    ],
)
def test_webhook_requires_public_https_target(url):
    with pytest.raises(ValidationError):
        create_data(target_url=url)


def test_webhook_rejects_duplicate_event_types():
    with pytest.raises(ValidationError):
        create_data(event_types=["created", "created"])


@pytest.mark.asyncio
async def test_owner_creates_webhook_and_receives_secret_once():
    service = WebhookService(AsyncMock())
    service.venue_repository.get_by_id = AsyncMock(return_value=MagicMock(owner_id=10))
    service.repository.count_active = AsyncMock(return_value=0)
    service.repository.create = AsyncMock(side_effect=lambda item: item)

    result = await service.create(7, create_data(), owner())

    assert result["signing_secret"]
    assert result["venue_id"] == 7
    assert result["event_types"] == ["created", "cancelled"]


@pytest.mark.asyncio
async def test_non_owner_cannot_manage_venue_webhooks():
    service = WebhookService(AsyncMock())
    service.venue_repository.get_by_id = AsyncMock(return_value=MagicMock(owner_id=99))
    with pytest.raises(HTTPException) as error:
        await service.create(7, create_data(), owner())
    assert error.value.status_code == 403


@pytest.mark.asyncio
async def test_active_subscription_limit_is_enforced():
    service = WebhookService(AsyncMock())
    service.venue_repository.get_by_id = AsyncMock(return_value=MagicMock(owner_id=10))
    service.repository.count_active = AsyncMock(
        return_value=settings.MAX_ACTIVE_VENUE_WEBHOOKS
    )
    with pytest.raises(HTTPException) as error:
        await service.create(7, create_data(), owner())
    assert error.value.status_code == 409


@pytest.mark.asyncio
async def test_webhook_can_be_deactivated_without_deleting_history():
    service = WebhookService(AsyncMock())
    item = subscription()
    service.venue_repository.get_by_id = AsyncMock(return_value=MagicMock(owner_id=10))
    service.repository.get_for_venue = AsyncMock(return_value=item)
    service.repository.update = AsyncMock(side_effect=lambda value: value)
    result = await service.deactivate(7, 2, owner())
    assert result.is_active is False


class FakeClient:
    def __init__(self, response=None, error=None):
        self.response = response
        self.error = error
        self.request = None

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return None

    async def post(self, url, content, headers):
        self.request = (url, content, headers)
        if self.error:
            raise self.error
        return self.response


@pytest.mark.asyncio
async def test_successful_delivery_is_signed_and_recorded():
    service = WebhookService(AsyncMock())
    service._ensure_public_target = AsyncMock()
    item = delivery()
    hook = subscription()
    service.repository.get_due_deliveries = AsyncMock(return_value=[item])
    service.repository.get_subscription = AsyncMock(return_value=hook)
    service.repository.save_delivery = AsyncMock()
    client = FakeClient(
        httpx.Response(204, request=httpx.Request("POST", hook.target_url))
    )
    now = datetime(2026, 8, 21, 12, tzinfo=UTC)
    with patch("app.services.webhook_service.httpx.AsyncClient", return_value=client):
        result = await service.deliver_due(now)
    body = json.dumps(item.payload, separators=(",", ":"), sort_keys=True).encode()
    timestamp = str(int(now.timestamp()))
    expected = hmac.new(
        service._secret(hook.signing_key).encode(),
        timestamp.encode() + b"." + body,
        hashlib.sha256,
    ).hexdigest()
    assert client.request[2]["X-Webhook-Signature"] == f"sha256={expected}"
    assert item.status == WebhookDeliveryStatus.DELIVERED.value
    assert item.attempts == 1
    assert result["delivered"] == 1


@pytest.mark.asyncio
async def test_failed_delivery_is_scheduled_with_exponential_backoff():
    service = WebhookService(AsyncMock())
    service._ensure_public_target = AsyncMock()
    item = delivery(attempts=1)
    service.repository.get_due_deliveries = AsyncMock(return_value=[item])
    service.repository.get_subscription = AsyncMock(return_value=subscription())
    service.repository.save_delivery = AsyncMock()
    now = datetime(2026, 8, 21, 12, tzinfo=UTC)
    client = FakeClient(error=httpx.ConnectError("unreachable"))
    with patch("app.services.webhook_service.httpx.AsyncClient", return_value=client):
        result = await service.deliver_due(now)
    assert item.status == WebhookDeliveryStatus.RETRYING.value
    assert item.next_attempt_at == now + timedelta(
        seconds=settings.WEBHOOK_RETRY_BASE_SECONDS * 2
    )
    assert result["retrying"] == 1


@pytest.mark.asyncio
async def test_delivery_stops_retrying_at_attempt_limit():
    service = WebhookService(AsyncMock())
    service._ensure_public_target = AsyncMock()
    item = delivery(attempts=settings.WEBHOOK_MAX_ATTEMPTS - 1)
    service.repository.get_due_deliveries = AsyncMock(return_value=[item])
    service.repository.get_subscription = AsyncMock(return_value=subscription())
    service.repository.save_delivery = AsyncMock()
    client = FakeClient(error=httpx.ConnectError("unreachable"))
    with patch("app.services.webhook_service.httpx.AsyncClient", return_value=client):
        result = await service.deliver_due()
    assert item.status == WebhookDeliveryStatus.FAILED.value
    assert result["failed"] == 1


@pytest.mark.asyncio
async def test_delivered_webhook_cannot_be_manually_retried():
    service = WebhookService(AsyncMock())
    service.venue_repository.get_by_id = AsyncMock(return_value=MagicMock(owner_id=10))
    service.repository.get_delivery_for_venue = AsyncMock(
        return_value=delivery(status="delivered")
    )
    with pytest.raises(HTTPException) as error:
        await service.retry(7, 9, owner())
    assert error.value.status_code == 409


@pytest.mark.asyncio
async def test_manual_retry_resets_the_attempt_budget():
    service = WebhookService(AsyncMock())
    item = delivery(
        status="failed",
        attempts=settings.WEBHOOK_MAX_ATTEMPTS,
        response_status=503,
        last_error="HTTP 503",
    )
    service.venue_repository.get_by_id = AsyncMock(return_value=MagicMock(owner_id=10))
    service.repository.get_delivery_for_venue = AsyncMock(return_value=item)
    service.repository.save_delivery = AsyncMock()

    result = await service.retry(7, 9, owner())

    assert result.status == WebhookDeliveryStatus.PENDING.value
    assert result.attempts == 0
    assert result.response_status is None
    assert result.last_error is None
