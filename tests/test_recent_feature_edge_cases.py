from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from fastapi import HTTPException

from app.api.routers.calendar_feeds import get_calendar_feed
from app.core.config import settings
from app.models.maintenance import MaintenanceActivity, MaintenanceWorkOrder
from app.models.reservation_event import ReservationEvent
from app.models.webhook import WebhookDeliveryStatus
from app.repositories.maintenance_repository import MaintenanceRepository
from app.repositories.reservation_event_repository import ReservationEventRepository
from app.repositories.webhook_repository import WebhookRepository
from app.schemas.maintenance import (
    WorkOrderAssignment,
    WorkOrderComment,
    WorkOrderTransition,
    WorkOrderUpdate,
)
from app.schemas.venue_staff import VenueStaffUpdate
from app.schemas.webhook import WebhookUpdate
from app.services.calendar_feed_service import CalendarFeedService
from app.services.maintenance_service import MaintenanceService
from app.services.venue_staff_service import VenueStaffService
from app.services.webhook_service import WebhookService


def user(user_id=10, role="owner"):
    return MagicMock(id=user_id, role=role, email=f"user{user_id}@example.com")


def venue(owner_id=10):
    item = MagicMock(id=7, owner_id=owner_id, address="1 Main Street")
    item.name = "Central Venue"
    return item


def webhook(**changes):
    values = {
        "id": 2,
        "venue_id": 7,
        "name": "CRM",
        "target_url": "https://example.com/hook",
        "event_types": ["created"],
        "signing_key": "random-key",
        "is_active": True,
        "created_by_id": 10,
        "created_at": datetime.now(UTC),
        "updated_at": datetime.now(UTC),
    }
    values.update(changes)
    item = MagicMock(**values)
    item.name = values["name"]
    return item


def webhook_delivery(**changes):
    values = {
        "id": 8,
        "subscription_id": 2,
        "event_id": 3,
        "event_type": "created",
        "payload": {"id": 3, "type": "reservation.created"},
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


def work_order(**changes):
    values = {
        "id": 4,
        "venue_id": 7,
        "status": "open",
        "priority": "medium",
        "assigned_to_id": 20,
        "due_at": datetime.now(UTC),
        "resolved_at": None,
        "updated_at": datetime.now(UTC),
    }
    values.update(changes)
    return MagicMock(**values)


def calendar_feed(**changes):
    values = {
        "id": 3,
        "venue_id": 7,
        "resource_id": None,
        "name": "Venue bookings",
        "include_pending": False,
        "revoked_at": None,
        "last_accessed_at": None,
    }
    values.update(changes)
    item = MagicMock(**values)
    item.name = values["name"]
    return item


@pytest.mark.asyncio
async def test_webhook_management_returns_404_for_missing_venue():
    service = WebhookService(AsyncMock())
    service.venue_repository.get_by_id = AsyncMock(return_value=None)

    with pytest.raises(HTTPException) as error:
        await service.list(404, user())

    assert error.value.status_code == 404


@pytest.mark.asyncio
async def test_admin_can_list_webhooks_for_any_venue():
    service = WebhookService(AsyncMock())
    service.venue_repository.get_by_id = AsyncMock(return_value=venue(owner_id=99))
    service.repository.list_for_venue = AsyncMock(return_value=[webhook()])

    result = await service.list(7, user(1, "admin"))

    assert len(result) == 1


@pytest.mark.asyncio
async def test_updating_missing_webhook_returns_404():
    service = WebhookService(AsyncMock())
    service.venue_repository.get_by_id = AsyncMock(return_value=venue())
    service.repository.get_for_venue = AsyncMock(return_value=None)
    data = WebhookUpdate(
        name="CRM",
        target_url="https://example.com/hook",
        event_types=["created"],
    )

    with pytest.raises(HTTPException) as error:
        await service.update(7, 99, data, user())

    assert error.value.status_code == 404


@pytest.mark.asyncio
async def test_reactivating_webhook_respects_active_limit():
    service = WebhookService(AsyncMock())
    service.venue_repository.get_by_id = AsyncMock(return_value=venue())
    service.repository.get_for_venue = AsyncMock(return_value=webhook(is_active=False))
    service.repository.count_active = AsyncMock(
        return_value=settings.MAX_ACTIVE_VENUE_WEBHOOKS
    )
    data = WebhookUpdate(
        name="CRM",
        target_url="https://example.com/hook",
        event_types=["created"],
        is_active=True,
    )

    with pytest.raises(HTTPException) as error:
        await service.update(7, 2, data, user())

    assert error.value.status_code == 409


@pytest.mark.asyncio
async def test_inactive_subscription_fails_queued_delivery_without_http_call():
    service = WebhookService(AsyncMock())
    item = webhook_delivery()
    service.repository.get_due_deliveries = AsyncMock(return_value=[item])
    service.repository.get_subscription = AsyncMock(
        return_value=webhook(is_active=False)
    )
    service.repository.save_delivery = AsyncMock()
    client = MagicMock()
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=None)
    client.post = AsyncMock()

    with patch("app.services.webhook_service.httpx.AsyncClient", return_value=client):
        result = await service.deliver_due()

    assert item.status == WebhookDeliveryStatus.FAILED.value
    assert result["failed"] == 1
    client.post.assert_not_awaited()


