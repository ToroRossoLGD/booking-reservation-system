from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from app.core.config import settings
from app.models.payment import Payment, PaymentStatus
from app.models.reservation import Reservation, ReservationStatus
from app.schemas.reservation import (
    RecurringReservationCreate,
    ReservationCreate,
    ReservationReschedule,
)
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
    service.resource_repository.get_by_id = AsyncMock(
        return_value=MagicMock(hourly_rate_cents=2000, currency="EUR")
    )
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
    assert reservation.quoted_amount_cents == 2000
    assert reservation.quoted_currency == "EUR"
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
    service.resource_repository.get_by_id = AsyncMock(
        return_value=MagicMock(hourly_rate_cents=2000, currency="EUR")
    )
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


def recurring_data() -> RecurringReservationCreate:
    start_time = datetime.now(UTC) + timedelta(days=7)
    return RecurringReservationCreate(
        resource_id=20,
        start_time=start_time,
        end_time=start_time + timedelta(hours=1),
        frequency="weekly",
        occurrence_count=3,
    )


@pytest.mark.asyncio
async def test_recurring_reservations_are_created_as_one_series():
    service = ReservationService(AsyncMock())
    data = recurring_data()
    current_user = MagicMock(id=10, email="user@example.com")

    service.resource_repository.get_by_id = AsyncMock(
        return_value=MagicMock(hourly_rate_cents=2000, currency="EUR")
    )
    service._is_within_availability_rules = AsyncMock(return_value=True)
    service._has_availability_exception = AsyncMock(return_value=False)
    service.reservation_repository.has_conflicting_reservation = AsyncMock(
        return_value=False
    )

    async def create_series(reservations):
        for index, reservation in enumerate(reservations, start=1):
            reservation.id = index
        return reservations

    service.reservation_repository.create_series_with_conflict_lock = AsyncMock(
        side_effect=create_series
    )
    service.notification_service.create_notification = AsyncMock()

    with patch(
        "app.services.reservation_service.delete_available_slots_cache_for_resource",
        new_callable=AsyncMock,
    ) as delete_cache:
        result = await service.create_recurring_reservations(data, current_user)

    reservations = result["reservations"]
    assert result["occurrence_count"] == 3
    assert len({item.recurrence_series_id for item in reservations}) == 1
    assert {item.quoted_amount_cents for item in reservations} == {2000}
    assert {item.quoted_currency for item in reservations} == {"EUR"}
    assert reservations[1].start_time - reservations[0].start_time == timedelta(days=7)
    service.reservation_repository.create_series_with_conflict_lock.assert_awaited_once()
    service.notification_service.create_notification.assert_awaited_once()
    delete_cache.assert_awaited_once_with(data.resource_id)


@pytest.mark.asyncio
async def test_recurring_reservations_reject_entire_series_on_preflight_conflict():
    service = ReservationService(AsyncMock())
    data = recurring_data()
    current_user = MagicMock(id=10)

    service.resource_repository.get_by_id = AsyncMock(
        return_value=MagicMock(hourly_rate_cents=2000, currency="EUR")
    )
    service._is_within_availability_rules = AsyncMock(return_value=True)
    service._has_availability_exception = AsyncMock(return_value=False)
    service.reservation_repository.has_conflicting_reservation = AsyncMock(
        side_effect=[False, True]
    )
    service.reservation_repository.create_series_with_conflict_lock = AsyncMock()

    with pytest.raises(HTTPException) as exception_info:
        await service.create_recurring_reservations(data, current_user)

    assert exception_info.value.status_code == 409
    assert "Occurrence 2" in exception_info.value.detail
    service.reservation_repository.create_series_with_conflict_lock.assert_not_awaited()


