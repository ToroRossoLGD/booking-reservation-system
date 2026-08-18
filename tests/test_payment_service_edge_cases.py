from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException

from app.models.payment import Payment, PaymentStatus
from app.models.reservation import ReservationStatus
from app.services.payment_service import PaymentService


def current_user(user_id=10, role="customer"):
    return MagicMock(id=user_id, role=role, email="customer@example.com")


def reservation(**overrides):
    values = {
        "id": 1,
        "user_id": 10,
        "status": ReservationStatus.PENDING.value,
        "quoted_amount_cents": 2500,
        "quoted_currency": "EUR",
    }
    values.update(overrides)
    return MagicMock(**values)


@pytest.mark.asyncio
async def test_get_payment_rejects_missing_reservation():
    service = PaymentService(AsyncMock())
    service.reservation_repository.get_by_id = AsyncMock(return_value=None)

    with pytest.raises(HTTPException) as error:
        await service.get_reservation_payment(1, current_user())

    assert error.value.status_code == 404
    assert error.value.detail == "Reservation not found"


@pytest.mark.asyncio
async def test_get_payment_rejects_different_customer():
    service = PaymentService(AsyncMock())
    service.reservation_repository.get_by_id = AsyncMock(
        return_value=reservation(user_id=99)
    )

    with pytest.raises(HTTPException) as error:
        await service.get_reservation_payment(1, current_user())

    assert error.value.status_code == 403


@pytest.mark.asyncio
async def test_admin_can_view_another_customers_payment():
    service = PaymentService(AsyncMock())
    payment = MagicMock()
    service.reservation_repository.get_by_id = AsyncMock(
        return_value=reservation(user_id=99)
    )
    service.payment_repository.get_by_reservation_id = AsyncMock(return_value=payment)

    result = await service.get_reservation_payment(1, current_user(role="admin"))

    assert result is payment


@pytest.mark.asyncio
async def test_get_payment_returns_not_found_when_no_payment_exists():
    service = PaymentService(AsyncMock())
    service.reservation_repository.get_by_id = AsyncMock(return_value=reservation())
    service.payment_repository.get_by_reservation_id = AsyncMock(return_value=None)

    with pytest.raises(HTTPException) as error:
        await service.get_reservation_payment(1, current_user())

    assert error.value.status_code == 404
    assert error.value.detail == "Payment not found"


@pytest.mark.asyncio
async def test_customer_cannot_pay_for_another_users_reservation():
    service = PaymentService(AsyncMock())
    service.reservation_repository.get_by_id = AsyncMock(
        return_value=reservation(user_id=99)
    )

    with pytest.raises(HTTPException) as error:
        await service.pay_for_reservation(1, current_user())

    assert error.value.status_code == 403


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "reservation_status",
    [
        ReservationStatus.CONFIRMED.value,
        ReservationStatus.CANCELLED.value,
        ReservationStatus.COMPLETED.value,
        ReservationStatus.EXPIRED.value,
    ],
)
async def test_only_pending_reservations_can_be_paid(reservation_status):
    service = PaymentService(AsyncMock())
    service.reservation_repository.get_by_id = AsyncMock(
        return_value=reservation(status=reservation_status)
    )

    with pytest.raises(HTTPException) as error:
        await service.pay_for_reservation(1, current_user())

    assert error.value.status_code == 400
    assert error.value.detail == "Only pending reservations can be paid"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("amount", "currency"),
    [(None, "EUR"), (2500, None), (None, None)],
)
async def test_payment_requires_snapshotted_quote(amount, currency):
    service = PaymentService(AsyncMock())
    service.reservation_repository.get_by_id = AsyncMock(
        return_value=reservation(quoted_amount_cents=amount, quoted_currency=currency)
    )

    with pytest.raises(HTTPException) as error:
        await service.pay_for_reservation(1, current_user())

    assert error.value.status_code == 409
    assert error.value.detail == "Reservation does not have a price quote"


@pytest.mark.asyncio
async def test_already_paid_reservation_cannot_be_paid_twice():
    service = PaymentService(AsyncMock())
    service.reservation_repository.get_by_id = AsyncMock(return_value=reservation())
    service.payment_repository.get_by_reservation_id = AsyncMock(
        return_value=MagicMock(status=PaymentStatus.PAID.value)
    )

    with pytest.raises(HTTPException) as error:
        await service.pay_for_reservation(1, current_user())

    assert error.value.status_code == 409
    assert error.value.detail == "Reservation is already paid"


@pytest.mark.asyncio
async def test_failed_payment_is_reused_instead_of_creating_duplicate():
    service = PaymentService(AsyncMock())
    booking = reservation()
    existing = Payment(
        id=7,
        reservation_id=1,
        amount_cents=2000,
        currency="EUR",
        status=PaymentStatus.FAILED.value,
        provider="mock",
    )
    service.reservation_repository.get_by_id = AsyncMock(return_value=booking)
    service.payment_repository.get_by_reservation_id = AsyncMock(return_value=existing)
    service.payment_repository.create = AsyncMock()
    service.payment_repository.update = AsyncMock(side_effect=lambda payment: payment)
    service.reservation_repository.update = AsyncMock(side_effect=lambda item: item)
    service.reservation_event_repository.create = AsyncMock(
        side_effect=lambda event: event
    )
    service.notification_service.create_notification = AsyncMock()

    result = await service.pay_for_reservation(1, current_user())

    assert result is existing
    assert result.status == PaymentStatus.PAID.value
    assert result.amount_cents == booking.quoted_amount_cents
    service.payment_repository.create.assert_not_awaited()


@pytest.mark.asyncio
async def test_successful_payment_confirms_reservation_and_records_audit_event():
    service = PaymentService(AsyncMock())
    booking = reservation()
    service.reservation_repository.get_by_id = AsyncMock(return_value=booking)
    service.payment_repository.get_by_reservation_id = AsyncMock(return_value=None)

    async def create_payment(payment):
        payment.id = 7
        return payment

    service.payment_repository.create = AsyncMock(side_effect=create_payment)
    service.payment_repository.update = AsyncMock(side_effect=lambda payment: payment)
    service.reservation_repository.update = AsyncMock(side_effect=lambda item: item)
    service.reservation_event_repository.create = AsyncMock(
        side_effect=lambda event: event
    )
    service.notification_service.create_notification = AsyncMock()

    paid = await service.pay_for_reservation(1, current_user())

    assert paid.status == PaymentStatus.PAID.value
    assert paid.amount_cents == 2500
    assert booking.status == ReservationStatus.CONFIRMED.value
    event = service.reservation_event_repository.create.await_args.args[0]
    assert event.previous_status == ReservationStatus.PENDING.value
    assert event.new_status == ReservationStatus.CONFIRMED.value
    assert event.details["payment_id"] == 7
    service.notification_service.create_notification.assert_awaited_once()
