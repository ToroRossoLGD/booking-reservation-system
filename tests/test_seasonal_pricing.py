import importlib.util
import json
import os
from datetime import date, timedelta
from pathlib import Path
from uuid import uuid4

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import create_engine, select, text
from sqlalchemy.ext.asyncio import create_async_engine

from app.core.config import settings
from app.models.property_listing import PropertyListing
from app.repositories.seasonal_price_expression import StayTotal
from app.schemas.property_listing import PropertyListingWrite
from app.services.nightly_pricing import nightly_prices
from app.services.property_listing_service import PropertyListingService
from tests import test_stay_availability_search as availability
from tests import test_stays

service = test_stays.service
catalog = availability.catalog


def rate(start, end, price=10000):
    return {
        "start": str(start),
        "end": str(end),
        "price_cents": price,
        "label": "Season",
    }


@pytest.mark.parametrize(
    "rates",
    [
        [rate("2030-10-03", "2030-10-03")],
        [rate("2030-10-04", "2030-10-03")],
        [rate("2030-10-03", "2030-10-05"), rate("2030-10-04", "2030-10-06")],
        [rate("2030-10-03", "2030-10-06"), rate("2030-10-04", "2030-10-05")],
        [rate("2030-10-03", "2030-10-04", 0)],
        [rate("2030-10-03", "2030-10-04", 1000000000001)],
    ],
)
def test_invalid_rates_rejected(rates):
    with pytest.raises(ValidationError):
        PropertyListingWrite(**test_stays.listing_data(seasonal_rates=rates))


def test_adjacent_rates_sorted_and_restricted_to_nightly():
    rates = [rate("2030-10-05", "2030-10-07"), rate("2030-10-03", "2030-10-05")]
    data = PropertyListingWrite(**test_stays.listing_data(seasonal_rates=rates))
    assert data.seasonal_rates[0].start == date(2030, 10, 3)
    for offer in ["sale", "long_term"]:
        with pytest.raises(ValidationError):
            PropertyListingWrite(
                **test_stays.listing_data(
                    offer_type=offer, booking_enabled=False, seasonal_rates=rates
                )
            )
    with pytest.raises(ValidationError):
        PropertyListingWrite(**test_stays.listing_data(seasonal_rates=rates * 13))


@pytest.mark.asyncio
async def test_owner_update_serializes_dates_and_preserves_confirmed_breakdown(service):
    db = service.repository.db
    data = test_stays.booking()
    periods = [rate(data.check_in, data.check_in + timedelta(days=1), 8500)]
    await PropertyListingService(db).update(
        1,
        PropertyListingWrite(**test_stays.listing_data(seasonal_rates=periods)),
        test_stays.OWNER,
    )
    quote = await service.quote(1, data)
    assert [night.price_cents for night in quote.nightly_prices] == [8500, 6500, 6500]
    assert quote.total_cents == 21500
    booking = data.model_copy(
        update={
            "expected_total_cents": quote.total_cents,
            "expected_nightly_prices": quote.nightly_prices,
        }
    )
    stay = await service.create(1, booking, test_stays.GUEST)
    snapshot = list(stay.nightly_prices)
    await PropertyListingService(db).update(
        1,
        PropertyListingWrite(**test_stays.listing_data(price_cents=12000)),
        test_stays.OWNER,
    )
    assert (
        await service.create(1, booking, test_stays.GUEST)
    ).nightly_prices == snapshot
    assert (await service.list(test_stays.GUEST)).items[0].nightly_prices[
        0
    ].price_cents == 8500
    assert (await service.list(test_stays.OWNER, owner=True)).items[
        0
    ].total_cents == 21500


@pytest.mark.asyncio
async def test_equal_total_but_changed_nightly_distribution_requires_new_quote(service):
    data = test_stays.booking()
    quote = await service.quote(1, data)
    listing = await service.repository.listing(1)
    listing.seasonal_rates = [
        rate(data.check_in, data.check_in + timedelta(days=1), 8500),
        rate(
            data.check_in + timedelta(days=1), data.check_in + timedelta(days=2), 4500
        ),
    ]
    await service.repository.db.commit()
    assert (await service.quote(1, data)).total_cents == quote.total_cents
    with pytest.raises(HTTPException) as error:
        await service.create(
            1,
            data.model_copy(update={"expected_nightly_prices": quote.nightly_prices}),
            test_stays.GUEST,
        )
    assert error.value.status_code == 409


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "start,days", [(0, 1), (1, 1), (2, 1), (3, 1), (0, 5), (2, 90)]
)
async def test_sql_and_python_pricing_agree_at_boundaries(catalog, start, days):
    _, session, listing = catalog
    base = availability.START
    listing.price_cents = 1000000000000
    listing.seasonal_rates = [
        rate(base + timedelta(days=1), base + timedelta(days=2), 1),
        rate(base + timedelta(days=2), base + timedelta(days=4), 12345),
    ]
    session.commit()
    arrival, departure = (
        base + timedelta(days=start),
        base + timedelta(days=start + days),
    )
    total = session.scalar(
        select(
            StayTotal(
                PropertyListing.seasonal_rates,
                PropertyListing.price_cents,
                arrival,
                departure,
            )
        ).where(PropertyListing.id == listing.id)
    )
    assert total == sum(
        night.price_cents for night in nightly_prices(listing, arrival, departure)
    )


