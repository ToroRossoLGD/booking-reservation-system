from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from app.models.webhook import WebhookDeliveryStatus
from app.schemas.maintenance import (
    WorkOrderCreate,
    WorkOrderTransition,
    WorkOrderUpdate,
)
from app.schemas.webhook import WebhookCreate
from app.services.calendar_feed_service import CalendarFeedService
from app.services.maintenance_service import MaintenanceService
from app.services.webhook_service import UnsafeWebhookTargetError, WebhookService


def user(user_id=10, role="owner"):
    return MagicMock(id=user_id, role=role)


def venue(owner_id=10):
    return MagicMock(id=7, owner_id=owner_id)


def webhook(**changes):
    values = {
        "id": 2,
        "venue_id": 7,
        "signing_key": "old-key",
        "is_active": True,
        "target_url": "https://hooks.example.com/events",
        "updated_at": datetime.now(UTC),
    }
    values.update(changes)
    return MagicMock(**values)


def calendar_feed(**changes):
    values = {
        "id": 3,
        "venue_id": 7,
        "token_prefix": "cal_old",
        "token_hash": "old-hash",
        "revoked_at": None,
    }
    values.update(changes)
    return MagicMock(**values)


def delivery():
    return MagicMock(
        id=8,
        subscription_id=2,
        payload={"type": "reservation.created"},
        status="pending",
        attempts=0,
        next_attempt_at=datetime.now(UTC),
        response_status=None,
        last_error=None,
        delivered_at=None,
        updated_at=datetime.now(UTC),
    )


@pytest.mark.parametrize(
    "target_url",
    [
        "https://user:password@example.com/hook",
        "https://example.com/hook#secret-fragment",
    ],
)
def test_webhook_url_rejects_credentials_and_fragments(target_url):
    with pytest.raises(ValidationError):
        WebhookCreate(
            name="Unsafe",
            target_url=target_url,
            event_types=["created"],
        )


@pytest.mark.asyncio
async def test_webhook_delivery_rejects_hostname_resolving_to_private_ip():
    service = WebhookService(AsyncMock())
    addresses = [(2, 1, 6, "", ("10.0.0.5", 443))]

    with (
        patch(
            "app.services.webhook_service.asyncio.to_thread",
            new=AsyncMock(return_value=addresses),
        ),
        pytest.raises(UnsafeWebhookTargetError) as error,
    ):
        await service._ensure_public_target("https://hooks.example.com/events")

    assert "non-public" in str(error.value)


@pytest.mark.asyncio
async def test_webhook_delivery_accepts_hostname_resolving_only_to_public_ips():
    service = WebhookService(AsyncMock())
    addresses = [
        (2, 1, 6, "", ("93.184.216.34", 443)),
        (10, 1, 6, "", ("2606:2800:220:1:248:1893:25c8:1946", 443, 0, 0)),
    ]

    with patch(
        "app.services.webhook_service.asyncio.to_thread",
        new=AsyncMock(return_value=addresses),
    ):
        await service._ensure_public_target("https://hooks.example.com/events")


@pytest.mark.asyncio
async def test_unsafe_webhook_target_uses_normal_retry_policy_without_http_request():
    service = WebhookService(AsyncMock())
    item = delivery()
    service.repository.get_due_deliveries = AsyncMock(return_value=[item])
    service.repository.get_subscription = AsyncMock(return_value=webhook())
    service.repository.save_delivery = AsyncMock()
    service._ensure_public_target = AsyncMock(
        side_effect=UnsafeWebhookTargetError("non-public")
    )
    client = MagicMock()
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=None)
    client.post = AsyncMock()

    with patch("app.services.webhook_service.httpx.AsyncClient", return_value=client):
        result = await service.deliver_due()

    assert item.status == WebhookDeliveryStatus.RETRYING.value
    assert "non-public" in item.last_error
    assert result["retrying"] == 1
    client.post.assert_not_awaited()


@pytest.mark.asyncio
async def test_active_webhook_secret_can_be_rotated():
    service = WebhookService(AsyncMock())
    item = webhook()
    service.venue_repository.get_by_id = AsyncMock(return_value=venue())
    service.repository.get_for_venue = AsyncMock(return_value=item)
    service.repository.update = AsyncMock(side_effect=lambda value: value)

    result = await service.rotate_secret(7, 2, user())

    assert item.signing_key != "old-key"
    assert result["id"] == 2
    assert result["signing_secret"] == service._secret(item.signing_key)
    service.repository.update.assert_awaited_once_with(item)


@pytest.mark.asyncio
async def test_inactive_webhook_secret_cannot_be_rotated():
    service = WebhookService(AsyncMock())
    service.venue_repository.get_by_id = AsyncMock(return_value=venue())
    service.repository.get_for_venue = AsyncMock(return_value=webhook(is_active=False))

    with pytest.raises(HTTPException) as error:
        await service.rotate_secret(7, 2, user())

    assert error.value.status_code == 409


@pytest.mark.asyncio
async def test_active_calendar_feed_token_can_be_rotated():
    service = CalendarFeedService(AsyncMock())
    item = calendar_feed()
    service.venue_repository.get_by_id = AsyncMock(return_value=venue())
    service.repository.get_for_venue = AsyncMock(return_value=item)
    service.repository.save = AsyncMock(side_effect=lambda value: value)

    result = await service.rotate_token(7, 3, user())

    assert item.token_prefix.startswith("cal_")
    assert item.token_prefix != "cal_old"
    assert item.token_hash == service._hash_token(result["feed_token"])
    assert result["feed_path"].endswith(".ics")


@pytest.mark.asyncio
async def test_revoked_calendar_feed_token_cannot_be_rotated():
    service = CalendarFeedService(AsyncMock())
    service.venue_repository.get_by_id = AsyncMock(return_value=venue())
    service.repository.get_for_venue = AsyncMock(
        return_value=calendar_feed(revoked_at=datetime.now(UTC))
    )

    with pytest.raises(HTTPException) as error:
        await service.rotate_token(7, 3, user())

    assert error.value.status_code == 409


@pytest.mark.parametrize(
    "schema",
    [
        lambda: WorkOrderCreate(
            title="Inspect unit",
            description="Inspection required",
            due_at=datetime(2026, 8, 22, 12),
        ),
        lambda: WorkOrderUpdate(due_at=datetime(2026, 8, 22, 12)),
    ],
)
def test_maintenance_due_date_requires_timezone(schema):
    with pytest.raises(ValidationError) as error:
        schema()

    assert "due_at must include a timezone" in str(error.value)


@pytest.mark.asyncio
async def test_unknown_stored_work_order_status_returns_controlled_conflict():
    service = MaintenanceService(AsyncMock())
    service.venue_repository.get_by_id = AsyncMock(return_value=venue())
    service.repository.get_for_venue = AsyncMock(
        return_value=MagicMock(id=4, status="legacy_status")
    )

    with pytest.raises(HTTPException) as error:
        await service.transition(7, 4, WorkOrderTransition(status="open"), user())

    assert error.value.status_code == 409
    assert "unsupported status" in error.value.detail
