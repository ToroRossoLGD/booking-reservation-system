from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

from app.core.config import settings
from app.models.reservation import Reservation
from app.services.reservation_service import ReservationService


def test_refund_is_full_before_free_cancellation_deadline():
    service = ReservationService(MagicMock())
    current_time = datetime(2026, 8, 13, 12, tzinfo=UTC)
    reservation = Reservation(
        start_time=current_time
        + timedelta(hours=settings.FREE_CANCELLATION_HOURS),
        end_time=current_time
        + timedelta(hours=settings.FREE_CANCELLATION_HOURS + 1),
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
        start_time=current_time
        + timedelta(hours=settings.FREE_CANCELLATION_HOURS - 1),
        end_time=current_time
        + timedelta(hours=settings.FREE_CANCELLATION_HOURS),
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
