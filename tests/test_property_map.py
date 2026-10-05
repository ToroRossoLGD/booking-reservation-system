import importlib.util
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import create_engine, inspect, text

from app.models.stay_block import StayBlock
from app.repositories.property_listing_repository import PropertyListingRepository
from app.schemas.property_listing import (
    PropertyListingRead,
    PropertyListingWrite,
    PropertySearch,
)
from app.schemas.saved_search import SavedSearchWrite
from tests.test_property_listings import payload, service  # noqa: F401
from tests.test_saved_search_alerts import USER, publish, store  # noqa: F401

OWNER = SimpleNamespace(id=1, role="owner")
BOUNDS = dict(map_south=44.7, map_north=44.9, map_west=20.3, map_east=20.6)


@pytest.mark.parametrize(
    "changes",
    [
        {"map_latitude": 44},
        {"map_longitude": 20},
        {"map_latitude": 86, "map_longitude": 20},
        {"map_latitude": 44, "map_longitude": 181},
        {"map_latitude": float("nan"), "map_longitude": 20},
        {"map_latitude": 44, "map_longitude": float("inf")},
    ],
)
def test_coordinates_require_a_finite_pair_in_map_range(changes):
    with pytest.raises(ValidationError):
        PropertyListingWrite(**payload(**changes))


@pytest.mark.parametrize(
    "changes",
    [
        {"map_south": 40},
        {**BOUNDS, "map_north": 44.6},
        {**BOUNDS, "map_east": 20.2},
        {**BOUNDS, "map_south": -86},
        {**BOUNDS, "map_west": float("nan")},
    ],
)
def test_map_bounds_are_complete_finite_and_ordered(changes):
    with pytest.raises(ValidationError):
        PropertySearch(**changes)


@pytest.mark.asyncio
async def test_only_approximate_coordinates_persist_and_owner_can_remove(service):  # noqa: F811
    data = PropertyListingWrite(
        **payload(is_published=True, map_latitude=44.812345, map_longitude=20.465678)
    )
    listing = await service.create(data, OWNER)
    assert (listing.map_latitude, listing.map_longitude) == (44.81, 20.47)
    assert PropertyListingRead.model_validate(listing).map_longitude == 20.47
    with pytest.raises(HTTPException) as error:
        await service.update(
            listing.id,
            PropertyListingWrite(**payload()),
            SimpleNamespace(id=2, role="owner"),
        )
    assert error.value.status_code == 403
    assert (await service.search(map_only=True)).total == 1
    await service.update(
        listing.id, PropertyListingWrite(**payload(is_published=True)), OWNER
    )
    assert (await service.search(map_only=True)).total == 0
    assert (await service.search()).total == 1
    assert listing.map_latitude is listing.map_longitude is None


@pytest.mark.asyncio
async def test_bounds_filter_before_count_and_pagination_without_disclosing_drafts(
    service,  # noqa: F811
):
    base = dict(is_published=True, map_latitude=44.8, map_longitude=20.45)
    for changes in [
        {},
        {"price_cents": 10000},
        {"map_latitude": 45},
        {"map_latitude": None, "map_longitude": None},
        {"is_published": False},
        {"currency": "RSD"},
        {"offer_type": "long_term"},
    ]:
        await service.create(PropertyListingWrite(**payload(**(base | changes))), OWNER)
    filters = PropertySearch(
        **BOUNDS, offer_type="sale", currency="EUR", sort="price_asc", limit=1
    )
    first = await service.search(**filters.model_dump())
    second = await service.search(**(filters.model_dump() | {"offset": 1}))
    assert first.total == second.total == 2
    assert first.items[0].id == 2 and first.has_next
    assert second.items[0].id == 1 and not second.has_next
    # Boundary points are included; filtering always uses the public rounded point.
    assert (
        await service.search(
            map_south=44.8, map_north=44.81, map_west=20.45, map_east=20.46
        )
    ).total == 4


def test_map_saved_search_preserves_bounds_and_validates_them():
    saved = SavedSearchWrite(
        name="Area",
        path="/?map_only=true&map_south=44.7&map_north=44.9&map_west=20.3&map_east=20.6&offset=12",
    )
    assert "map_south=44.7" in saved.path and "map_only=true" in saved.path
    assert "offset" not in saved.path
    with pytest.raises(ValidationError):
        SavedSearchWrite(name="Area", path="/?map_south=44.7")


@pytest.mark.asyncio
async def test_map_combines_availability_seasonal_prices_and_saved_alerts(store):  # noqa: F811
    session, db, searches, alerts = store
    search = await searches.save(
        SavedSearchWrite(
            name="Area",
            path="/?map_south=44.7&map_north=44.9&map_west=20.3&map_east=20.6",
        ),
        USER,
    )
    await searches.set_alerts(search.id, True, USER)
    start = datetime.now(UTC).date() + timedelta(days=10)
    end = start + timedelta(days=3)
    listing = await publish(
        db,
        map_latitude=44.81,
        map_longitude=20.46,
        timezone="UTC",
        seasonal_rates=[{"start": str(start), "end": str(end), "price_cents": 12000}],
    )
    await publish(db, map_latitude=45.25, map_longitude=19.84)
    await publish(db)
    assert await alerts.process(search.id) == 1
    assert await alerts.process(search.id) == 0
    repo = PropertyListingRepository(db)
    filters = dict(
        **BOUNDS,
        offer_type="short_stay",
        check_in=start,
        check_out=end,
        guests=2,
        currency="EUR",
    )
    assert (await repo.search(**filters, max_price_cents=11999))[1] == 0
    items, total = await repo.search(**filters, max_price_cents=12000)
    assert total == 1 and items[0].id == listing.id
    session.add(
        StayBlock(
            venue_id=1,
            created_by_id=1,
            request_id="map-test-block",
            check_in=start,
            check_out=end,
        )
    )
    session.commit()
    assert (await repo.search(**filters))[1] == 0


def test_migration_keeps_existing_listings_off_map_and_round_trips():
    spec = importlib.util.spec_from_file_location(
        "map_migration",
        Path("alembic/versions/c3fb39768023_add_property_map_location.py"),
    )
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    engine = create_engine("sqlite://")
    with engine.begin() as connection:
        connection.execute(
            text(
                "CREATE TABLE property_listings "
                "(id INTEGER PRIMARY KEY, title TEXT NOT NULL)"
            )
        )
        connection.execute(
            text("INSERT INTO property_listings VALUES (1, 'Existing listing')")
        )
        migration.op = Operations(MigrationContext.configure(connection))
        migration.upgrade()
        row = connection.execute(
            text("SELECT map_latitude, map_longitude FROM property_listings")
        ).one()
        assert row == (None, None)
        migration.downgrade()
        assert "map_latitude" not in {
            column["name"]
            for column in inspect(connection).get_columns("property_listings")
        }
        assert (
            connection.scalar(text("SELECT title FROM property_listings"))
            == "Existing listing"
        )
    engine.dispose()
