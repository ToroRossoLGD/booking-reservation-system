from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.reservation import AttendanceStatus, ReservationStatus
from app.models.reservation_event import ReservationEventType
from app.services.notification_service import NotificationService
from app.services.reservation_reminder_service import ReservationReminderService


def reminder_candidate(now: datetime, starts_in_hours: int):
    reservation = MagicMock(
        id=42,
        user_id=10,
        start_time=now + timedelta(hours=starts_in_hours),
        status=ReservationStatus.CONFIRMED.value,
        attendance_status=AttendanceStatus.SCHEDULED.value,
    )
    user = MagicMock(id=10, email="customer@example.com")
    resource = MagicMock(id=20, name="Court 1")
    venue = MagicMock(id=30, name="City Sports Centre")
    return reservation, user, resource, venue


@pytest.mark.asyncio
async def test_first_reminder_is_sent_and_audited():
    now = datetime(2026, 8, 20, 12, tzinfo=UTC)
    candidate = reminder_candidate(now, starts_in_hours=20)
    service = ReservationReminderService(AsyncMock())
    service.reservation_repository.get_reminder_candidates = AsyncMock(
        return_value=[candidate]
    )
    service.notification_service.create_notification = AsyncMock(
        return_value=MagicMock(id=99)
    )
    service.reservation_event_repository.create = AsyncMock()

    result = await service.send_due_reminders(current_time=now)

    assert result == {
        "candidate_count": 1,
        "sent_count": 1,
        "duplicate_count": 0,
    }
    notification_call = service.notification_service.create_notification.await_args
    assert notification_call.kwargs["deduplication_key"] == (
        "reservation:42:reminder:24h"
    )
    assert "Court 1" in notification_call.kwargs["title"]
    assert "City Sports Centre" in notification_call.kwargs["message"]
    event = service.reservation_event_repository.create.await_args.args[0]
    assert event.event_type == ReservationEventType.REMINDER_SENT.value
    assert event.actor_role == "system"
    assert event.details == {"reminder_hours": 24, "notification_id": 99}


@pytest.mark.asyncio
async def test_final_reminder_uses_final_window_key():
    now = datetime(2026, 8, 20, 12, tzinfo=UTC)
    service = ReservationReminderService(AsyncMock())
    service.reservation_repository.get_reminder_candidates = AsyncMock(
        return_value=[reminder_candidate(now, starts_in_hours=1)]
    )
    service.notification_service.create_notification = AsyncMock(
        return_value=MagicMock(id=100)
    )
    service.reservation_event_repository.create = AsyncMock()

    await service.send_due_reminders(current_time=now)

    call = service.notification_service.create_notification.await_args
    assert call.kwargs["deduplication_key"] == "reservation:42:reminder:2h"
    event = service.reservation_event_repository.create.await_args.args[0]
    assert event.details["reminder_hours"] == 2


@pytest.mark.asyncio
async def test_duplicate_reminder_does_not_send_email_or_audit_again():
    now = datetime(2026, 8, 20, 12, tzinfo=UTC)
    service = ReservationReminderService(AsyncMock())
    service.reservation_repository.get_reminder_candidates = AsyncMock(
        return_value=[reminder_candidate(now, starts_in_hours=20)]
    )
    service.notification_service.create_notification = AsyncMock(return_value=None)
    service.reservation_event_repository.create = AsyncMock()

    result = await service.send_due_reminders(current_time=now)

    assert result["sent_count"] == 0
    assert result["duplicate_count"] == 1
    service.reservation_event_repository.create.assert_not_awaited()


@pytest.mark.asyncio
async def test_candidate_query_uses_configured_outer_window():
    now = datetime(2026, 8, 20, 12, tzinfo=UTC)
    service = ReservationReminderService(AsyncMock())
    service.reservation_repository.get_reminder_candidates = AsyncMock(return_value=[])

    with (
        patch(
            "app.services.reservation_reminder_service.settings."
            "RESERVATION_FIRST_REMINDER_HOURS",
            48,
        ),
        patch(
            "app.services.reservation_reminder_service.settings."
            "RESERVATION_FINAL_REMINDER_HOURS",
            3,
        ),
    ):
        await service.send_due_reminders(current_time=now)

    service.reservation_repository.get_reminder_candidates.assert_awaited_once_with(
        starts_after=now,
        final_window_ends=now + timedelta(hours=3),
        starts_before=now + timedelta(hours=48),
        first_reminder_hours=48,
        final_reminder_hours=3,
    )


@pytest.mark.asyncio
async def test_notification_deduplication_skips_second_delivery():
    service = NotificationService(AsyncMock())
    service.notification_repository.create_once = AsyncMock(return_value=None)
    service.email_service.send_email = MagicMock()

    result = await service.create_notification(
        user_id=10,
        title="Reminder",
        message="Starts soon",
        user_email="customer@example.com",
        deduplication_key="reservation:42:reminder:2h",
    )

    assert result is None
    service.email_service.send_email.assert_not_called()
