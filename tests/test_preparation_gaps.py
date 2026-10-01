import importlib.util
from datetime import timedelta
from pathlib import Path
from uuid import uuid4

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import create_engine, text

from app.models.property_listing import PropertyListing
from app.schemas.property_listing import PropertyListingWrite
from tests import test_stay_availability_search as availability
from tests import test_stays

service = test_stays.service
catalog = availability.catalog


@pytest.mark.asyncio
async def test_manual_blocks_do_not_expand(service):
    from app.schemas.stay_block import StayBlockCreate
    from app.services.stay_block_service import StayBlockService

    listing = await service.repository.listing(1)
    listing.preparation_days = 2
    data = test_stays.booking()
    block = await StayBlockService(service.repository.db).create(
        1,
        StayBlockCreate(
            check_in=data.check_in,
            check_out=data.check_out,
            request_id=uuid4(),
            reason="Maintenance",
        ),
        test_stays.OWNER,
    )
    adjacent = data.model_copy(
        update={
            "check_in": block.check_out,
            "check_out": block.check_out + timedelta(days=3),
        }
    )
    assert (await service.quote(1, adjacent)).nights == 3
    calendar = await service.calendar(1, data.check_in, adjacent.check_out)
    assert calendar.occupied[0].check_in == block.check_in
    assert calendar.occupied[0].check_out == block.check_out


@pytest.mark.parametrize("days", [-1, 8])
def test_invalid_gap(days):
    with pytest.raises(ValidationError):
        PropertyListingWrite(**test_stays.listing_data(preparation_days=days))


def test_gap_restricted_to_short_stays():
    with pytest.raises(ValidationError):
        PropertyListingWrite(
            **test_stays.listing_data(
                offer_type="sale", booking_enabled=False, preparation_days=1
            )
        )


@pytest.mark.asyncio
async def test_shared_gap_calendar_boundaries_and_cancel(service):
    first = await service.create(1, test_stays.booking(), test_stays.GUEST)
    sibling = await service.repository.listing(2)
    sibling.preparation_days = 2
    await service.repository.db.commit()
    candidate = test_stays.booking(
        check_in=first.check_out + timedelta(days=1),
        check_out=first.check_out + timedelta(days=4),
        request_id=uuid4(),
    )
    with pytest.raises(HTTPException) as error:
        await service.create(1, candidate, test_stays.OTHER)
    assert error.value.status_code == 409
    calendar = await service.calendar(
        1, first.check_in, first.check_out + timedelta(days=3)
    )
    assert calendar.preparation_days == 2
    assert calendar.occupied[0].check_in == first.check_in - timedelta(days=2)
    assert calendar.occupied[0].check_out == first.check_out + timedelta(days=2)
    assert first.check_out == test_stays.booking().check_out
    boundary = candidate.model_copy(
        update={
            "check_in": first.check_out + timedelta(days=2),
            "check_out": first.check_out + timedelta(days=5),
        }
    )
    assert (await service.quote(1, boundary)).nights == 3
    await service.cancel(first.id, test_stays.GUEST)
    assert (await service.quote(1, candidate)).nights == 3


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "start,end,total", [(3, 6, 0), (2, 5, 0), (1, 4, 1), (11, 14, 0), (12, 15, 1)]
)
async def test_search_gap_both_sides_before_pagination(catalog, start, end, total):
    repository, session, listing = catalog
    listing.preparation_days = 2
    availability.reserve(
        session,
        listing,
        availability.TODAY + timedelta(days=6),
        availability.TODAY + timedelta(days=10),
    )
    items, count = await availability.search(
        repository,
        check_in=availability.TODAY + timedelta(days=start),
        check_out=availability.TODAY + timedelta(days=end),
    )
    assert count == total
    assert len(items) == total


@pytest.mark.asyncio
async def test_search_uses_enabled_sibling_gap(catalog):
    repository, session, listing = catalog
    sibling = PropertyListing(
        **test_stays.listing_data(preparation_days=2, is_published=False)
    )
    session.add(sibling)
    availability.reserve(
        session, listing, availability.END, availability.END + timedelta(days=2)
    )
    assert (await availability.search(repository))[1] == 0
    sibling.booking_enabled = False
    session.commit()
    assert (await availability.search(repository))[1] == 1


def test_preparation_migration():
    path = (
        Path(__file__).parents[1]
        / "alembic/versions/cfa57310246d_add_preparation_days.py"
    )
    spec = importlib.util.spec_from_file_location("gap_migration", path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    engine = create_engine("sqlite://")
    with engine.begin() as connection:
        connection.execute(
            text("CREATE TABLE property_listings (id INTEGER PRIMARY KEY)")
        )
        connection.execute(text("INSERT INTO property_listings VALUES (1)"))
        connection.execute(
            text("CREATE TABLE stays (id INTEGER PRIMARY KEY, total_cents BIGINT)")
        )
        connection.execute(text("INSERT INTO stays VALUES (1, 19500)"))
        migration.op = Operations(MigrationContext.configure(connection))
        migration.upgrade()
        assert (
            connection.scalar(text("SELECT preparation_days FROM property_listings"))
            == 0
        )
        migration.downgrade()
        assert connection.scalar(text("SELECT total_cents FROM stays")) == 19500
    engine.dispose()
