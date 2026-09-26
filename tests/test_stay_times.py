import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import create_engine, inspect, text

from app.schemas.property_listing import PropertyListingWrite
from app.schemas.stay import StayDates, StayRead
from app.services.property_listing_service import PropertyListingService
from tests import test_stays
from tests.test_stay_migration import load_migration

service = test_stays.service


@pytest.mark.parametrize("value", ["24:00", "9:00", "12:60", "14:00:00", "14:00Z", ""])
def test_rejects_invalid_local_times(value):
    with pytest.raises(ValidationError):
        PropertyListingWrite(
            **test_stays.listing_data(check_in_time=value, check_out_time="11:00")
        )


@pytest.mark.parametrize("offer", ["long_term", "sale"])
def test_times_are_only_for_nightly_properties(offer):
    with pytest.raises(ValidationError, match="only to short stays"):
        PropertyListingWrite(
            **test_stays.listing_data(
                offer_type=offer,
                booking_enabled=False,
                check_in_time="14:00",
                check_out_time="11:00",
            )
        )


def test_times_are_optional_but_must_be_a_pair():
    assert PropertyListingWrite(**test_stays.listing_data()).check_in_time is None
    with pytest.raises(ValidationError, match="both"):
        PropertyListingWrite(**test_stays.listing_data(check_in_time="14:00"))
    # These are on different dates: checkout need not be later in the day.
    assert (
        PropertyListingWrite(
            **test_stays.listing_data(check_in_time="23:59", check_out_time="00:00")
        ).check_out_time
        == "00:00"
    )


@pytest.mark.asyncio
async def test_snapshot_stale_quote_retry_and_offer_change(service):
    properties = PropertyListingService(service.repository.db)

    async def update(**changes):
        return await properties.update(
            1,
            PropertyListingWrite(**test_stays.listing_data(**changes)),
            test_stays.OWNER,
        )

    await update(check_in_time="14:00", check_out_time="11:00")
    data = test_stays.booking(
        expected_check_in_time="14:00",
        expected_check_out_time="11:00",
        expected_timezone="Europe/Belgrade",
    )
    dates = StayDates(**data.model_dump(include={"check_in", "check_out", "guests"}))
    quote = await service.quote(1, dates)
    assert (quote.check_in_time, quote.check_out_time) == ("14:00", "11:00")
    await update(check_in_time="15:00", check_out_time="10:00")
    with pytest.raises(HTTPException) as error:
        await service.create(1, data, test_stays.GUEST)
    assert error.value.status_code == 409
    await update(
        check_in_time="14:00", check_out_time="11:00", timezone="Europe/London"
    )
    with pytest.raises(HTTPException) as error:
        await service.create(1, data, test_stays.GUEST)
    assert error.value.status_code == 409
    await update(check_in_time="14:00", check_out_time="11:00")
    stay = await service.create(1, data, test_stays.GUEST)
    await update(offer_type="long_term", booking_enabled=False)
    retry = await service.create(1, data, test_stays.GUEST)
    assert retry.id == stay.id
    for owner, user in [(False, test_stays.GUEST), (True, test_stays.OWNER)]:
        saved = (await service.list(user, owner=owner)).items[0]
        assert (saved.check_in_time, saved.check_out_time, saved.timezone) == (
            "14:00",
            "11:00",
            "Europe/Belgrade",
        )
    assert StayRead.model_validate(stay).check_in_time == "14:00"


def test_migration_preserves_unknown_historical_times():
    engine = create_engine("sqlite://")
    with engine.begin() as connection:
        for table in ("property_listings", "stays"):
            connection.execute(text(f"CREATE TABLE {table} (id INTEGER PRIMARY KEY)"))
            connection.execute(text(f"INSERT INTO {table} VALUES (1)"))
        migration = load_migration(
            "f61c8a213574_add_stay_times.py",
            Operations(MigrationContext.configure(connection)),
        )
        migration.upgrade()
        for table in ("property_listings", "stays"):
            assert tuple(connection.execute(text(f"SELECT * FROM {table}")).one()) == (
                1,
                None,
                None,
            )
        migration.downgrade()
        for table in ("property_listings", "stays"):
            assert [c["name"] for c in inspect(connection).get_columns(table)] == ["id"]
            assert connection.scalar(text(f"SELECT id FROM {table}")) == 1
    engine.dispose()
