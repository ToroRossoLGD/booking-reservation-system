from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException

from app.models.payment import PaymentStatus
from app.models.reservation import ReservationStatus
from app.services.payment_service import PaymentService


@pytest.mark.asyncio
async def test_user_can_get_payment_for_own_reservation():
    service = PaymentService(AsyncMock())
    reservation = MagicMock(id=1, user_id=10)
    payment = MagicMock(reservation_id=reservation.id)
    current_user = MagicMock(id=reservation.user_id, role="user")
    service.reservation_repository.get_by_id = AsyncMock(return_value=reservation)
    service.payment_repository.get_by_reservation_id = AsyncMock(return_value=payment)

    result = await service.get_reservation_payment(
        reservation_id=reservation.id,
        current_user=current_user,
    )

    assert result is payment


@pytest.mark.asyncio
async def test_user_cannot_get_payment_for_another_users_reservation():
    service = PaymentService(AsyncMock())
    reservation = MagicMock(id=1, user_id=10)
    current_user = MagicMock(id=99, role="user")
    service.reservation_repository.get_by_id = AsyncMock(return_value=reservation)

    with pytest.raises(HTTPException) as exception_info:
        await service.get_reservation_payment(
            reservation_id=reservation.id,
            current_user=current_user,
        )

    assert exception_info.value.status_code == 403


@pytest.mark.asyncio
async def test_payment_uses_reservation_quote_instead_of_client_amount():
    service = PaymentService(AsyncMock())
    reservation = MagicMock(
        id=1,
        user_id=10,
        status=ReservationStatus.PENDING.value,
        quoted_amount_cents=3750,
        quoted_currency="EUR",
    )
    current_user = MagicMock(id=10, email="user@example.com")
    service.reservation_repository.get_by_id = AsyncMock(return_value=reservation)
    service.payment_repository.get_by_reservation_id = AsyncMock(return_value=None)
    service.payment_repository.create = AsyncMock(side_effect=lambda payment: payment)
    service.payment_repository.update = AsyncMock(side_effect=lambda payment: payment)
    service.reservation_repository.update = AsyncMock(return_value=reservation)
    service.notification_service.create_notification = AsyncMock()

    payment = await service.pay_for_reservation(
        reservation_id=reservation.id,
        current_user=current_user,
    )

    assert payment.amount_cents == 3750
    assert payment.currency == "EUR"
    assert payment.status == PaymentStatus.PAID.value
    assert reservation.status == ReservationStatus.CONFIRMED.value


@pytest.mark.asyncio
async def test_payment_rejects_legacy_reservation_without_quote():
    service = PaymentService(AsyncMock())
    reservation = MagicMock(
        id=1,
        user_id=10,
        status=ReservationStatus.PENDING.value,
        quoted_amount_cents=None,
        quoted_currency=None,
    )
    service.reservation_repository.get_by_id = AsyncMock(return_value=reservation)

    with pytest.raises(HTTPException) as exception_info:
        await service.pay_for_reservation(
            reservation_id=reservation.id,
            current_user=MagicMock(id=10),
        )

    assert exception_info.value.status_code == 409
