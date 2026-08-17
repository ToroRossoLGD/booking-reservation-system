from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from app.schemas.venue import VenueBookingRulesUpdate
from app.services.reservation_service import ReservationService
from app.services.venue_service import VenueService


def booking_rules(**overrides) -> VenueBookingRulesUpdate:
    values = {
        "minimum_booking_notice_minutes": 120,
        "maximum_advance_booking_days": 90,
        "minimum_booking_duration_minutes": 30,
        "maximum_booking_duration_minutes": 240,
        "max_active_reservations_per_customer": 5,
    }
    values.update(overrides)
    return VenueBookingRulesUpdate(**values)


def configured_venue(**overrides):
    values = {
        "id": 5,
        "owner_id": 10,
        "minimum_booking_notice_minutes": 120,
        "maximum_advance_booking_days": 90,
        "minimum_booking_duration_minutes": 30,
        "maximum_booking_duration_minutes": 240,
        "max_active_reservations_per_customer": 5,
    }
    values.update(overrides)
    return MagicMock(**values)


@pytest.mark.asyncio
async def test_owner_can_update_own_venue_booking_rules():
    service = VenueService(AsyncMock())
    venue = configured_venue()
    service.venue_repository.get_by_id = AsyncMock(return_value=venue)
    service.venue_repository.update = AsyncMock(return_value=venue)

    result = await service.update_booking_rules(
        venue.id,
        booking_rules(max_active_reservations_per_customer=8),
        MagicMock(id=venue.owner_id, role="owner"),
    )

    assert result.max_active_reservations_per_customer == 8
    service.venue_repository.update.assert_awaited_once_with(venue)


@pytest.mark.asyncio
async def test_owner_cannot_update_another_owners_booking_rules():
    service = VenueService(AsyncMock())
    service.venue_repository.get_by_id = AsyncMock(
        return_value=configured_venue(owner_id=10)
    )

    with pytest.raises(HTTPException) as exception_info:
        await service.update_booking_rules(
            5,
            booking_rules(),
            MagicMock(id=99, role="owner"),
        )

    assert exception_info.value.status_code == 403


def test_booking_rules_reject_inverted_duration_range():
    with pytest.raises(ValidationError):
        booking_rules(
            minimum_booking_duration_minutes=120,
            maximum_booking_duration_minutes=60,
        )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("start_delta", "duration", "expected_detail"),
    [
        (timedelta(minutes=60), timedelta(hours=1), "at least 120 minutes notice"),
        (timedelta(days=91), timedelta(hours=1), "more than 90 days"),
        (timedelta(days=2), timedelta(minutes=15), "at least 30 minutes"),
        (timedelta(days=2), timedelta(hours=5), "cannot exceed 240 minutes"),
    ],
)
async def test_booking_rule_time_boundaries_are_enforced(
    start_delta,
    duration,
    expected_detail,
):
    service = ReservationService(AsyncMock())
    service.venue_repository.get_by_id = AsyncMock(return_value=configured_venue())
    service.reservation_repository.count_active_for_user_at_venue = AsyncMock(
        return_value=0
    )
    start_time = datetime.now(UTC) + start_delta

    with pytest.raises(HTTPException) as exception_info:
        await service._validate_booking_rules(
            venue_id=5,
            occurrences=[(start_time, start_time + duration)],
            current_user=MagicMock(id=10),
        )

    assert exception_info.value.status_code == 400
    assert expected_detail in exception_info.value.detail


@pytest.mark.asyncio
async def test_recurring_series_counts_every_occurrence_against_active_limit():
    service = ReservationService(AsyncMock())
    service.reservation_repository.lock_user_for_booking_rules = AsyncMock()
    service.venue_repository.get_by_id = AsyncMock(
        return_value=configured_venue(max_active_reservations_per_customer=5)
    )
    service.reservation_repository.count_active_for_user_at_venue = AsyncMock(
        return_value=3
    )
    start_time = datetime.now(UTC) + timedelta(days=2)
    occurrences = [
        (
            start_time + timedelta(days=7 * index),
            start_time + timedelta(days=7 * index, hours=1),
        )
        for index in range(3)
    ]

    with pytest.raises(HTTPException) as exception_info:
        await service._validate_booking_rules(
            venue_id=5,
            occurrences=occurrences,
            current_user=MagicMock(id=10),
        )

    assert exception_info.value.status_code == 409
    assert "active reservation limit" in exception_info.value.detail
    service.db.rollback.assert_awaited_once()


@pytest.mark.asyncio
async def test_valid_booking_rules_check_active_count_for_user_and_venue():
    service = ReservationService(AsyncMock())
    service.reservation_repository.lock_user_for_booking_rules = AsyncMock()
    service.venue_repository.get_by_id = AsyncMock(return_value=configured_venue())
    service.reservation_repository.count_active_for_user_at_venue = AsyncMock(
        return_value=1
    )
    current_user = MagicMock(id=42)
    start_time = datetime.now(UTC) + timedelta(days=2)

    await service._validate_booking_rules(
        venue_id=5,
        occurrences=[(start_time, start_time + timedelta(hours=1))],
        current_user=current_user,
    )

    call = service.reservation_repository.count_active_for_user_at_venue.await_args
    service.reservation_repository.lock_user_for_booking_rules.assert_awaited_once_with(
        current_user.id
    )
    assert call.kwargs["user_id"] == current_user.id
    assert call.kwargs["venue_id"] == 5
