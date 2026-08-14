from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException

from app.models.waitlist_entry import WaitlistEntry, WaitlistStatus
from app.schemas.waitlist import WaitlistEntryCreate
from app.services.waitlist_service import WaitlistService


def waitlist_data() -> WaitlistEntryCreate:
    start_time = datetime.now(UTC) + timedelta(days=2)
    return WaitlistEntryCreate(
        resource_id=20,
        start_time=start_time,
        end_time=start_time + timedelta(hours=1),
    )


@pytest.mark.asyncio
async def test_user_can_join_waitlist_for_booked_slot():
    service = WaitlistService(AsyncMock())
    data = waitlist_data()
    user = MagicMock(id=10)
    conflict = MagicMock(user_id=99)
    created_entry = WaitlistEntry(id=1, user_id=user.id, **data.model_dump())

    service.resource_repository.get_by_id = AsyncMock(return_value=MagicMock())
    service.reservation_repository.get_conflicting_reservation = AsyncMock(
        return_value=conflict
    )
    service.waitlist_repository.get_waiting_entry = AsyncMock(return_value=None)
    service.waitlist_repository.create = AsyncMock(return_value=created_entry)

    result = await service.join_waitlist(data, user)

    assert result is created_entry
    service.waitlist_repository.create.assert_awaited_once()


@pytest.mark.asyncio
async def test_user_cannot_join_waitlist_for_available_slot():
    service = WaitlistService(AsyncMock())
    data = waitlist_data()
    user = MagicMock(id=10)
    service.resource_repository.get_by_id = AsyncMock(return_value=MagicMock())
    service.reservation_repository.get_conflicting_reservation = AsyncMock(
        return_value=None
    )

    with pytest.raises(HTTPException) as exception_info:
        await service.join_waitlist(data, user)

    assert exception_info.value.status_code == 400
    assert "does not require a waitlist" in exception_info.value.detail


@pytest.mark.asyncio
async def test_user_cannot_join_same_waitlist_twice():
    service = WaitlistService(AsyncMock())
    data = waitlist_data()
    user = MagicMock(id=10)
    service.resource_repository.get_by_id = AsyncMock(return_value=MagicMock())
    service.reservation_repository.get_conflicting_reservation = AsyncMock(
        return_value=MagicMock(user_id=99)
    )
    service.waitlist_repository.get_waiting_entry = AsyncMock(return_value=MagicMock())

    with pytest.raises(HTTPException) as exception_info:
        await service.join_waitlist(data, user)

    assert exception_info.value.status_code == 409


@pytest.mark.asyncio
async def test_next_waiting_user_is_notified_when_slot_opens():
    service = WaitlistService(AsyncMock())
    data = waitlist_data()
    entry = WaitlistEntry(
        id=1,
        user_id=10,
        status=WaitlistStatus.WAITING.value,
        **data.model_dump(),
    )
    notified_entry = MagicMock(
        id=entry.id,
        user_id=entry.user_id,
        status=WaitlistStatus.NOTIFIED.value,
    )
    service.waitlist_repository.get_next_waiting_for_slot = AsyncMock(
        return_value=entry
    )
    service.waitlist_repository.mark_notified = AsyncMock(return_value=notified_entry)
    service.notification_service.create_notification = AsyncMock()

    result = await service.notify_next_for_slot(
        resource_id=data.resource_id,
        start_time=data.start_time,
        end_time=data.end_time,
    )

    assert result is notified_entry
    service.waitlist_repository.mark_notified.assert_awaited_once_with(entry)
    service.notification_service.create_notification.assert_awaited_once()
