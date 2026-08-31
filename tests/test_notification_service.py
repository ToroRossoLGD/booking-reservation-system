from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException

from app.models.notification import Notification
from app.services.notification_service import NotificationService


def notification_service() -> NotificationService:
    service = NotificationService(AsyncMock())
    service.notification_repository = MagicMock()
    service.email_service = MagicMock()
    return service


@pytest.mark.asyncio
async def test_create_notification_persists_without_deduplication():
    service = notification_service()
    service.notification_repository.create = AsyncMock(side_effect=lambda item: item)

    result = await service.create_notification(7, "Confirmed", "Your booking is set")

    assert isinstance(result, Notification)
    assert result.user_id == 7
    assert result.title == "Confirmed"
    assert result.message == "Your booking is set"
    assert result.deduplication_key is None
    service.notification_repository.create_once.assert_not_called()
    service.email_service.send_email.assert_not_called()


@pytest.mark.asyncio
async def test_create_notification_uses_deduplicated_persistence():
    service = notification_service()
    created = SimpleNamespace(id=12)
    service.notification_repository.create_once = AsyncMock(return_value=created)

    result = await service.create_notification(
        7,
        "Reminder",
        "Your booking starts soon",
        deduplication_key="reservation:42:reminder:2h",
    )

    assert result is created
    persisted = service.notification_repository.create_once.await_args.args[0]
    assert persisted.deduplication_key == "reservation:42:reminder:2h"
    service.notification_repository.create.assert_not_called()


@pytest.mark.asyncio
async def test_create_notification_sends_email_immediately_without_background_tasks():
    service = notification_service()
    created = SimpleNamespace(id=12)
    service.notification_repository.create = AsyncMock(return_value=created)

    result = await service.create_notification(
        7,
        "Confirmed",
        "Your booking is set",
        user_email="guest@example.com",
    )

    assert result is created
    service.email_service.send_email.assert_called_once_with(
        to_email="guest@example.com",
        subject="Confirmed",
        body="Your booking is set",
    )


@pytest.mark.asyncio
async def test_create_notification_queues_email_when_background_tasks_are_available():
    service = notification_service()
    service.notification_repository.create = AsyncMock(
        return_value=SimpleNamespace(id=12)
    )
    background_tasks = MagicMock()

    await service.create_notification(
        7,
        "Confirmed",
        "Your booking is set",
        user_email="guest@example.com",
        background_tasks=background_tasks,
    )

    background_tasks.add_task.assert_called_once_with(
        service.email_service.send_email,
        "guest@example.com",
        "Confirmed",
        "Your booking is set",
    )
    service.email_service.send_email.assert_not_called()


@pytest.mark.asyncio
async def test_mark_notification_as_read_rejects_unknown_or_unowned_notification():
    service = notification_service()
    service.notification_repository.get_by_id_for_user = AsyncMock(return_value=None)

    with pytest.raises(HTTPException) as error:
        await service.mark_notification_as_read(notification_id=99, user_id=7)

    assert error.value.status_code == 404
    assert error.value.detail == "Notification not found"
    service.notification_repository.mark_as_read.assert_not_called()


@pytest.mark.asyncio
async def test_mark_notification_as_read_updates_unread_notification():
    service = notification_service()
    notification = SimpleNamespace(id=12, is_read=False)
    updated = SimpleNamespace(id=12, is_read=True)
    service.notification_repository.get_by_id_for_user = AsyncMock(
        return_value=notification
    )
    service.notification_repository.mark_as_read = AsyncMock(return_value=updated)

    result = await service.mark_notification_as_read(notification_id=12, user_id=7)

    assert result is updated
    service.notification_repository.mark_as_read.assert_awaited_once_with(notification)


@pytest.mark.asyncio
async def test_bulk_read_and_unread_count_delegate_with_user_scope():
    service = notification_service()
    service.notification_repository.mark_all_as_read = AsyncMock()
    service.notification_repository.count_unread = AsyncMock(return_value=3)

    await service.mark_all_notifications_as_read(user_id=7)
    result = await service.get_unread_count(user_id=7)

    assert result == 3
    service.notification_repository.mark_all_as_read.assert_awaited_once_with(7)
    service.notification_repository.count_unread.assert_awaited_once_with(7)


@pytest.mark.asyncio
async def test_dismiss_notification_rejects_unknown_or_unowned_notification():
    service = notification_service()
    service.notification_repository.get_by_id_for_user = AsyncMock(return_value=None)

    with pytest.raises(HTTPException) as error:
        await service.dismiss_notification(notification_id=99, user_id=7)

    assert error.value.status_code == 404
    assert error.value.detail == "Notification not found"
    service.notification_repository.delete.assert_not_called()


@pytest.mark.asyncio
async def test_dismiss_notification_deletes_owned_notification():
    service = notification_service()
    notification = SimpleNamespace(id=12, user_id=7)
    service.notification_repository.get_by_id_for_user = AsyncMock(
        return_value=notification
    )
    service.notification_repository.delete = AsyncMock()

    await service.dismiss_notification(notification_id=12, user_id=7)

    service.notification_repository.delete.assert_awaited_once_with(notification)


@pytest.mark.asyncio
async def test_dismiss_read_notifications_delegates_with_user_scope():
    service = notification_service()
    service.notification_repository.delete_read_by_user_id = AsyncMock(return_value=4)

    result = await service.dismiss_read_notifications(user_id=7)

    assert result == 4
    service.notification_repository.delete_read_by_user_id.assert_awaited_once_with(7)
