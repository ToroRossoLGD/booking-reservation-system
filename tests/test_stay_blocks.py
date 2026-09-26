import importlib.util
from datetime import timedelta
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import create_engine, inspect, text

from app.models.venue import Venue
from app.repositories.property_listing_repository import PropertyListingRepository
from app.schemas.property_listing import PropertyListingWrite
from app.schemas.stay_block import StayBlockCreate
from app.services.property_listing_service import PropertyListingService
from app.services.stay_block_service import StayBlockService
from tests import test_stays
from tests.test_stays import GUEST, OWNER, TODAY, booking, listing_data

stay_service = test_stays.service


def block_data(**changes):
    return StayBlockCreate(
        **(
            dict(
                check_in=TODAY + timedelta(days=2),
                check_out=TODAY + timedelta(days=5),
                reason="Private maintenance note",
                request_id=uuid4(),
            )
            | changes
        )
    )


@pytest.mark.asyncio
async def test_block_alias_privacy_search_and_reopening(stay_service):
    blocks = StayBlockService(stay_service.repository.db)
    data = block_data()
    created = await blocks.create(1, data, OWNER)
    assert (await blocks.create(2, data, OWNER)).id == created.id
    assert (await blocks.list(2, OWNER)).total == 1
    calendar = await stay_service.calendar(2, TODAY, TODAY + timedelta(days=31))
    assert calendar.occupied[0].model_dump() == {
        "check_in": data.check_in,
        "check_out": data.check_out,
    }
    with pytest.raises(HTTPException) as error:
        await stay_service.quote(2, booking())
    assert error.value.status_code == 409
    with pytest.raises(HTTPException) as error:
        await stay_service.create(2, booking(), GUEST)
    assert error.value.status_code == 409
    search = PropertyListingRepository(stay_service.repository.db)
    assert (
        await search.search(
            offer_type="short_stay",
            check_in=data.check_in,
            check_out=data.check_out,
            guests=2,
        )
    )[1] == 0
    await blocks.remove(2, created.id, OWNER)
    await blocks.remove(2, created.id, OWNER)
    assert (await blocks.list(1, OWNER)).total == 0
    assert (
        await search.search(
            offer_type="short_stay",
            check_in=data.check_in,
            check_out=data.check_out,
            guests=2,
        )
    )[1] == 2
    assert (await stay_service.create(2, booking(), GUEST)).status == "confirmed"
    with pytest.raises(HTTPException) as error:
        await blocks.create(1, data, OWNER)
    assert error.value.status_code == 409


@pytest.mark.asyncio
async def test_no_overlap_with_bookings_or_blocks_and_adjacent_dates_allowed(
    stay_service,
):
    blocks = StayBlockService(stay_service.repository.db)
    await stay_service.create(1, booking(), GUEST)
    with pytest.raises(HTTPException) as error:
        await blocks.create(2, block_data(), OWNER)
    assert error.value.status_code == 409
    adjacent = block_data(
        check_in=TODAY + timedelta(days=5), check_out=TODAY + timedelta(days=8)
    )
    created = await blocks.create(2, adjacent, OWNER)
    with pytest.raises(HTTPException) as error:
        await blocks.create(
            1, adjacent.model_copy(update={"request_id": uuid4()}), OWNER
        )
    assert error.value.status_code == 409
    assert created.active


@pytest.mark.asyncio
async def test_permissions_and_request_payload_conflict(stay_service):
    blocks = StayBlockService(stay_service.repository.db)
    data = block_data()
    created = await blocks.create(1, data, OWNER)
    for user in [GUEST, SimpleNamespace(id=2, role="owner")]:
        for action in [
            lambda: blocks.list(1, user),
            lambda: blocks.create(1, data, user),
            lambda: blocks.remove(1, created.id, user),
        ]:
            with pytest.raises(HTTPException) as error:
                await action()
            assert error.value.status_code == 403
    with pytest.raises(HTTPException) as error:
        await blocks.create(1, data.model_copy(update={"reason": "Changed"}), OWNER)
    assert error.value.status_code == 409
    with pytest.raises(HTTPException) as error:
        await blocks.remove(1, 9999, OWNER)
    assert error.value.status_code == 404


@pytest.mark.asyncio
async def test_window_and_pagination(stay_service):
    blocks = StayBlockService(stay_service.repository.db)
    for start, end in [
        (TODAY - timedelta(days=1), TODAY),
        (TODAY + timedelta(days=364), TODAY + timedelta(days=366)),
    ]:
        with pytest.raises(HTTPException) as error:
            await blocks.create(1, block_data(check_in=start, check_out=end), OWNER)
        assert error.value.status_code == 400
    first = await blocks.create(
        1, block_data(check_in=TODAY, check_out=TODAY + timedelta(days=1)), OWNER
    )
    await blocks.create(1, block_data(), OWNER)
    page = await blocks.list(1, OWNER, limit=1)
    assert page.total == 2 and page.has_next and page.items[0].id == first.id
    assert not (await blocks.list(1, OWNER, offset=1, limit=1)).has_next


@pytest.mark.asyncio
async def test_blocks_remain_manageable_after_withdrawal_or_offer_change(stay_service):
    db = stay_service.repository.db
    blocks = StayBlockService(db)
    listings = PropertyListingService(db)
    created = await blocks.create(1, block_data(), OWNER)
    db.add(Venue(id=2, name="Other", address="Other address", owner_id=1))
    await db.commit()
    with pytest.raises(HTTPException) as error:
        await listings.update(
            1, PropertyListingWrite(**listing_data(venue_id=2)), OWNER
        )
    assert error.value.status_code == 409
    await listings.update(
        1,
        PropertyListingWrite(
            **listing_data(
                is_published=False, offer_type="long_term", booking_enabled=False
            )
        ),
        OWNER,
    )
    assert (await blocks.list(1, OWNER)).items[0].id == created.id
    with pytest.raises(HTTPException) as error:
        await blocks.create(1, block_data(), OWNER)
    assert error.value.status_code == 400
    await blocks.remove(1, created.id, OWNER)
    assert (await blocks.list(2, OWNER)).total == 0


@pytest.mark.parametrize(
    "changes",
    [
        {"check_out": TODAY + timedelta(days=2)},
        {"check_out": TODAY + timedelta(days=368)},
        {"reason": "x" * 301},
        {"request_id": "bad"},
    ],
)
def test_invalid_input(changes):
    with pytest.raises(ValidationError):
        block_data(**changes)


def test_migration_round_trip_preserves_existing_objects():
    path = (
        Path(__file__).parents[1]
        / "alembic/versions/e50b7f102463_create_stay_blocks.py"
    )
    spec = importlib.util.spec_from_file_location("block_migration", path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    engine = create_engine("sqlite://")
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE venues (id INTEGER PRIMARY KEY)"))
        connection.execute(text("CREATE TABLE users (id INTEGER PRIMARY KEY)"))
        connection.execute(text("INSERT INTO venues VALUES (42)"))
        migration.op = Operations(MigrationContext.configure(connection))
        migration.upgrade()
        assert "stay_blocks" in inspect(connection).get_table_names()
        assert inspect(connection).get_unique_constraints("stay_blocks")[0][
            "column_names"
        ] == ["venue_id", "request_id"]
        migration.downgrade()
        assert "stay_blocks" not in inspect(connection).get_table_names()
        assert connection.scalar(text("SELECT id FROM venues")) == 42
    engine.dispose()