@pytest.mark.asyncio
async def test_non_success_http_response_is_retried_and_status_is_recorded():
    service = WebhookService(AsyncMock())
    service._ensure_public_target = AsyncMock()
    item = webhook_delivery()
    service.repository.get_due_deliveries = AsyncMock(return_value=[item])
    service.repository.get_subscription = AsyncMock(return_value=webhook())
    service.repository.save_delivery = AsyncMock()
    response = httpx.Response(
        503, request=httpx.Request("POST", "https://example.com/hook")
    )
    client = MagicMock()
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=None)
    client.post = AsyncMock(return_value=response)

    with patch("app.services.webhook_service.httpx.AsyncClient", return_value=client):
        result = await service.deliver_due()

    assert item.response_status == 503
    assert item.status == WebhookDeliveryStatus.RETRYING.value
    assert result["retrying"] == 1


@pytest.mark.asyncio
async def test_retrying_missing_webhook_delivery_returns_404():
    service = WebhookService(AsyncMock())
    service.venue_repository.get_by_id = AsyncMock(return_value=venue())
    service.repository.get_delivery_for_venue = AsyncMock(return_value=None)

    with pytest.raises(HTTPException) as error:
        await service.retry(7, 999, user())

    assert error.value.status_code == 404


@pytest.mark.asyncio
async def test_calendar_management_returns_404_for_missing_venue():
    service = CalendarFeedService(AsyncMock())
    service.venue_repository.get_by_id = AsyncMock(return_value=None)

    with pytest.raises(HTTPException) as error:
        await service.list(404, user())

    assert error.value.status_code == 404


@pytest.mark.asyncio
async def test_admin_can_manage_calendar_feed_for_any_venue():
    service = CalendarFeedService(AsyncMock())
    service.venue_repository.get_by_id = AsyncMock(return_value=venue(owner_id=99))
    service.repository.list_for_venue = AsyncMock(return_value=[])

    assert await service.list(7, user(1, "admin")) == []


@pytest.mark.asyncio
async def test_revoking_missing_calendar_feed_returns_404():
    service = CalendarFeedService(AsyncMock())
    service.venue_repository.get_by_id = AsyncMock(return_value=venue())
    service.repository.get_for_venue = AsyncMock(return_value=None)

    with pytest.raises(HTTPException) as error:
        await service.revoke(7, 99, user())

    assert error.value.status_code == 404


@pytest.mark.asyncio
async def test_revoking_already_revoked_feed_is_idempotent():
    service = CalendarFeedService(AsyncMock())
    revoked_at = datetime.now(UTC)
    item = calendar_feed(revoked_at=revoked_at)
    service.venue_repository.get_by_id = AsyncMock(return_value=venue())
    service.repository.get_for_venue = AsyncMock(return_value=item)
    service.repository.save = AsyncMock()

    result = await service.revoke(7, 3, user())

    assert result.revoked_at == revoked_at
    service.repository.save.assert_not_awaited()


@pytest.mark.asyncio
async def test_empty_calendar_is_valid_and_tracks_access():
    service = CalendarFeedService(AsyncMock())
    item = calendar_feed()
    service.repository.get_active_by_hash = AsyncMock(return_value=item)
    service.repository.get_calendar_entries = AsyncMock(return_value=[])
    service.repository.save = AsyncMock()

    content, _ = await service.render("secret")

    assert content.startswith("BEGIN:VCALENDAR\r\n")
    assert "BEGIN:VEVENT" not in content
    assert content.endswith("END:VCALENDAR\r\n")
    assert item.last_accessed_at is not None


