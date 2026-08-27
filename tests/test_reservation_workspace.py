from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from app.models.payment import PaymentStatus
from app.models.reservation import ReservationStatus
from app.services.reservation_service import ReservationService


def reservation(**overrides):
    values = {
        "id": 42,
        "user_id": 7,
        "resource_id": 10,
        "status": ReservationStatus.CONFIRMED.value,
        "start_time": datetime.now(UTC) + timedelta(days=3),
        "end_time": datetime.now(UTC) + timedelta(days=3, hours=1),
        "cancellation_free_hours": 24,
        "cancellation_late_refund_percent": 50,
    }
    values.update(overrides)
    return MagicMock(**values)


@pytest.mark.asyncio
@patch("app.services.reservation_service.datetime")
async def test_cancellation_preview_uses_snapshot_and_paid_amount(mock_datetime):
    now = datetime(2026, 8, 27, 12, tzinfo=UTC)
    mock_datetime.now.return_value = now
    service = ReservationService(AsyncMock())
    booked = reservation(start_time=now + timedelta(hours=12))
    service.get_reservation = AsyncMock(return_value=booked)
    service.payment_repository.get_by_reservation_id = AsyncMock(
        return_value=MagicMock(
            status=PaymentStatus.PAID.value,
            amount_cents=10_000,
        )
    )

    preview = await service.preview_cancellation(
        booked.id,
        MagicMock(id=booked.user_id, role="customer"),
    )

    assert preview["refund_percentage"] == 50
    assert preview["refund_amount_cents"] == 5_000
    assert preview["cancellation_fee_cents"] == 5_000
    assert preview["applied_free_cancellation_hours"] == 24


@pytest.mark.asyncio
async def test_cancellation_preview_rejects_finished_reservation():
    service = ReservationService(AsyncMock())
    booked = reservation(status=ReservationStatus.COMPLETED.value)
    service.get_reservation = AsyncMock(return_value=booked)

    with pytest.raises(HTTPException) as exception_info:
        await service.preview_cancellation(
            42,
            MagicMock(id=booked.user_id, role="customer"),
        )

    assert exception_info.value.status_code == 400


@pytest.mark.asyncio
async def test_cancellation_preview_rejects_non_customer_manager():
    service = ReservationService(AsyncMock())
    service.get_reservation = AsyncMock(return_value=reservation())

    with pytest.raises(HTTPException) as exception_info:
        await service.preview_cancellation(
            42,
            MagicMock(id=99, role="owner"),
        )

    assert exception_info.value.status_code == 403


@pytest.mark.asyncio
async def test_workspace_returns_context_and_server_owned_actions():
    service = ReservationService(AsyncMock())
    booked = reservation(status=ReservationStatus.PENDING.value)
    resource = MagicMock(id=10, venue_id=3, name="Garden room")
    venue = MagicMock(id=3, name="Green House", address="Main Street")
    events = [MagicMock(id=1, event_type="created")]
    service.get_reservation = AsyncMock(return_value=booked)
    service.resource_repository.get_by_id = AsyncMock(return_value=resource)
    service.venue_repository.get_by_id = AsyncMock(return_value=venue)
    service.payment_repository.get_by_reservation_id = AsyncMock(return_value=None)
    service.reservation_event_repository.get_for_reservation = AsyncMock(
        return_value=events
    )
    service.preview_cancellation = AsyncMock(return_value={"refund_amount_cents": 0})

    workspace = await service.get_reservation_workspace(
        42,
        MagicMock(id=booked.user_id, role="customer"),
    )

    assert workspace["resource"] is resource
    assert workspace["venue"] is venue
    assert workspace["timeline"] == events
    assert workspace["allowed_actions"] == ["pay", "cancel", "reschedule"]
    assert workspace["cancellation_preview"] == {"refund_amount_cents": 0}
