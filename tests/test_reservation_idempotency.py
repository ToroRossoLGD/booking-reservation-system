from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from app.models.reservation import Reservation
from app.repositories.reservation_repository import (
    IdempotencyKeyConflict,
    ReservationRepository,
)
from app.schemas.reservation import ReservationCreate
from app.services.reservation_service import ReservationService


def reservation_data() -> ReservationCreate:
    start_time = datetime.now(UTC) + timedelta(days=2)
    return ReservationCreate(
        resource_id=20,
        start_time=start_time,
        end_time=start_time + timedelta(hours=1),
    )


@pytest.mark.asyncio
async def test_matching_idempotent_retry_returns_original_reservation():
    service = ReservationService(AsyncMock())
    data = reservation_data()
    request_hash = service._idempotency_request_hash(data)
    existing = Reservation(
        id=7,
        user_id=10,
        resource_id=data.resource_id,
        start_time=data.start_time,
        end_time=data.end_time,
        idempotency_key="booking-request-123",
        idempotency_request_hash=request_hash,
    )
    service.reservation_repository.get_by_idempotency_key = AsyncMock(
        return_value=existing
    )
    service.resource_repository.get_by_id = AsyncMock()

    result = await service.create_reservation(
        data,
        MagicMock(id=10),
        idempotency_key="booking-request-123",
    )

    assert result is existing
    service.resource_repository.get_by_id.assert_not_awaited()


@pytest.mark.asyncio
async def test_reusing_key_for_different_payload_is_rejected():
    service = ReservationService(AsyncMock())
    data = reservation_data()
    existing = MagicMock(idempotency_request_hash="different-hash")
    service.reservation_repository.get_by_idempotency_key = AsyncMock(
        return_value=existing
    )

    with pytest.raises(HTTPException) as exception_info:
        await service.create_reservation(
            data,
            MagicMock(id=10),
            idempotency_key="booking-request-123",
        )

    assert exception_info.value.status_code == 409
    assert "different request" in exception_info.value.detail


@pytest.mark.asyncio
@patch(
    "app.services.reservation_service.delete_available_slots_cache_for_resource",
    new_callable=AsyncMock,
)
async def test_idempotency_lookup_is_scoped_to_authenticated_user(_delete_cache):
    service = ReservationService(AsyncMock())
    service._get_cancellation_policy = AsyncMock(return_value=(24, 50))
    service._validate_booking_rules = AsyncMock()
    data = reservation_data()
    current_user = MagicMock(id=42, email="user@example.com")
    service.reservation_repository.get_by_idempotency_key = AsyncMock(return_value=None)
    service.resource_repository.get_by_id = AsyncMock(
        return_value=MagicMock(
            id=data.resource_id,
            venue_id=5,
            hourly_rate_cents=2000,
            currency="EUR",
        )
    )
    service._resolve_promotion = AsyncMock(return_value=None)
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
    service.notification_service.create_notification = AsyncMock()

    await service.create_reservation(
        data,
        current_user,
        idempotency_key="booking-request-123",
    )

    service.reservation_repository.get_by_idempotency_key.assert_awaited_once_with(
        current_user.id, "booking-request-123"
    )
    created = service.reservation_repository.create_with_conflict_lock.await_args.args[
        0
    ]
    assert created.user_id == current_user.id
    assert created.idempotency_key == "booking-request-123"
    assert created.idempotency_request_hash == service._idempotency_request_hash(data)


@pytest.mark.asyncio
async def test_concurrent_key_payload_conflict_becomes_http_conflict():
    service = ReservationService(AsyncMock())
    service._get_cancellation_policy = AsyncMock(return_value=(24, 50))
    service._validate_booking_rules = AsyncMock()
    data = reservation_data()
    service.reservation_repository.get_by_idempotency_key = AsyncMock(return_value=None)
    service.resource_repository.get_by_id = AsyncMock(
        return_value=MagicMock(
            venue_id=5,
            hourly_rate_cents=2000,
            currency="EUR",
        )
    )
    service._resolve_promotion = AsyncMock(return_value=None)
    service._is_within_availability_rules = AsyncMock(return_value=True)
    service._has_availability_exception = AsyncMock(return_value=False)
    service.reservation_repository.has_conflicting_reservation = AsyncMock(
        return_value=False
    )
    service.reservation_repository.create_with_conflict_lock = AsyncMock(
        side_effect=IdempotencyKeyConflict
    )

    with pytest.raises(HTTPException) as exception_info:
        await service.create_reservation(
            data,
            MagicMock(id=10),
            idempotency_key="booking-request-123",
        )

    assert exception_info.value.status_code == 409
    assert "different request" in exception_info.value.detail


@pytest.mark.asyncio
async def test_locked_concurrent_retry_returns_existing_reservation():
    db = AsyncMock()
    repository = ReservationRepository(db)
    attempted = MagicMock(
        user_id=10,
        resource_id=20,
        idempotency_key="booking-request-123",
        idempotency_request_hash="same-hash",
    )
    existing = MagicMock(id=7, idempotency_request_hash="same-hash")
    user_lock_result = MagicMock()
    existing_result = MagicMock()
    existing_result.scalar_one_or_none.return_value = existing
    db.execute = AsyncMock(side_effect=[user_lock_result, existing_result])

    result = await repository.create_with_conflict_lock(attempted)

    assert result is existing
    assert db.execute.await_count == 2
    db.rollback.assert_awaited_once()
    db.add.assert_not_called()
