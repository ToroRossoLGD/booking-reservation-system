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

from app.schemas.property_listing import PropertyListingWrite
from tests import test_stay_availability_search as availability
from tests import test_stays

service = test_stays.service
catalog = availability.catalog


@pytest.mark.parametrize(
    "changes",
    [
        {"advance_notice_days": 0},
        {"advance_notice_days": 91},
        {"booking_window_days": 366},
        {"advance_notice_days": 5, "booking_window_days": 6},
        {"offer_type": "sale", "booking_enabled": False, "advance_notice_days": 3},
    ],
)
def test_invalid_booking_windows(changes):
    with pytest.raises(ValidationError):
        PropertyListingWrite(**test_stays.listing_data(**changes))


@pytest.mark.asyncio
async def test_boundaries_rechecked_at_confirmation_and_retry_preserved(service):
    listing = await service.repository.listing(1)
    listing.advance_notice_days = 2
    listing.booking_window_days = 5
    data = test_stays.booking()
    assert (await service.quote(1, data)).nights == 3
    listing.advance_notice_days = 3
    with pytest.raises(HTTPException) as error:
        await service.create(1, data, test_stays.GUEST)
    assert error.value.status_code == 400
    listing.advance_notice_days = 2
    first = await service.create(1, data, test_stays.GUEST)
    listing.booking_window_days = 4
    assert (await service.create(1, data, test_stays.GUEST)).id == first.id
    with pytest.raises(HTTPException) as error:
        await service.create(
            1, data.model_copy(update={"request_id": uuid4()}), test_stays.GUEST
        )
    assert error.value.status_code == 400
    assert first.check_out == data.check_out


@pytest.mark.asyncio
@pytest.mark.parametrize("notice,window,expected", [(3, 6, 1), (4, 6, 0), (3, 5, 0)])
async def test_search_filters_window_before_counting(catalog, notice, window, expected):
    repository, session, listing = catalog
    listing.advance_notice_days = notice
    listing.booking_window_days = window
    session.commit()
    items, total = await availability.search(repository)
    assert total == expected
    assert len(items) == expected


@pytest.mark.asyncio
async def test_local_timezone_window(catalog):
    repository, session, listing = catalog
    # At the fixture's UTC instant Los Angeles is still September 30.
    listing.timezone = "America/Los_Angeles"
    listing.advance_notice_days = 4
    listing.booking_window_days = 7
    session.commit()
    assert (await availability.search(repository))[1] == 1
    assert (
        await availability.search(
            repository, check_out=availability.END + timedelta(days=1)
        )
    )[1] == 0


def test_booking_window_migration():
    path = (
        Path(__file__).parents[1]
        / "alembic/versions/be946209135c_add_booking_windows.py"
    )
    spec = importlib.util.spec_from_file_location("window_migration", path)
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
        assert tuple(
            connection.execute(
                text(
                    "SELECT advance_notice_days, booking_window_days "
                    "FROM property_listings"
                )
            ).one()
        ) == (1, 365)
        migration.downgrade()
        assert connection.scalar(text("SELECT total_cents FROM stays")) == 19500
    engine.dispose()
