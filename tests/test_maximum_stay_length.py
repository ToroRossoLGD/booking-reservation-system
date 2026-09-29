import importlib.util
from pathlib import Path

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import create_engine, select, text

from app.models.property_listing import PropertyListing
from app.schemas.property_listing import PropertyListingWrite
from tests import test_stays

service = test_stays.service


@pytest.mark.parametrize("maximum", [0, 91, 1])
def test_invalid_maximum_or_inverted_range(maximum):
    with pytest.raises(ValidationError):
        PropertyListingWrite(**test_stays.listing_data(maximum_nights=maximum))


def test_old_payload_defaults_to_ninety_nights():
    assert PropertyListingWrite(**test_stays.listing_data()).maximum_nights == 90
    assert (
        PropertyListingWrite(**test_stays.listing_data(maximum_nights=2)).maximum_nights
        == 2
    )


@pytest.mark.asyncio
async def test_limit_is_rechecked_at_confirmation_but_retries_preserve_booking(service):
    listing = await service.repository.db.scalar(
        select(PropertyListing).where(PropertyListing.id == 1)
    )
    listing.maximum_nights = 3
    await service.repository.db.commit()
    data = test_stays.booking()
    assert (await service.quote(1, data)).nights == 3
    listing.maximum_nights = 2
    await service.repository.db.commit()
    for operation in [
        service.quote(1, data),
        service.create(1, data, test_stays.GUEST),
    ]:
        with pytest.raises(HTTPException) as error:
            await operation
        assert error.value.status_code == 400
        assert "Maximum stay is 2" in error.value.detail
    listing.maximum_nights = 3
    await service.repository.db.commit()
    stay = await service.create(1, data, test_stays.GUEST)
    listing.maximum_nights = 2
    await service.repository.db.commit()
    retry = await service.create(1, data, test_stays.GUEST)
    assert retry.id == stay.id and retry.status == "confirmed"
    assert retry.check_out == data.check_out


def test_migration_preserves_listings_with_existing_limit():
    path = (
        Path(__file__).parents[1]
        / "alembic/versions/fc724087913a_add_maximum_stay_length.py"
    )
    spec = importlib.util.spec_from_file_location("maximum_stay_migration", path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    engine = create_engine("sqlite://")
    with engine.begin() as connection:
        connection.execute(
            text("CREATE TABLE property_listings (id INTEGER PRIMARY KEY)")
        )
        connection.execute(text("INSERT INTO property_listings VALUES (7)"))
        migration.op = Operations(MigrationContext.configure(connection))
        migration.upgrade()
        assert tuple(
            connection.execute(text("SELECT * FROM property_listings")).one()
        ) == (7, 90)
        migration.downgrade()
        assert connection.scalar(text("SELECT id FROM property_listings")) == 7
    engine.dispose()
