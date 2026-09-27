from types import SimpleNamespace

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from pydantic import ValidationError
from sqlalchemy import create_engine, inspect, text

from app.schemas.property_listing import (
    PropertyListingRead,
    PropertyListingWrite,
    PropertySearch,
)
from tests import test_property_listings
from tests.test_stay_migration import load_migration

service = test_property_listings.service
OWNER = SimpleNamespace(id=1, role="owner")


@pytest.mark.parametrize(
    "field,value",
    [
        ("property_type", "office"),
        ("floor", -3),
        ("floor", 201),
        ("floor", 1.5),
        ("heating", "invalid"),
        ("furnishing", "invalid"),
        ("neighborhood", "x" * 101),
        ("has_elevator", "unknown"),
    ],
)
def test_invalid_details_rejected_in_listings_and_search(field, value):
    with pytest.raises(ValidationError):
        PropertyListingWrite(**test_property_listings.payload(**{field: value}))
    with pytest.raises(ValidationError):
        PropertySearch(**{field: value})


@pytest.mark.asyncio
async def test_details_persist_filter_before_pagination_and_clear(service):
    async def create(**changes):
        return await service.create(
            PropertyListingWrite(
                **test_property_listings.payload(is_published=True, **changes)
            ),
            OWNER,
        )

    first = await create(
        property_type="apartment",
        neighborhood="Liman 100%",
        floor=0,
        heating="district",
        furnishing="furnished",
        has_elevator=False,
        has_parking=True,
        has_terrace=True,
    )
    second = await create(
        property_type="apartment",
        neighborhood="Liman 100%",
        floor=0,
        heating="district",
        furnishing="furnished",
        has_elevator=False,
        has_parking=True,
        has_terrace=True,
    )
    await create(property_type="house", neighborhood="Liman 100X", has_parking=False)
    await create()  # Unknown is neither true nor false.
    filters = dict(
        property_type="apartment",
        neighborhood="100%",
        floor=0,
        heating="district",
        furnishing="furnished",
        has_elevator=False,
        has_parking=True,
        has_terrace=True,
    )
    page = await service.search(**filters, limit=1)
    assert page.total == 2 and page.has_next and page.items[0].id == second.id
    assert (await service.search(**filters, limit=1, offset=1)).items[0].id == first.id
    assert (await service.search(has_parking=False)).total == 1
    assert (await service.search(neighborhood="100%")).total == 2
    assert (await service.search(owner_id=2, **filters)).total == 0
    assert PropertyListingRead.model_validate(first).has_elevator is False
    await service.update(
        first.id, PropertyListingWrite(**test_property_listings.payload()), OWNER
    )
    assert first.floor is None and first.has_parking is None
    assert (await service.search(**filters)).total == 1


def test_details_migration_preserves_existing_rows_and_unknown_values():
    engine = create_engine("sqlite://")
    with engine.begin() as connection:
        connection.execute(
            text("CREATE TABLE property_listings (id INTEGER PRIMARY KEY)")
        )
        connection.execute(text("INSERT INTO property_listings VALUES (1)"))
        migration = load_migration(
            "a72d9b324685_add_property_details.py",
            Operations(MigrationContext.configure(connection)),
        )
        migration.upgrade()
        row = connection.execute(text("SELECT * FROM property_listings")).one()
        assert tuple(row) == (1,) + (None,) * 8
        connection.execute(
            text(
                "UPDATE property_listings SET property_type='house', "
                "floor=0, has_parking=0"
            )
        )
        migration.downgrade()
        assert [
            c["name"] for c in inspect(connection).get_columns("property_listings")
        ] == ["id"]
        assert connection.scalar(text("SELECT id FROM property_listings")) == 1
    engine.dispose()
