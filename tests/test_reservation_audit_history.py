from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.reservation import Reservation, ReservationStatus
from app.models.reservation_event import ReservationEventType
from app.schemas.reservation import ReservationReschedule
from app.services.reservation_service import ReservationService


@pytest.mark.asyncio
@patch(
    "app.services.reservation_service.delete_available_slots_cache_for_resource",
    new_callable=AsyncMock,
)
async def test_reschedule_records_before_and_after_times(_delete_cache):
    service = ReservationService(AsyncMock())
    old_start = datetime.now(UTC) + timedelta(days=2)
    new_start = old_start + timedelta(hours=2)
    reservation = Reservation(
        id=1,
        user_id=10,
        resource_id=20,
        start_time=old_start,
        end_time=old_start + timedelta(hours=1),
        status=ReservationStatus.CONFIRMED.value,
    )
    current_user = MagicMock(id=10, role="customer")
    service.reservation_repository.get_by_id = AsyncMock(return_value=reservation)
    service.resource_repository.get_by_id = AsyncMock(
        return_value=MagicMock(hourly_rate_cents=2000, currency="EUR")
    )
    service._is_within_availability_rules = AsyncMock(return_value=True)
    service._has_availability_exception = AsyncMock(return_value=False)
    service._validate_booking_rules = AsyncMock()

    async def reschedule(reservation, start_time, end_time):
        reservation.start_time = start_time
        reservation.end_time = end_time
        return reservation

    service.reservation_repository.reschedule_with_conflict_lock = AsyncMock(
        side_effect=reschedule
    )
    service.reservation_event_repository.create = AsyncMock(
        side_effect=lambda event: event
    )
    service.notification_service.create_notification = AsyncMock()
    service.waitlist_service.notify_next_for_slot = AsyncMock()

    await service.reschedule_reservation(
        reservation_id=1,
        data=ReservationReschedule(
            start_time=new_start,
            end_time=new_start + timedelta(hours=1),
        ),
        current_user=current_user,
    )

    event = service.reservation_event_repository.create.await_args.args[0]
    assert event.event_type == ReservationEventType.RESCHEDULED.value
    assert event.actor_id == current_user.id
    assert event.previous_status == ReservationStatus.CONFIRMED.value
    assert event.new_status == ReservationStatus.CONFIRMED.value
    assert event.details == {
        "previous_start_time": old_start.isoformat(),
        "previous_end_time": (old_start + timedelta(hours=1)).isoformat(),
        "new_start_time": new_start.isoformat(),
        "new_end_time": (new_start + timedelta(hours=1)).isoformat(),
    }


@pytest.mark.asyncio
async def test_timeline_uses_existing_reservation_access_control():
    service = ReservationService(AsyncMock())
    reservation = MagicMock(id=7)
    events = [MagicMock(reservation_id=reservation.id)]
    service.get_reservation = AsyncMock(return_value=reservation)
    service.reservation_event_repository.get_for_reservation = AsyncMock(
        return_value=events
    )
    current_user = MagicMock(id=10, role="customer")

    result = await service.get_reservation_timeline(7, current_user)

    service.get_reservation.assert_awaited_once_with(7, current_user)
    assert result == {"reservation_id": 7, "events": events}


@pytest.mark.asyncio
@patch(
    "app.services.reservation_service.delete_available_slots_cache_for_resource",
    new_callable=AsyncMock,
)
async def test_expiry_event_is_attributed_to_system(_delete_cache):
    service = ReservationService(AsyncMock())
    reservation = MagicMock(
        id=3,
        resource_id=20,
        status=ReservationStatus.PENDING.value,
    )
    service.reservation_repository.get_expired_pending_reservations = AsyncMock(
        return_value=[reservation]
    )
    service.reservation_repository.update = AsyncMock(return_value=reservation)
    service.reservation_event_repository.create = AsyncMock(
        side_effect=lambda event: event
    )

    result = await service.expire_pending_reservations()

    event = service.reservation_event_repository.create.await_args.args[0]
    assert result == {"expired_count": 1}
    assert event.event_type == ReservationEventType.EXPIRED.value
    assert event.actor_id is None
    assert event.actor_role == "system"
    assert event.previous_status == ReservationStatus.PENDING.value
    assert event.new_status == ReservationStatus.EXPIRED.value
