from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from app.core.config import settings
from app.models.payment import Payment, PaymentStatus
from app.models.reservation import Reservation, ReservationStatus
from app.schemas.reservation import ReservationReschedule
from app.services.reservation_service import ReservationService


def test_refund_is_full_before_free_cancellation_deadline():
    service = ReservationService(MagicMock())
    current_time = datetime(2026, 8, 13, 12, tzinfo=UTC)
    reservation = Reservation(
        start_time=current_time + timedelta(hours=settings.FREE_CANCELLATION_HOURS),
        end_time=current_time + timedelta(hours=settings.FREE_CANCELLATION_HOURS + 1),
    )

    refund_percentage = service._get_refund_percentage(
        reservation=reservation,
        current_time=current_time,
    )

    assert refund_percentage == 100


def test_refund_is_reduced_after_free_cancellation_deadline():
    service = ReservationService(MagicMock())
    current_time = datetime(2026, 8, 13, 12, tzinfo=UTC)
    reservation = Reservation(
        start_time=current_time + timedelta(hours=settings.FREE_CANCELLATION_HOURS - 1),
        end_time=current_time + timedelta(hours=settings.FREE_CANCELLATION_HOURS),
    )

    refund_percentage = service._get_refund_percentage(
        reservation=reservation,
        current_time=current_time,
    )

    assert refund_percentage == settings.LATE_CANCELLATION_REFUND_PERCENT


def test_refund_is_rejected_after_reservation_starts():
    service = ReservationService(MagicMock())
    current_time = datetime(2026, 8, 13, 12, tzinfo=UTC)
    reservation = Reservation(
        start_time=current_time - timedelta(minutes=1),
        end_time=current_time + timedelta(hours=1),
    )

    with pytest.raises(HTTPException) as exception_info:
        service._get_refund_percentage(
            reservation=reservation,
            current_time=current_time,
        )

    assert exception_info.value.status_code == 400
    assert exception_info.value.detail == (
        "A reservation cannot be cancelled after its start time"
    )


@pytest.mark.asyncio
async def test_cancelling_paid_reservation_updates_both_states():
    db = AsyncMock()
    service = ReservationService(db)
    start_time = datetime.now(UTC) + timedelta(
        hours=settings.FREE_CANCELLATION_HOURS + 1
    )
    reservation = Reservation(
        id=1,
        user_id=10,
        resource_id=20,
        start_time=start_time,
        end_time=start_time + timedelta(hours=1),
        status=ReservationStatus.CONFIRMED.value,
    )
    payment = Payment(
        reservation_id=reservation.id,
        amount_cents=10_000,
        currency="EUR",
        status=PaymentStatus.PAID.value,
    )
    current_user = MagicMock(
        id=reservation.user_id, role="user", email="user@example.com"
    )

    service.reservation_repository.get_by_id = AsyncMock(return_value=reservation)
    service.payment_repository.get_by_reservation_id = AsyncMock(return_value=payment)
    service.notification_service.create_notification = AsyncMock()
    service.waitlist_service.notify_next_for_slot = AsyncMock(return_value=None)

    with patch(
        "app.services.reservation_service.delete_available_slots_cache_for_resource",
        new_callable=AsyncMock,
    ):
        result = await service.cancel_reservation(
            reservation_id=reservation.id,
            current_user=current_user,
        )

    assert reservation.status == ReservationStatus.CANCELLED.value
    assert payment.status == PaymentStatus.REFUNDED.value
    assert payment.refunded_amount_cents == payment.amount_cents
    assert result["refund_percentage"] == 100
    db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_user_can_reschedule_own_pending_reservation():
    service = ReservationService(AsyncMock())
    start_time = datetime.now(UTC) + timedelta(days=2)
    new_start_time = start_time + timedelta(hours=2)
    reservation = Reservation(
        id=1,
        user_id=10,
        resource_id=20,
        start_time=start_time,
        end_time=start_time + timedelta(hours=1),
        status=ReservationStatus.PENDING.value,
    )
    current_user = MagicMock(id=reservation.user_id, role="customer")
    data = ReservationReschedule(
        start_time=new_start_time,
        end_time=new_start_time + timedelta(hours=1),
    )

    service.reservation_repository.get_by_id = AsyncMock(return_value=reservation)
    service._is_within_availability_rules = AsyncMock(return_value=True)
    service._has_availability_exception = AsyncMock(return_value=False)
    service.reservation_repository.reschedule_with_conflict_lock = AsyncMock(
        return_value=reservation
    )
    service.notification_service.create_notification = AsyncMock()
    service.waitlist_service.notify_next_for_slot = AsyncMock(return_value=None)

    with patch(
        "app.services.reservation_service.delete_available_slots_cache_for_resource",
        new_callable=AsyncMock,
    ) as delete_cache:
        result = await service.reschedule_reservation(
            reservation_id=reservation.id,
            data=data,
            current_user=current_user,
        )

    assert result is reservation
    service.reservation_repository.reschedule_with_conflict_lock.assert_awaited_once()
    service.notification_service.create_notification.assert_awaited_once()
    delete_cache.assert_awaited_once_with(reservation.resource_id)


@pytest.mark.asyncio
async def test_user_cannot_reschedule_another_users_reservation():
    service = ReservationService(AsyncMock())
    reservation = MagicMock(id=1, user_id=10)
    current_user = MagicMock(id=99, role="customer")
    service.reservation_repository.get_by_id = AsyncMock(return_value=reservation)

    with pytest.raises(HTTPException) as exception_info:
        await service.reschedule_reservation(
            reservation_id=reservation.id,
            data=MagicMock(),
            current_user=current_user,
        )

    assert exception_info.value.status_code == 403


@pytest.mark.asyncio
async def test_cancelled_reservation_cannot_be_rescheduled():
    service = ReservationService(AsyncMock())
    reservation = MagicMock(
        id=1,
        user_id=10,
        status=ReservationStatus.CANCELLED.value,
    )
    current_user = MagicMock(id=reservation.user_id, role="customer")
    service.reservation_repository.get_by_id = AsyncMock(return_value=reservation)

    with pytest.raises(HTTPException) as exception_info:
        await service.reschedule_reservation(
            reservation_id=reservation.id,
            data=MagicMock(),
            current_user=current_user,
        )

    assert exception_info.value.status_code == 400


@pytest.mark.asyncio
async def test_reschedule_rejects_conflicting_time_slot():
    service = ReservationService(AsyncMock())
    start_time = datetime.now(UTC) + timedelta(days=2)
    reservation = Reservation(
        id=1,
        user_id=10,
        resource_id=20,
        start_time=start_time,
        end_time=start_time + timedelta(hours=1),
        status=ReservationStatus.CONFIRMED.value,
    )
    current_user = MagicMock(id=reservation.user_id, role="customer")
    data = ReservationReschedule(
        start_time=start_time + timedelta(hours=2),
        end_time=start_time + timedelta(hours=3),
    )

    service.reservation_repository.get_by_id = AsyncMock(return_value=reservation)
    service._is_within_availability_rules = AsyncMock(return_value=True)
    service._has_availability_exception = AsyncMock(return_value=False)
    service.reservation_repository.reschedule_with_conflict_lock = AsyncMock(
        return_value=None
    )

    with pytest.raises(HTTPException) as exception_info:
        await service.reschedule_reservation(
            reservation_id=reservation.id,
            data=data,
            current_user=current_user,
        )

    assert exception_info.value.status_code == 409
