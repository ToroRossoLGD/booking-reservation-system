from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from app.models.venue_customer_block import VenueCustomerBlock
from app.schemas.venue_customer_block import VenueCustomerBlockCreate
from app.services.reservation_service import ReservationService
from app.services.venue_customer_block_service import VenueCustomerBlockService


def customer(user_id: int = 20):
    return SimpleNamespace(id=user_id, email="customer@example.com", role="customer")


def owner(user_id: int = 10):
    return SimpleNamespace(id=user_id, role="owner")


def venue(owner_id: int = 10):
    return SimpleNamespace(
        id=5,
        name="Central Courts",
        owner_id=owner_id,
        minimum_booking_notice_minutes=60,
        maximum_advance_booking_days=365,
        minimum_booking_duration_minutes=30,
        maximum_booking_duration_minutes=480,
        max_active_reservations_per_customer=10,
    )


def block_data(**overrides) -> VenueCustomerBlockCreate:
    values = {
        "customer_email": "customer@example.com",
        "reason": "Repeated violation of venue safety rules",
        "blocked_until": datetime.now(UTC) + timedelta(days=30),
    }
    values.update(overrides)
    return VenueCustomerBlockCreate(**values)


@pytest.mark.asyncio
async def test_owner_can_temporarily_block_customer_for_own_venue():
    service = VenueCustomerBlockService(AsyncMock())
    service.venue_repository.get_by_id = AsyncMock(return_value=venue())
    service.user_repository.get_by_email = AsyncMock(return_value=customer())
    service.repository.lock_customer = AsyncMock()
    service.repository.get = AsyncMock(return_value=None)

    async def save(value):
        value.id = 8
        return value

    service.repository.save = AsyncMock(side_effect=save)

    result = await service.block(5, block_data(), owner())

    assert result["customer_email"] == "customer@example.com"
    assert result["is_active"] is True
    assert result["blocked_by_id"] == 10
    service.repository.lock_customer.assert_awaited_once_with(20)


@pytest.mark.asyncio
async def test_owner_cannot_manage_another_venues_blocks():
    service = VenueCustomerBlockService(AsyncMock())
    service.venue_repository.get_by_id = AsyncMock(return_value=venue(owner_id=99))

    with pytest.raises(HTTPException) as error:
        await service.list_for_venue(5, True, owner())

    assert error.value.status_code == 403


@pytest.mark.asyncio
async def test_only_customer_accounts_can_be_blocked():
    service = VenueCustomerBlockService(AsyncMock())
    service.venue_repository.get_by_id = AsyncMock(return_value=venue())
    service.user_repository.get_by_email = AsyncMock(
        return_value=SimpleNamespace(id=30, email="owner@example.com", role="owner")
    )

    with pytest.raises(HTTPException) as error:
        await service.block(5, block_data(), owner())

    assert error.value.status_code == 400
    assert "Only customer" in error.value.detail


@pytest.mark.asyncio
async def test_duplicate_effective_block_is_rejected():
    service = VenueCustomerBlockService(AsyncMock())
    service.venue_repository.get_by_id = AsyncMock(return_value=venue())
    service.user_repository.get_by_email = AsyncMock(return_value=customer())
    service.repository.lock_customer = AsyncMock()
    existing = VenueCustomerBlock(
        id=8,
        venue_id=5,
        customer_id=20,
        reason="Existing reason",
        blocked_at=datetime.now(UTC),
        blocked_until=None,
        blocked_by_id=10,
    )
    service.repository.get = AsyncMock(return_value=existing)

    with pytest.raises(HTTPException) as error:
        await service.block(5, block_data(), owner())

    assert error.value.status_code == 409


@pytest.mark.asyncio
async def test_expired_block_can_be_reactivated():
    service = VenueCustomerBlockService(AsyncMock())
    service.venue_repository.get_by_id = AsyncMock(return_value=venue())
    service.user_repository.get_by_email = AsyncMock(return_value=customer())
    service.repository.lock_customer = AsyncMock()
    existing = VenueCustomerBlock(
        id=8,
        venue_id=5,
        customer_id=20,
        reason="Old reason",
        blocked_at=datetime.now(UTC) - timedelta(days=30),
        blocked_until=datetime.now(UTC) - timedelta(days=1),
        blocked_by_id=10,
        unblocked_at=None,
    )
    service.repository.get = AsyncMock(return_value=existing)
    service.repository.save = AsyncMock(side_effect=lambda value: value)

    result = await service.block(5, block_data(reason="New incident"), owner())

    assert result["is_active"] is True
    assert existing.reason == "New incident"
    assert existing.unblocked_at is None


@pytest.mark.asyncio
async def test_unblock_records_actor_and_time():
    service = VenueCustomerBlockService(AsyncMock())
    service.venue_repository.get_by_id = AsyncMock(return_value=venue())
    active = VenueCustomerBlock(
        id=8,
        venue_id=5,
        customer_id=20,
        reason="Safety violation",
        blocked_at=datetime.now(UTC),
        blocked_until=None,
        blocked_by_id=10,
    )
    service.repository.get_by_id = AsyncMock(return_value=active)
    service.repository.lock_customer = AsyncMock()
    service.user_repository.get_by_id = AsyncMock(return_value=customer())
    service.repository.save = AsyncMock(side_effect=lambda value: value)

    result = await service.unblock(5, 8, owner())

    assert result["is_active"] is False
    assert active.unblocked_at is not None
    assert active.unblocked_by_id == 10


@pytest.mark.asyncio
async def test_effective_block_prevents_new_booking_after_user_lock():
    db = AsyncMock()
    service = ReservationService(db)
    service.venue_repository.get_by_id = AsyncMock(return_value=venue())
    service.reservation_repository.lock_user_for_booking_rules = AsyncMock()
    service.venue_customer_block_repository.get_effective = AsyncMock(
        return_value=SimpleNamespace(
            blocked_until=datetime.now(UTC) + timedelta(days=1)
        )
    )
    start = datetime.now(UTC) + timedelta(days=2)

    with pytest.raises(HTTPException) as error:
        await service._validate_booking_rules(
            venue_id=5,
            occurrences=[(start, start + timedelta(hours=1))],
            current_user=customer(),
        )

    assert error.value.status_code == 403
    assert "Booking is not allowed" in error.value.detail
    service.reservation_repository.lock_user_for_booking_rules.assert_awaited_once_with(
        20
    )
    db.rollback.assert_awaited_once()


def test_block_expiry_requires_timezone():
    with pytest.raises(ValidationError, match="timezone"):
        block_data(blocked_until=datetime.now())


@pytest.mark.asyncio
async def test_customer_can_list_own_effective_blocks():
    service = VenueCustomerBlockService(AsyncMock())
    active = VenueCustomerBlock(
        id=8,
        venue_id=5,
        customer_id=20,
        reason="Safety violation",
        blocked_at=datetime.now(UTC),
        blocked_until=None,
        blocked_by_id=10,
    )
    service.repository.list_effective_for_customer = AsyncMock(
        return_value=[(active, "Central Courts")]
    )

    result = await service.list_my_blocks(customer())

    assert result[0]["venue_name"] == "Central Courts"
    assert result[0]["reason"] == "Safety violation"
