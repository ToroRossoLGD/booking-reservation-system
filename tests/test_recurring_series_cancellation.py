from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from app.models.reservation import ReservationStatus
from app.schemas.reservation import RecurringSeriesCancellationRequest
from app.services.reservation_service import ReservationService


def occurrence(
    reservation_id,
    *,
    start_delta=timedelta(days=3),
    status=ReservationStatus.CONFIRMED.value,
    user_id=10,
):
    return SimpleNamespace(
        id=reservation_id,
        user_id=user_id,
        start_time=datetime.now(UTC) + start_delta,
        status=status,
    )


def cancellation_result(item, refund=0, fee=0):
    return {
        "reservation": item,
        "refund_amount_cents": refund,
        "cancellation_fee_cents": fee,
    }


@pytest.mark.asyncio
async def test_series_cancellation_reuses_series_authorization():
    service = ReservationService(AsyncMock())
    current_user = MagicMock(id=10, role="customer")
    service.get_recurring_reservations = AsyncMock(
        side_effect=HTTPException(status_code=403, detail="Forbidden")
    )

    with pytest.raises(HTTPException) as error:
        await service.cancel_recurring_reservations(
            "series-id",
            RecurringSeriesCancellationRequest(),
            current_user,
        )

    assert error.value.status_code == 403
    service.get_recurring_reservations.assert_awaited_once_with(
        recurrence_series_id="series-id", current_user=current_user
    )


@pytest.mark.asyncio
async def test_series_cancellation_aggregates_refunds_and_fees():
    service = ReservationService(AsyncMock())
    first = occurrence(1)
    second = occurrence(2, start_delta=timedelta(days=4))
    service.get_recurring_reservations = AsyncMock(
        return_value={"reservations": [first, second]}
    )
    service.cancel_reservation = AsyncMock(
        side_effect=[
            cancellation_result(first, refund=2000, fee=0),
            cancellation_result(second, refund=1000, fee=500),
        ]
    )

    result = await service.cancel_recurring_reservations(
        "series-id",
        RecurringSeriesCancellationRequest(),
        MagicMock(id=10, role="customer"),
    )

    assert result["occurrence_count"] == 2
    assert result["cancelled_count"] == 2
    assert result["skipped_count"] == 0
    assert result["total_refund_amount_cents"] == 3000
    assert result["total_cancellation_fee_cents"] == 500
    assert result["cancelled_reservations"] == [first, second]


@pytest.mark.asyncio
async def test_cancel_from_leaves_earlier_occurrences_untouched():
    service = ReservationService(AsyncMock())
    early = occurrence(1, start_delta=timedelta(days=2))
    late = occurrence(2, start_delta=timedelta(days=8))
    service.get_recurring_reservations = AsyncMock(
        return_value={"reservations": [early, late]}
    )
    service.cancel_reservation = AsyncMock(
        return_value=cancellation_result(late, refund=1000)
    )
    cutoff = datetime.now(UTC) + timedelta(days=5)

    result = await service.cancel_recurring_reservations(
        "series-id",
        RecurringSeriesCancellationRequest(cancel_from=cutoff),
        MagicMock(id=10, role="customer"),
    )

    assert result["cancelled_count"] == 1
    assert result["skipped_count"] == 1
    assert service.cancel_reservation.await_args.kwargs["reservation_id"] == late.id


@pytest.mark.asyncio
async def test_terminal_and_started_occurrences_are_skipped():
    service = ReservationService(AsyncMock())
    reservations = [
        occurrence(1, status=ReservationStatus.CANCELLED.value),
        occurrence(2, status=ReservationStatus.COMPLETED.value),
        occurrence(3, status=ReservationStatus.EXPIRED.value),
        occurrence(4, start_delta=timedelta(minutes=-1)),
    ]
    service.get_recurring_reservations = AsyncMock(
        return_value={"reservations": reservations}
    )
    service.cancel_reservation = AsyncMock()

    result = await service.cancel_recurring_reservations(
        "series-id",
        RecurringSeriesCancellationRequest(),
        MagicMock(id=10, role="customer"),
    )

    assert result["cancelled_count"] == 0
    assert result["skipped_count"] == 4
    service.cancel_reservation.assert_not_awaited()


@pytest.mark.asyncio
async def test_past_cutoff_still_never_cancels_started_occurrence():
    service = ReservationService(AsyncMock())
    started = occurrence(1, start_delta=timedelta(hours=-1))
    future = occurrence(2, start_delta=timedelta(days=1))
    service.get_recurring_reservations = AsyncMock(
        return_value={"reservations": [started, future]}
    )
    service.cancel_reservation = AsyncMock(return_value=cancellation_result(future))

    result = await service.cancel_recurring_reservations(
        "series-id",
        RecurringSeriesCancellationRequest(
            cancel_from=datetime.now(UTC) - timedelta(days=30)
        ),
        MagicMock(id=10, role="customer"),
    )

    assert result["cancelled_count"] == 1
    assert service.cancel_reservation.await_args.kwargs["reservation_id"] == 2


@pytest.mark.asyncio
async def test_concurrently_cancelled_occurrence_is_safely_skipped():
    service = ReservationService(AsyncMock())
    first = occurrence(1)
    second = occurrence(2)
    service.get_recurring_reservations = AsyncMock(
        return_value={"reservations": [first, second]}
    )
    service.cancel_reservation = AsyncMock(
        side_effect=[
            HTTPException(status_code=400, detail="Already cancelled"),
            cancellation_result(second, refund=500),
        ]
    )

    result = await service.cancel_recurring_reservations(
        "series-id",
        RecurringSeriesCancellationRequest(),
        MagicMock(id=10, role="customer"),
    )

    assert result["cancelled_count"] == 1
    assert result["skipped_count"] == 1
    assert result["total_refund_amount_cents"] == 500


@pytest.mark.asyncio
async def test_unexpected_cancellation_error_is_not_hidden():
    service = ReservationService(AsyncMock())
    service.get_recurring_reservations = AsyncMock(
        return_value={"reservations": [occurrence(1)]}
    )
    service.cancel_reservation = AsyncMock(
        side_effect=HTTPException(
            status_code=503, detail="Payment provider unavailable"
        )
    )

    with pytest.raises(HTTPException) as error:
        await service.cancel_recurring_reservations(
            "series-id",
            RecurringSeriesCancellationRequest(),
            MagicMock(id=10, role="customer"),
        )

    assert error.value.status_code == 503


@pytest.mark.asyncio
async def test_individual_cancellations_receive_series_audit_context():
    service = ReservationService(AsyncMock())
    item = occurrence(1)
    background_tasks = MagicMock()
    service.get_recurring_reservations = AsyncMock(
        return_value={"reservations": [item]}
    )
    service.cancel_reservation = AsyncMock(return_value=cancellation_result(item))

    await service.cancel_recurring_reservations(
        "series-id",
        RecurringSeriesCancellationRequest(),
        MagicMock(id=10, role="customer"),
        background_tasks=background_tasks,
    )

    service.cancel_reservation.assert_awaited_once_with(
        reservation_id=1,
        current_user=service.get_recurring_reservations.await_args.kwargs[
            "current_user"
        ],
        background_tasks=background_tasks,
        recurring_series_id="series-id",
    )


def test_cancel_from_requires_timezone_information():
    with pytest.raises(ValidationError) as error:
        RecurringSeriesCancellationRequest(cancel_from=datetime(2026, 9, 1, 9))

    assert "cancel_from must include timezone information" in str(error.value)