@pytest.mark.asyncio
async def test_recurring_reservations_handle_conflict_found_under_lock():
    service = ReservationService(AsyncMock())
    data = recurring_data()
    current_user = MagicMock(id=10)

    service.resource_repository.get_by_id = AsyncMock(
        return_value=MagicMock(hourly_rate_cents=2000, currency="EUR")
    )
    service._is_within_availability_rules = AsyncMock(return_value=True)
    service._has_availability_exception = AsyncMock(return_value=False)
    service.reservation_repository.has_conflicting_reservation = AsyncMock(
        return_value=False
    )
    service.reservation_repository.create_series_with_conflict_lock = AsyncMock(
        return_value=None
    )

    with pytest.raises(HTTPException) as exception_info:
        await service.create_recurring_reservations(data, current_user)

    assert exception_info.value.status_code == 409
    assert "became unavailable" in exception_info.value.detail


@pytest.mark.asyncio
async def test_user_cannot_view_another_users_recurring_series():
    service = ReservationService(AsyncMock())
    service.reservation_repository.get_by_series_id = AsyncMock(
        return_value=[MagicMock(user_id=10)]
    )

    with pytest.raises(HTTPException) as exception_info:
        await service.get_recurring_reservations(
            recurrence_series_id="series-id",
            current_user=MagicMock(id=99, role="customer"),
        )

    assert exception_info.value.status_code == 403


@pytest.mark.asyncio
async def test_price_quote_uses_resource_hourly_rate():
    service = ReservationService(AsyncMock())
    start_time = datetime.now(UTC) + timedelta(days=1)
    service.resource_repository.get_by_id = AsyncMock(
        return_value=MagicMock(hourly_rate_cents=2400, currency="EUR")
    )

    quote = await service.get_price_quote(
        resource_id=20,
        start_time=start_time,
        end_time=start_time + timedelta(minutes=90),
    )

    assert quote["duration_minutes"] == 90
    assert quote["amount_cents"] == 3600
    assert quote["currency"] == "EUR"


@pytest.mark.asyncio
async def test_promotion_is_snapshotted_when_reservation_is_created():
    service = ReservationService(AsyncMock())
    start_time = datetime.now(UTC) + timedelta(days=2)
    data = ReservationCreate(
        resource_id=20,
        start_time=start_time,
        end_time=start_time + timedelta(hours=2),
        promotion_code="SAVE25",
    )
    resource = MagicMock(
        id=20,
        venue_id=5,
        hourly_rate_cents=2000,
        currency="EUR",
    )
    promotion = MagicMock(id=7, code="SAVE25", discount_percent=25)
    service.resource_repository.get_by_id = AsyncMock(return_value=resource)
    service._resolve_promotion = AsyncMock(return_value=promotion)
    service._is_within_availability_rules = AsyncMock(return_value=True)
    service._has_availability_exception = AsyncMock(return_value=False)
    service.reservation_repository.has_conflicting_reservation = AsyncMock(
        return_value=False
    )

    async def create_reservation(reservation, promotion_redemptions):
        reservation.id = 1
        assert promotion_redemptions == 1
        return reservation

    service.reservation_repository.create_with_conflict_lock = AsyncMock(
        side_effect=create_reservation
    )
    service.notification_service.create_notification = AsyncMock()

    with patch(
        "app.services.reservation_service.delete_available_slots_cache_for_resource",
        new_callable=AsyncMock,
    ):
        reservation = await service.create_reservation(
            data, MagicMock(id=10, email="user@example.com")
        )

    assert reservation.base_amount_cents == 4000
    assert reservation.discount_amount_cents == 1000
    assert reservation.quoted_amount_cents == 3000
    assert reservation.promotion_code == "SAVE25"
    assert reservation.promotion_discount_percent == 25


@pytest.mark.asyncio
async def test_exhausted_promotion_is_rejected():
    service = ReservationService(AsyncMock())
    now = datetime.now(UTC)
    service.promotion_repository.get_by_code = AsyncMock(
        return_value=MagicMock(
            venue_id=5,
            is_active=True,
            valid_from=now - timedelta(days=1),
            valid_until=now + timedelta(days=1),
            max_redemptions=10,
            redemption_count=10,
        )
    )

    with pytest.raises(HTTPException) as exception_info:
        await service._resolve_promotion("SOLDOUT", venue_id=5)

    assert exception_info.value.status_code == 409
    assert exception_info.value.detail == "Promotion redemption limit reached"