@pytest.mark.asyncio
async def test_seasonal_search_filters_and_sorts_before_pagination(catalog):
    repository, session, listing = catalog
    listing.seasonal_rates = [rate(availability.START, availability.END, 12000)]
    second = PropertyListing(**test_stays.listing_data(price_cents=8000))
    session.add(second)
    session.commit()
    items, total = await availability.search(repository, sort="price_asc", limit=1)
    assert total == 2 and items[0].id == second.id
    items, total = await availability.search(
        repository, sort="price_asc", limit=1, offset=1
    )
    assert total == 2 and items[0].id == listing.id
    items, total = await availability.search(repository, max_price_cents=10000)
    assert total == 1 and items[0].id == second.id
    items, total = await availability.search(
        repository, min_price_cents=12000, max_price_cents=12000
    )
    assert total == 1 and items[0].id == listing.id
    # Without dates, filters retain their documented base-price meaning.
    items, _ = await repository.search(offer_type="short_stay", sort="price_asc")
    assert items[0].id == listing.id


@pytest.mark.asyncio
async def test_average_filter_uses_exact_total_and_response_contains_total(catalog):
    repository, session, listing = catalog
    listing.seasonal_rates = [
        rate(availability.START, availability.END - timedelta(days=1), 10000)
    ]
    session.commit()
    assert (await availability.search(repository, max_price_cents=8833))[1] == 0
    assert (await availability.search(repository, max_price_cents=8834))[1] == 1
    result = await PropertyListingService(repository.db).search(
        offer_type="short_stay",
        check_in=availability.START,
        check_out=availability.END,
        guests=2,
    )
    assert result.items[0].stay_total_cents == 26500
    assert result.items[0].price_cents == 6500


@pytest.mark.asyncio
@pytest.mark.skipif(not os.getenv("STAY_TEST_POSTGRES"), reason="Requires PostgreSQL")
async def test_postgres_price_expression_matches_nightly_calculation():
    engine = create_async_engine(settings.DATABASE_URL)
    table = "seasonal_price_test_" + uuid4().hex
    try:
        async with engine.begin() as connection:
            # A transaction-local temporary table cannot touch application data.
            await connection.execute(
                text(
                    f"CREATE TEMP TABLE {table} "
                    "(rates JSON, base BIGINT) ON COMMIT DROP"
                )
            )
            await connection.execute(
                text(f"INSERT INTO {table} VALUES (CAST(:rates AS JSON), :base)"),
                {
                    "rates": json.dumps([rate("2030-10-02", "2030-10-04", 9000)]),
                    "base": 6500,
                },
            )
            from sqlalchemy import JSON, BigInteger, column
            from sqlalchemy import table as sql_table

            source = sql_table(table, column("rates", JSON), column("base", BigInteger))
            total = await connection.scalar(
                select(
                    StayTotal(
                        source.c.rates,
                        source.c.base,
                        date(2030, 10, 1),
                        date(2030, 10, 5),
                    )
                )
            )
            assert total == 31000
    finally:
        await engine.dispose()


def test_migration_retains_legacy_booking_prices():
    path = (
        Path(__file__).parents[1]
        / "alembic/versions/ad835198024b_add_seasonal_nightly_rates.py"
    )
    spec = importlib.util.spec_from_file_location("seasonal_migration", path)
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
            connection.scalar(text("SELECT seasonal_rates FROM property_listings"))
            == "[]"
        )
        assert tuple(
            connection.execute(
                text("SELECT total_cents, nightly_prices FROM stays")
            ).one()
        ) == (19500, None)
        migration.downgrade()
        assert connection.scalar(text("SELECT total_cents FROM stays")) == 19500
    engine.dispose()