def test_calendar_datetime_formatter_accepts_naive_datetime_as_utc():
    value = datetime(2026, 8, 21, 12, 30)

    assert CalendarFeedService._utc(value) == "20260821T123000Z"


def test_calendar_text_escaping_handles_slashes_delimiters_and_newlines():
    value = "A\\B; C, D\nSecond line"

    assert CalendarFeedService._escape(value) == "A\\\\B\\; C\\, D\\nSecond line"


@pytest.mark.asyncio
async def test_calendar_endpoint_returns_content_headers_for_changed_feed():
    db = AsyncMock()
    with patch.object(
        CalendarFeedService,
        "render",
        new=AsyncMock(return_value=("BEGIN:VCALENDAR\r\n", '"etag"')),
    ):
        response = await get_calendar_feed("token", None, db)

    assert response.status_code == 200
    assert response.headers["etag"] == '"etag"'
    assert response.headers["content-disposition"] == 'inline; filename="bookings.ics"'
    assert response.media_type == "text/calendar; charset=utf-8"


@pytest.mark.asyncio
async def test_maintenance_returns_404_for_missing_venue():
    service = MaintenanceService(AsyncMock())
    service.venue_repository.get_by_id = AsyncMock(return_value=None)

    with pytest.raises(HTTPException) as error:
        await service.list(404, user())

    assert error.value.status_code == 404


@pytest.mark.asyncio
async def test_admin_can_manage_maintenance_for_any_venue():
    service = MaintenanceService(AsyncMock())
    service.venue_repository.get_by_id = AsyncMock(return_value=venue(owner_id=99))
    service.repository.list_for_venue = AsyncMock(return_value=[])

    assert await service.list(7, user(1, "admin")) == []


@pytest.mark.asyncio
async def test_missing_work_order_returns_404_after_authorization():
    service = MaintenanceService(AsyncMock())
    service.venue_repository.get_by_id = AsyncMock(return_value=venue())
    service.repository.get_for_venue = AsyncMock(return_value=None)

    with pytest.raises(HTTPException) as error:
        await service.get(7, 999, user())

    assert error.value.status_code == 404


@pytest.mark.asyncio
async def test_same_work_order_status_is_conflict():
    service = MaintenanceService(AsyncMock())
    service.venue_repository.get_by_id = AsyncMock(return_value=venue())
    service.repository.get_for_venue = AsyncMock(return_value=work_order(status="open"))

    with pytest.raises(HTTPException) as error:
        await service.transition(7, 4, WorkOrderTransition(status="open"), user())

    assert error.value.status_code == 409


@pytest.mark.asyncio
async def test_work_order_can_be_unassigned_and_audited():
    service = MaintenanceService(AsyncMock())
    item = work_order(assigned_to_id=20)
    service.venue_repository.get_by_id = AsyncMock(return_value=venue())
    service.repository.get_for_venue = AsyncMock(return_value=item)
    service.repository.save = AsyncMock(side_effect=lambda value, activity: value)

    result = await service.assign(
        7, 4, WorkOrderAssignment(assigned_to_id=None), user()
    )

    assert result.assigned_to_id is None
    activity = service.repository.save.await_args.args[1]
    assert activity.details == {
        "previous_assignee_id": 20,
        "assigned_to_id": None,
    }


@pytest.mark.asyncio
async def test_explicitly_clearing_due_date_is_recorded_as_update():
    service = MaintenanceService(AsyncMock())
    due_at = datetime.now(UTC)
    item = work_order(due_at=due_at)
    service.venue_repository.get_by_id = AsyncMock(return_value=venue())
    service.repository.get_for_venue = AsyncMock(return_value=item)
    service.repository.save = AsyncMock(side_effect=lambda value, activity: value)

    result = await service.update(7, 4, WorkOrderUpdate(due_at=None), user())

    assert result.due_at is None
    activity = service.repository.save.await_args.args[1]
    assert activity.details["before"]["due_at"] == due_at
    assert activity.details["after"]["due_at"] is None


@pytest.mark.asyncio
async def test_unauthorized_user_cannot_comment_on_maintenance():
    service = MaintenanceService(AsyncMock())
    service.venue_repository.get_by_id = AsyncMock(return_value=venue())
    service.staff_repository.has_role = AsyncMock(return_value=False)

    with pytest.raises(HTTPException) as error:
        await service.comment(
            7, 4, WorkOrderComment(message="Not allowed"), user(99, "customer")
        )

    assert error.value.status_code == 403


