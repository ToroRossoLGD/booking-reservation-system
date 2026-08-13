from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException

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
