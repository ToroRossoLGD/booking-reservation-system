from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from app.api.routers.notifications import (
    dismiss_notification,
    dismiss_read_notifications,
    get_unread_notification_count,
    mark_all_notifications_as_read,
    mark_notification_as_read,
)


@pytest.mark.asyncio
async def test_unread_count_is_scoped_to_current_user():
    user = SimpleNamespace(id=17)
    with patch(
        "app.api.routers.notifications.NotificationService.get_unread_count",
        new=AsyncMock(return_value=4),
    ) as get_unread_count:
        result = await get_unread_notification_count(AsyncMock(), user)

    assert result.unread_count == 4
    get_unread_count.assert_awaited_once_with(17)


@pytest.mark.asyncio
async def test_mark_notification_read_is_scoped_to_current_user():
    user = SimpleNamespace(id=17)
    notification = SimpleNamespace(
        id=23,
        user_id=17,
        title="Booking confirmed",
        message="Your reservation is ready.",
        is_read=True,
        created_at=datetime.now(UTC),
    )
    with patch(
        "app.api.routers.notifications.NotificationService.mark_notification_as_read",
        new=AsyncMock(return_value=notification),
    ) as mark_read:
        result = await mark_notification_as_read(23, AsyncMock(), user)

    assert result is notification
    mark_read.assert_awaited_once_with(notification_id=23, user_id=17)


@pytest.mark.asyncio
async def test_mark_all_notifications_read_is_scoped_to_current_user():
    user = SimpleNamespace(id=17)
    with patch(
        "app.api.routers.notifications.NotificationService.mark_all_notifications_as_read",
        new=AsyncMock(),
    ) as mark_all_read:
        response = await mark_all_notifications_as_read(AsyncMock(), user)

    assert response.status_code == 204
    mark_all_read.assert_awaited_once_with(17)


@pytest.mark.asyncio
async def test_dismiss_notification_is_scoped_to_current_user():
    user = SimpleNamespace(id=17)
    with patch(
        "app.api.routers.notifications.NotificationService.dismiss_notification",
        new=AsyncMock(),
    ) as dismiss:
        response = await dismiss_notification(23, AsyncMock(), user)

    assert response.status_code == 204
    dismiss.assert_awaited_once_with(notification_id=23, user_id=17)


@pytest.mark.asyncio
async def test_dismiss_read_notifications_returns_user_scoped_count():
    user = SimpleNamespace(id=17)
    with patch(
        "app.api.routers.notifications.NotificationService.dismiss_read_notifications",
        new=AsyncMock(return_value=3),
    ) as dismiss_read:
        result = await dismiss_read_notifications(AsyncMock(), user)

    assert result.dismissed_count == 3
    dismiss_read.assert_awaited_once_with(17)
