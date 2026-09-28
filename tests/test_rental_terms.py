from datetime import date, timedelta

import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import select

from app.models.property_listing import PropertyListing
from app.schemas.property_listing import PropertyListingWrite
from app.schemas.rental_inquiry import RentalInquiryRead
from tests import test_rental_inquiries
from tests.test_property_listings import payload

service = test_rental_inquiries.service


@pytest.mark.parametrize("offer", ["sale", "short_stay"])
@pytest.mark.parametrize(
    "terms",
    [
        {"deposit_cents": 0},
        {"monthly_bills_cents": 0},
        {"available_from": "2030-01-01"},
        {"minimum_rental_months": 1},
        {"pets_policy": "allowed"},
    ],
)
def test_terms_restricted_to_long_term(offer, terms):
    with pytest.raises(ValidationError):
        PropertyListingWrite(**payload(offer_type=offer, **terms))


@pytest.mark.parametrize(
    "terms",
    [
        {"deposit_cents": -1},
        {"monthly_bills_cents": -1},
        {"minimum_rental_months": 0},
        {"minimum_rental_months": 121},
        {"pets_policy": "unknown"},
    ],
)
def test_invalid_rental_terms(terms):
    with pytest.raises(ValidationError):
        PropertyListingWrite(**payload(offer_type="long_term", **terms))


@pytest.mark.asyncio
async def test_inquiry_enforces_terms_and_preserves_snapshot_on_retry(service):
    listing = await service.db.scalar(
        select(PropertyListing).where(PropertyListing.id == 1)
    )
    available = date.today() + timedelta(days=40)
    listing.available_from = available
    listing.minimum_rental_months = 24
    listing.deposit_cents = 0
    listing.monthly_bills_cents = 15000
    listing.pets_policy = "by_agreement"
    await service.db.commit()
    for changes in [
        dict(move_in=available - timedelta(days=1), duration_months=24),
        dict(move_in=available, duration_months=23),
    ]:
        with pytest.raises(HTTPException) as error:
            await service.create(
                1,
                test_rental_inquiries.inquiry_data(**changes),
                test_rental_inquiries.TENANT,
            )
        assert error.value.status_code == 400
    data = test_rental_inquiries.inquiry_data(move_in=available, duration_months=24)
    inquiry = await service.create(1, data, test_rental_inquiries.TENANT)
    snapshot = RentalInquiryRead.model_validate(inquiry)
    assert snapshot.deposit_cents == 0
    assert snapshot.monthly_bills_cents == 15000
    assert snapshot.minimum_rental_months == 24
    assert snapshot.available_from == available
    assert snapshot.pets_policy == "by_agreement"
    listing.deposit_cents = 90000
    listing.available_from = available + timedelta(days=60)
    listing.minimum_rental_months = 36
    await service.db.commit()
    retry = await service.create(1, data, test_rental_inquiries.TENANT)
    assert retry.id == inquiry.id
    assert retry.deposit_cents == 0 and retry.minimum_rental_months == 24
    for actor, owner in [
        (test_rental_inquiries.TENANT, False),
        (test_rental_inquiries.OWNER, True),
    ]:
        item = (await service.list(actor, owner=owner))["items"][0]
        assert RentalInquiryRead.model_validate(item).available_from == available


def test_migration_preserves_existing_rows():
    import importlib.util
    from pathlib import Path

    from alembic.migration import MigrationContext
    from alembic.operations import Operations
    from sqlalchemy import create_engine, inspect, text

    path = (
        Path(__file__).parents[1] / "alembic/versions/da502e657918_add_rental_terms.py"
    )
    spec = importlib.util.spec_from_file_location("rental_terms_migration", path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    engine = create_engine("sqlite://")
    with engine.begin() as connection:
        for table in ("property_listings", "rental_inquiries"):
            connection.execute(text(f"CREATE TABLE {table} (id INTEGER PRIMARY KEY)"))
            connection.execute(text(f"INSERT INTO {table} (id) VALUES (1)"))
        migration.op = Operations(MigrationContext.configure(connection))
        migration.upgrade()
        for table in ("property_listings", "rental_inquiries"):
            row = connection.execute(text(f"SELECT * FROM {table}")).one()
            assert tuple(row) == (1, None, None, None, None, None)
        migration.downgrade()
        for table in ("property_listings", "rental_inquiries"):
            assert [c["name"] for c in inspect(connection).get_columns(table)] == ["id"]
            assert connection.scalar(text(f"SELECT id FROM {table}")) == 1
    engine.dispose()
