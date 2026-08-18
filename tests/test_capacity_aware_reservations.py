from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException

from app.models.reservation import Reservation
from app.repositories.reservation_repository import ReservationRepository
from app.schemas.reservation import ReservationCreate
from app.services.reservation_service import ReservationService
from app.services.resource_service import ResourceService


def reservation(start, end, party_size):
    return Reservation(start_time=start, end_time=end, party_size=party_size)


def test_peak_occupancy_does_not_sum_non_concurrent_overlaps():
    start = datetime(2026, 9, 1, 9, tzinfo=UTC)
    existing = [
        reservation(start, start + timedelta(hours=1), 4),
        reservation(start + timedelta(hours=1), start + timedelta(hours=2), 5),
    ]

    peak = ReservationRepository._peak_occupancy(
        existing,
        start + timedelta(minutes=30),
        start + timedelta(minutes=90),
    )

    assert peak == 5


def test_peak_occupancy_sums_genuinely_concurrent_groups():
    start = datetime(2026, 9, 1, 9, tzinfo=UTC)
    existing = [
        reservation(start, start + timedelta(hours=2), 4),
        reservation(
            start + timedelta(minutes=30),
            start + timedelta(minutes=90),
            3,
        ),
    ]

    assert (
        ReservationRepository._peak_occupancy(
            existing, start, start + timedelta(hours=2)
        )
        == 7
    )


@pytest.mark.asyncio
async def test_availability_reports_remaining_capacity_for_requested_party():
    service = ReservationService(AsyncMock())
    start = datetime(2026, 9, 1, 9, tzinfo=UTC)
    service.resource_repository.get_by_id = AsyncMock(
        return_value=MagicMock(id=20, capacity=10)
    )
    service._is_within_availability_rules = AsyncMock(return_value=True)
    service._has_availability_exception = AsyncMock(return_value=False)
    service.reservation_repository.get_capacity_availability = AsyncMock(
        return_value=(10, 4)
    )

    result = await service.check_availability(
        resource_id=20,
        start_time=start,
        end_time=start + timedelta(hours=1),
        party_size=5,
    )

    assert result["available"] is False
    assert result["requested_capacity"] == 5
    assert result["remaining_capacity"] == 4


@pytest.mark.asyncio
async def test_reservation_rejects_party_larger_than_total_capacity():
    service = ReservationService(AsyncMock())
    start = datetime.now(UTC) + timedelta(days=2)
    service.resource_repository.get_by_id = AsyncMock(
        return_value=MagicMock(id=20, capacity=6)
    )

    with pytest.raises(HTTPException) as exception_info:
        await service.create_reservation(
            ReservationCreate(
                resource_id=20,
                start_time=start,
                end_time=start + timedelta(hours=1),
                party_size=7,
            ),
            MagicMock(id=10),
        )

    assert exception_info.value.status_code == 400
    assert exception_info.value.detail == "Party size exceeds resource capacity (6)"


def test_party_size_is_part_of_idempotency_identity():
    start = datetime(2026, 9, 1, 9, tzinfo=UTC)
    common = {
        "resource_id": 20,
        "start_time": start,
        "end_time": start + timedelta(hours=1),
    }

    small_group = ReservationService._idempotency_request_hash(
        ReservationCreate(**common, party_size=2)
    )
    large_group = ReservationService._idempotency_request_hash(
        ReservationCreate(**common, party_size=5)
    )

    assert small_group != large_group


@pytest.mark.asyncio
async def test_available_resource_search_filters_by_remaining_capacity():
    service = ResourceService(AsyncMock())
    start = datetime(2026, 9, 1, 9, tzinfo=UTC)
    venue = SimpleNamespace(id=1, name="Community Center", address="Main Street")
    nearly_full = SimpleNamespace(
        id=10,
        name="Hall A",
        resource_type="hall",
        capacity=10,
        hourly_rate_cents=2000,
        currency="EUR",
    )
    available = SimpleNamespace(
        id=11,
        name="Hall B",
        resource_type="hall",
        capacity=10,
        hourly_rate_cents=2500,
        currency="EUR",
    )
    service.resource_repository.get_available_candidates = AsyncMock(
        return_value=[(nearly_full, venue), (available, venue)]
    )
    service.reservation_repository.get_capacity_availability = AsyncMock(
        side_effect=[(10, 2), (10, 6)]
    )

    result = await service.search_available_resources(
        start_time=start,
        end_time=start + timedelta(hours=1),
        minimum_capacity=4,
        limit=20,
        offset=0,
    )

    assert result.total == 1
    assert result.items[0].id == available.id
    assert result.items[0].remaining_capacity == 6
