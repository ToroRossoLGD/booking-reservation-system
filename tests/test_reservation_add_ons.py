from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from app.models.reservation import Reservation
from app.models.reservation_add_on import AddOn, ReservationAddOn
from app.repositories.reservation_repository import (
    AddOnUnavailable,
    ReservationRepository,
)
from app.schemas.add_on import AddOnCreate, AddOnSelection, AddOnUpdate
from app.schemas.reservation import ReservationCreate
from app.services.add_on_service import AddOnService
from app.services.reservation_service import ReservationService


def future_window() -> tuple[datetime, datetime]:
    start = datetime.now(UTC) + timedelta(days=5)
    return start, start + timedelta(hours=2)


@pytest.mark.asyncio
async def test_owner_can_create_add_on_for_own_venue():
    service = AddOnService(AsyncMock())
    service.venue_repository.get_by_id = AsyncMock(
        return_value=MagicMock(id=4, owner_id=12)
    )
    service.repository.create = AsyncMock(side_effect=lambda add_on: add_on)

    result = await service.create(
        4,
        AddOnCreate(name="Projector", price_cents=1500, stock=3),
        MagicMock(id=12, role="owner"),
    )

    assert result.venue_id == 4
    assert result.name == "Projector"
    assert result.price_cents == 1500


@pytest.mark.asyncio
async def test_owner_cannot_manage_another_venues_add_ons():
    service = AddOnService(AsyncMock())
    service.venue_repository.get_by_id = AsyncMock(
        return_value=MagicMock(id=4, owner_id=99)
    )

    with pytest.raises(HTTPException) as error:
        await service.list_managed(4, MagicMock(id=12, role="owner"))

    assert error.value.status_code == 403


@pytest.mark.asyncio
async def test_admin_can_deactivate_add_on_and_snapshots_are_not_modified():
    service = AddOnService(AsyncMock())
    add_on = AddOn(id=8, venue_id=4, name="Lunch", price_cents=2500, stock=20)
    service.repository.get_by_id = AsyncMock(return_value=add_on)
    service.repository.update = AsyncMock(side_effect=lambda value: value)
    service.venue_repository.get_by_id = AsyncMock(
        return_value=MagicMock(id=4, owner_id=99)
    )
    snapshot = ReservationAddOn(
        add_on_id=8, name="Lunch", unit_price_cents=2500, quantity=2
    )

    updated = await service.update(
        8,
        AddOnUpdate(name="Premium lunch", price_cents=3000, is_active=False),
        MagicMock(id=1, role="admin"),
    )

    assert updated.name == "Premium lunch"
    assert updated.is_active is False
    assert snapshot.name == "Lunch"
    assert snapshot.unit_price_cents == 2500


def test_reservation_rejects_duplicate_add_on_selections():
    start, end = future_window()

    with pytest.raises(ValidationError, match="selected only once"):
        ReservationCreate(
            resource_id=3,
            start_time=start,
            end_time=end,
            add_ons=[
                AddOnSelection(add_on_id=7, quantity=1),
                AddOnSelection(add_on_id=7, quantity=2),
            ],
        )


@pytest.mark.asyncio
async def test_quote_adds_extras_after_resource_discount():
    start, end = future_window()
    service = ReservationService(AsyncMock())
    service.resource_repository.get_by_id = AsyncMock(
        return_value=MagicMock(id=3, venue_id=4, hourly_rate_cents=2000, currency="EUR")
    )
    service.add_on_repository.get_by_id = AsyncMock(
        return_value=SimpleNamespace(
            id=7,
            venue_id=4,
            name="Projector",
            price_cents=1500,
            stock=3,
            is_active=True,
        )
    )
    service.add_on_repository.reserved_quantity = AsyncMock(return_value=0)

    quote = await service.get_price_quote(
        resource_id=3,
        start_time=start,
        end_time=end,
        add_ons=[AddOnSelection(add_on_id=7, quantity=2)],
    )

    assert quote["base_amount_cents"] == 4000
    assert quote["add_on_total_cents"] == 3000
    assert quote["amount_cents"] == 7000
    assert quote["add_ons"][0].name == "Projector"


@pytest.mark.asyncio
async def test_quote_rejects_insufficient_overlapping_stock():
    start, end = future_window()
    service = ReservationService(AsyncMock())
    service.resource_repository.get_by_id = AsyncMock(
        return_value=MagicMock(id=3, venue_id=4, hourly_rate_cents=2000, currency="EUR")
    )
    service.add_on_repository.get_by_id = AsyncMock(
        return_value=SimpleNamespace(
            id=7,
            venue_id=4,
            name="Projector",
            price_cents=1500,
            stock=3,
            is_active=True,
        )
    )
    service.add_on_repository.reserved_quantity = AsyncMock(return_value=2)

    with pytest.raises(HTTPException) as error:
        await service.get_price_quote(
            resource_id=3,
            start_time=start,
            end_time=end,
            add_ons=[AddOnSelection(add_on_id=7, quantity=2)],
        )

    assert error.value.status_code == 409


@pytest.mark.asyncio
async def test_transactional_validation_refreshes_snapshot_and_total():
    start, end = future_window()
    repository = ReservationRepository(AsyncMock())
    repository.add_on_repository.get_by_id = AsyncMock(
        return_value=SimpleNamespace(
            id=7,
            venue_id=4,
            name="Renamed projector",
            price_cents=1750,
            stock=5,
            is_active=True,
        )
    )
    repository.add_on_repository.reserved_quantity = AsyncMock(return_value=1)
    reservation = Reservation(
        start_time=start,
        end_time=end,
        resource_id=3,
        user_id=2,
        base_amount_cents=4000,
        discount_amount_cents=1000,
        quoted_amount_cents=3000,
        quoted_currency="EUR",
    )
    reservation.add_ons = [
        ReservationAddOn(
            add_on_id=7, name="Old name", unit_price_cents=1500, quantity=2
        )
    ]

    await repository._validate_and_price_add_ons(reservation, venue_id=4)

    assert reservation.add_ons[0].name == "Renamed projector"
    assert reservation.add_ons[0].unit_price_cents == 1750
    assert reservation.add_on_total_cents == 3500
    assert reservation.quoted_amount_cents == 6500


@pytest.mark.asyncio
async def test_transactional_validation_blocks_stock_race():
    start, end = future_window()
    db = AsyncMock()
    repository = ReservationRepository(db)
    repository.add_on_repository.get_by_id = AsyncMock(
        return_value=SimpleNamespace(
            id=7,
            venue_id=4,
            name="Projector",
            price_cents=1500,
            stock=3,
            is_active=True,
        )
    )
    repository.add_on_repository.reserved_quantity = AsyncMock(return_value=2)
    reservation = Reservation(
        start_time=start,
        end_time=end,
        resource_id=3,
        user_id=2,
        base_amount_cents=4000,
        discount_amount_cents=0,
        quoted_amount_cents=4000,
        quoted_currency="EUR",
    )
    reservation.add_ons = [
        ReservationAddOn(
            add_on_id=7, name="Projector", unit_price_cents=1500, quantity=2
        )
    ]

    with pytest.raises(AddOnUnavailable, match="enough stock"):
        await repository._validate_and_price_add_ons(reservation, venue_id=4)

    db.rollback.assert_awaited_once()
