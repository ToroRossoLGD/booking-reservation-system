import hashlib
import hmac
import json
import socket
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from app.core.config import settings
from app.models.webhook import WebhookDeliveryStatus
from app.schemas.webhook import WebhookCreate, WebhookUpdate
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


@pytest.mark.asyncio
@pytest.mark.parametrize("missing", [False, True])
async def test_inactive_or_deleted_subscription_never_sends(missing):
    service = WebhookService(AsyncMock())
    item = delivery(attempts=2)
    service.repository.get_due_deliveries = AsyncMock(return_value=[item])
    service.repository.get_subscription = AsyncMock(
        return_value=None if missing else subscription(is_active=False)
    )
    service.repository.save_delivery = AsyncMock()
    service._ensure_public_target = AsyncMock()
    client = FakeClient()

    with patch("app.services.webhook_service.httpx.AsyncClient", return_value=client):
        result = await service.deliver_due()

    assert result == {"processed": 1, "delivered": 0, "retrying": 0, "failed": 1}
    assert item.status == "failed"
    assert item.attempts == 2
    assert client.request is None
    service._ensure_public_target.assert_not_awaited()
    service.repository.save_delivery.assert_awaited_once_with(item)


@pytest.mark.asyncio
@pytest.mark.parametrize("private_ip", ["127.0.0.1", "::1"])
async def test_mixed_public_and_private_dns_answers_prevent_http_delivery(private_ip):
    service = WebhookService(AsyncMock())
    item = delivery()
    service.repository.get_due_deliveries = AsyncMock(return_value=[item])
    service.repository.get_subscription = AsyncMock(return_value=subscription())
    service.repository.save_delivery = AsyncMock()
    addresses = [
        (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("9.9.9.9", 443)),
        (
            socket.AF_INET6 if ":" in private_ip else socket.AF_INET,
            socket.SOCK_STREAM,
            6,
            "",
            (private_ip, 443),
        ),
    ]
    client = FakeClient()

    with (
        patch(
            "app.services.webhook_service.socket.getaddrinfo", return_value=addresses
        ),
        patch("app.services.webhook_service.httpx.AsyncClient", return_value=client),
    ):
        result = await service.deliver_due()

    assert client.request is None
    assert item.status == "retrying"
    assert "non-public address" in item.last_error
    assert result["retrying"] == 1
    service.repository.save_delivery.assert_awaited_once_with(item)


@pytest.mark.asyncio
async def test_one_timeout_does_not_abort_remaining_due_deliveries(monkeypatch):
    monkeypatch.setattr(settings, "WEBHOOK_MAX_ATTEMPTS", 3)
    monkeypatch.setattr(settings, "WEBHOOK_RETRY_BASE_SECONDS", 60)
    service = WebhookService(AsyncMock())
    items = [delivery(id=1), delivery(id=2), delivery(id=3)]
    service.repository.get_due_deliveries = AsyncMock(return_value=items)
    service.repository.get_subscription = AsyncMock(return_value=subscription())
    service.repository.save_delivery = AsyncMock()
    service._ensure_public_target = AsyncMock()
    client = FakeClient()
    client.post = AsyncMock(
        side_effect=[
            httpx.Response(204),
            httpx.ReadTimeout("timeout"),
            httpx.Response(200),
        ]
    )
    now = datetime(2030, 1, 1, tzinfo=UTC)

    with patch("app.services.webhook_service.httpx.AsyncClient", return_value=client):
        result = await service.deliver_due(now, limit=3)

    assert result == {"processed": 3, "delivered": 2, "retrying": 1, "failed": 0}
    assert [item.status for item in items] == ["delivered", "retrying", "delivered"]
    assert [item.attempts for item in items] == [1, 1, 1]
    assert items[1].next_attempt_at == now + timedelta(seconds=60)
    assert items[0].delivered_at == items[2].delivered_at == now
    assert client.post.await_count == 3
    assert [
        call.args[0] for call in service.repository.save_delivery.await_args_list
    ] == items
    service.repository.get_due_deliveries.assert_awaited_once_with(now, 3)


@pytest.mark.asyncio
@pytest.mark.parametrize("already_active", [False, True])
async def test_full_quota_blocks_reactivation_but_allows_editing_active_hook(
    already_active,
):
    service = WebhookService(AsyncMock())
    item = subscription(is_active=already_active)
    service.venue_repository.get_by_id = AsyncMock(return_value=MagicMock(owner_id=10))
    service.repository.get_for_venue = AsyncMock(return_value=item)
    service.repository.count_active = AsyncMock(
        return_value=settings.MAX_ACTIVE_VENUE_WEBHOOKS
    )
    service.repository.update = AsyncMock(side_effect=lambda value: value)
    data = WebhookUpdate(**create_data().model_dump(), is_active=True)

    if already_active:
        assert await service.update(7, 2, data, owner()) is item
        service.repository.update.assert_awaited_once_with(item)
        service.repository.count_active.assert_not_awaited()
    else:
        with pytest.raises(HTTPException) as error:
            await service.update(7, 2, data, owner())
        assert error.value.status_code == 409
        assert item.is_active is False
        service.repository.update.assert_not_awaited()