@pytest.mark.asyncio
async def test_activity_history_checks_work_order_and_returns_timeline():
    service = MaintenanceService(AsyncMock())
    service.venue_repository.get_by_id = AsyncMock(return_value=venue())
    service.repository.get_for_venue = AsyncMock(return_value=work_order())
    service.repository.list_activity = AsyncMock(return_value=[MagicMock(id=1)])

    result = await service.activity(7, 4, user())

    assert len(result) == 1
    service.repository.list_activity.assert_awaited_once_with(4)


@pytest.mark.asyncio
async def test_venue_staff_service_returns_404_for_missing_venue():
    service = VenueStaffService(AsyncMock())
    service.venue_repository.get_by_id = AsyncMock(return_value=None)

    with pytest.raises(HTTPException) as error:
        await service.list_for_venue(404, user())

    assert error.value.status_code == 404


@pytest.mark.asyncio
async def test_owner_lists_active_venue_staff():
    service = VenueStaffService(AsyncMock())
    service.venue_repository.get_by_id = AsyncMock(return_value=venue())
    service.repository.list_active_for_venue = AsyncMock(return_value=[MagicMock(id=2)])

    result = await service.list_for_venue(7, user())

    assert len(result) == 1


@pytest.mark.asyncio
async def test_updating_missing_staff_assignment_returns_404():
    service = VenueStaffService(AsyncMock())
    service.venue_repository.get_by_id = AsyncMock(return_value=venue())
    service.repository.get_active_by_id = AsyncMock(return_value=None)

    with pytest.raises(HTTPException) as error:
        await service.update_role(7, 999, VenueStaffUpdate(role="manager"), user())

    assert error.value.status_code == 404


@pytest.mark.asyncio
async def test_webhook_event_fanout_persists_matching_delivery_payload():
    db = AsyncMock()
    db.add = MagicMock()
    result = MagicMock()
    result.scalars.return_value.all.return_value = [
        webhook(id=12, event_types=["cancelled"])
    ]
    db.execute.return_value = result
    event = MagicMock(
        id=30,
        reservation_id=40,
        event_type="cancelled",
        occurred_at=datetime(2026, 8, 21, 12, tzinfo=UTC),
        previous_status="confirmed",
        new_status="cancelled",
        actor_role="customer",
        details={"refund_percentage": 100},
    )

    count = await WebhookRepository(db).enqueue_for_event(event)

    assert count == 1
    delivery = db.add.call_args.args[0]
    assert delivery.subscription_id == 12
    assert delivery.payload["type"] == "reservation.cancelled"
    assert delivery.payload["data"]["details"]["refund_percentage"] == 100
    db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_webhook_event_fanout_commits_event_when_no_feed_matches():
    db = AsyncMock()
    db.add = MagicMock()
    result = MagicMock()
    result.scalars.return_value.all.return_value = []
    db.execute.return_value = result

    count = await WebhookRepository(db).enqueue_for_event(
        MagicMock(event_type="created")
    )

    assert count == 0
    db.add.assert_not_called()
    db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_reservation_event_repository_flushes_before_webhook_fanout():
    db = AsyncMock()
    event = ReservationEvent(
        reservation_id=40,
        event_type="created",
        actor_role="customer",
        new_status="pending",
        details={},
    )
    with patch(
        "app.repositories.reservation_event_repository.WebhookRepository"
    ) as webhook_repository:
        webhook_repository.return_value.enqueue_for_event = AsyncMock()
        result = await ReservationEventRepository(db).create(event)

    assert result is event
    db.flush.assert_awaited_once()
    db.refresh.assert_awaited_once_with(event)
    webhook_repository.return_value.enqueue_for_event.assert_awaited_once_with(event)


@pytest.mark.asyncio
async def test_maintenance_repository_creates_order_and_activity_atomically():
    db = AsyncMock()
    db.add = MagicMock()
    order = MaintenanceWorkOrder(
        venue_id=7,
        title="Broken light",
        description="Fixture failed",
        priority="high",
        status="open",
    )
    activity = MaintenanceActivity(
        activity_type="created",
        details={},
    )

    result = await MaintenanceRepository(db).create(order, activity)

    assert result is order
    assert db.add.call_args_list[0].args[0] is order
    assert db.add.call_args_list[1].args[0] is activity
    db.flush.assert_awaited_once()
    db.commit.assert_awaited_once()
    db.refresh.assert_awaited_once_with(order)
