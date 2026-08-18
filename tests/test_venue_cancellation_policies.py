from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from app.models.reservation import Reservation
from app.schemas.reservation import ReservationCreate
from app.schemas.venue import VenueCancellationPolicyUpdate
from app.services.reservation_service import ReservationService
from app.services.venue_service import VenueService


@pytest.mark.asyncio
async def test_owner_can_update_own_venue_cancellation_policy():
    service = VenueService(AsyncMock())
    venue = MagicMock(
        id=5,
        owner_id=10,
        free_cancellation_hours=24,
        late_cancellation_refund_percent=50,
    )
    service.venue_repository.get_by_id = AsyncMock(return_value=venue)
    service.venue_repository.update = AsyncMock(return_value=venue)

    result = await service.update_cancellation_policy(
        venue_id=venue.id,
        data=VenueCancellationPolicyUpdate(
            free_cancellation_hours=48,
            late_cancellation_refund_percent=25,
        ),
        current_user=MagicMock(id=venue.owner_id, role="owner"),
    )

    assert result.free_cancellation_hours == 48
    assert result.late_cancellation_refund_percent == 25
    service.venue_repository.update.assert_awaited_once_with(venue)


@pytest.mark.asyncio
async def test_owner_cannot_update_another_owners_policy():
    service = VenueService(AsyncMock())
    service.venue_repository.get_by_id = AsyncMock(
        return_value=MagicMock(id=5, owner_id=10)
    )

    with pytest.raises(HTTPException) as exception_info:
        await service.update_cancellation_policy(
            venue_id=5,
            data=VenueCancellationPolicyUpdate(
                free_cancellation_hours=48,
                late_cancellation_refund_percent=25,
            ),
            current_user=MagicMock(id=99, role="owner"),
        )

    assert exception_info.value.status_code == 403


def test_policy_rejects_invalid_refund_percentage():
    with pytest.raises(ValidationError):
        VenueCancellationPolicyUpdate(
            free_cancellation_hours=24,
            late_cancellation_refund_percent=101,
        )


def test_reservation_uses_snapshotted_policy_for_late_cancellation():
    service = ReservationService(MagicMock())
    current_time = datetime(2026, 8, 13, 12, tzinfo=UTC)
    reservation = Reservation(
        start_time=current_time + timedelta(hours=47),
        end_time=current_time + timedelta(hours=48),
        cancellation_free_hours=48,
        cancellation_late_refund_percent=25,
    )

    refund_percentage = service._get_refund_percentage(reservation, current_time)

    assert refund_percentage == 25


@pytest.mark.asyncio
@patch(
    "app.services.reservation_service.delete_available_slots_cache_for_resource",
    new_callable=AsyncMock,
)
async def test_new_reservation_snapshots_current_venue_policy(_delete_cache):
    service = ReservationService(AsyncMock())
    start_time = datetime.now(UTC) + timedelta(days=3)
    data = ReservationCreate(
        resource_id=20,
        start_time=start_time,
        end_time=start_time + timedelta(hours=1),
    )
    service.resource_repository.get_by_id = AsyncMock(
        return_value=MagicMock(
            id=20,
            venue_id=5,
            hourly_rate_cents=2000,
            currency="EUR",
            capacity=10,
        )
    )
    service._resolve_promotion = AsyncMock(return_value=None)
    service._get_cancellation_policy = AsyncMock(return_value=(48, 25))
    service._validate_booking_rules = AsyncMock()
    service._is_within_availability_rules = AsyncMock(return_value=True)
    service._has_availability_exception = AsyncMock(return_value=False)
    service.reservation_repository.has_conflicting_reservation = AsyncMock(
        return_value=False
    )

    async def create(reservation, promotion_redemptions):
        reservation.id = 1
        return reservation

    service.reservation_repository.create_with_conflict_lock = AsyncMock(
        side_effect=create
    )
    service.reservation_event_repository.create = AsyncMock(
        side_effect=lambda event: event
    )
    service.notification_service.create_notification = AsyncMock()

    reservation = await service.create_reservation(
        data,
        MagicMock(id=10, role="customer", email="user@example.com"),
    )

    assert reservation.cancellation_free_hours == 48
    assert reservation.cancellation_late_refund_percent == 25
