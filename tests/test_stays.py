import asyncio
import os
from datetime import date, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import create_engine, func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.orm import Session
from sqlalchemy.schema import CreateSchema, DropSchema

from app.core.config import settings
from app.db.base import Base
from app.models.property_listing import PropertyListing
from app.models.resource import Resource
from app.models.stay import Stay
from app.models.user import User
from app.models.venue import Venue
from app.repositories.resource_repository import (
    NightlyInventoryConflict,
    ResourceRepository,
)
from app.schemas.property_listing import PropertyListingWrite
from app.schemas.stay import StayCreate, StayDates
from app.services.property_listing_service import PropertyListingService
from app.services.stay_service import StayService

TODAY = date(2026, 10, 1)
GUEST = SimpleNamespace(id=2, role="customer")
OTHER = SimpleNamespace(id=3, role="customer")
OWNER = SimpleNamespace(id=1, role="owner")


def listing_data(**changes):
    return (
        dict(
            venue_id=1,
            title="Planinski stan",
            city="Zlatibor",
            description="Ceo stan za odmor u planini.",
            offer_type="short_stay",
            area_sqm=45,
            rooms=2,
            price_cents=6500,
            currency="EUR",
            contact_email="host@example.com",
            is_published=True,
            booking_enabled=True,
            minimum_nights=2,
            max_guests=4,
            timezone="Europe/Belgrade",
        )
        | changes
    )


def booking(**changes):
    return StayCreate(
        **(
            dict(
                check_in=TODAY + timedelta(days=2),
                check_out=TODAY + timedelta(days=5),
                guests=2,
                request_id=uuid4(),
                expected_total_cents=19500,
                expected_currency="EUR",
            )
            | changes
        )
    )


def seed(session):
    session.add_all(
        [
            User(
                id=i,
                email=f"user{i}@example.com",
                hashed_password="test",
                role="owner" if i == 1 else "customer",
            )
            for i in (1, 2, 3)
        ]
    )
    session.flush()
    session.add(Venue(id=1, name="Apartment", address="Test address", owner_id=1))
    session.flush()
    session.add_all(
        [
            PropertyListing(id=1, **listing_data()),
            PropertyListing(id=2, **listing_data(title="Drugi oglas istog stana")),
        ]
    )
    session.commit()


@pytest.fixture
def service(monkeypatch):
    monkeypatch.setattr(StayService, "today", staticmethod(lambda zone: TODAY))
    engine = create_engine("sqlite://")
    Base.metadata.create_all(
        engine,
        tables=[
            User.__table__,
            Venue.__table__,
            PropertyListing.__table__,
            Resource.__table__,
            Stay.__table__,
        ],
    )
    with Session(engine, expire_on_commit=False) as session:
        seed(session)
        db = MagicMock()
        db.add = session.add
        for method in (
            "get",
            "commit",
            "refresh",
            "scalar",
            "scalars",
            "execute",
            "rollback",
        ):
            setattr(db, method, AsyncMock(side_effect=getattr(session, method)))
        yield StayService(db)
    engine.dispose()


@pytest.mark.asyncio
async def test_quote_booking_snapshot_and_cancel(service):
    data = booking()
    quote = await service.quote(
        1, StayDates(**data.model_dump(include={"check_in", "check_out", "guests"}))
    )
    assert quote.total_cents == 19500 and quote.nights == 3
    first = await service.create(1, data, GUEST)
    assert first.status == "confirmed"
    assert (await service.create(1, data, GUEST)).id == first.id
    # Occupancy is shared between aliases of the same whole apartment.
    with pytest.raises(HTTPException) as error:
        await service.create(2, booking(guests=1), OTHER)
    assert error.value.status_code == 409
    calendar = await service.calendar(2, TODAY, TODAY + timedelta(days=31))
    assert calendar.occupied[0].check_out == data.check_out
    assert set(calendar.occupied[0].model_dump()) == {"check_in", "check_out"}
    # Same-day departure/arrival is allowed: intervals are half-open.
    await service.create(
        2,
        booking(check_in=data.check_out, check_out=data.check_out + timedelta(days=3)),
        OTHER,
    )
    await PropertyListingService(service.repository.db).update(
        1,
        PropertyListingWrite(**listing_data(price_cents=9000, title="New title")),
        OWNER,
    )
    assert first.total_cents == 19500 and first.title == "Planinski stan"
    assert (await service.list(GUEST)).items[0].guest_email is None
    assert (await service.list(OWNER, owner=True)).items[0].guest_email is not None
    assert (await service.list(OTHER, owner=True)).total == 0
    await service.cancel(first.id, GUEST)
    assert (await service.create(1, data, GUEST)).status == "cancelled"
    replacement = await service.create(2, booking(), OTHER)
    assert replacement.id != first.id


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "changes,code",
    [
        ({"guests": 5}, 400),
        ({"check_in": TODAY}, 400),
        ({"check_out": TODAY + timedelta(days=3)}, 400),
        ({"expected_total_cents": 1}, 409),
        ({"expected_currency": "USD"}, 409),
        (
            {
                "check_in": TODAY + timedelta(days=365),
                "check_out": TODAY + timedelta(days=368),
            },
            400,
        ),
    ],
)
async def test_invalid_booking_rules(service, changes, code):
    with pytest.raises(HTTPException) as error:
        await service.create(1, booking(**changes), GUEST)
    assert error.value.status_code == code
    assert (await service.list(GUEST)).total == 0


@pytest.mark.asyncio
async def test_permissions_disabled_listings_and_request_reuse(service):
    with pytest.raises(HTTPException) as error:
        await service.create(1, booking(), OWNER)
    assert error.value.status_code == 400
    data = booking()
    stay = await service.create(1, data, GUEST)
    for actor in (OTHER, OWNER):
        with pytest.raises(HTTPException) as error:
            await service.cancel(stay.id, actor)
        assert error.value.status_code == 403
    with pytest.raises(HTTPException) as error:
        await service.create(1, booking(request_id=data.request_id, guests=3), GUEST)
    assert error.value.status_code == 409
    listing = await service.repository.listing(1)
    listing.is_published = False
    await service.repository.db.commit()
    # Safe retries still return the original reservation after unpublishing.
    assert (await service.create(1, data, GUEST)).id == stay.id
    with pytest.raises(HTTPException) as error:
        await service.quote(1, booking())
    assert error.value.status_code == 404
    listing.is_published = True
    listing.booking_enabled = False
    await service.repository.db.commit()
    with pytest.raises(HTTPException) as error:
        await service.quote(1, booking())
    assert error.value.status_code == 400


@pytest.mark.asyncio
async def test_cancellation_cutoff_and_calendar_bounds(service, monkeypatch):
    stay = await service.create(1, booking(), GUEST)
    monkeypatch.setattr(StayService, "today", staticmethod(lambda zone: stay.check_in))
    with pytest.raises(HTTPException) as error:
        await service.cancel(stay.id, GUEST)
    assert error.value.status_code == 400
    with pytest.raises(HTTPException):
        await service.calendar(1, TODAY, TODAY + timedelta(days=94))


@pytest.mark.asyncio
async def test_dst_counts_calendar_nights(service, monkeypatch):
    monkeypatch.setattr(
        StayService, "today", staticmethod(lambda zone: date(2026, 10, 20))
    )
    quote = await service.quote(
        1,
        StayDates(check_in=date(2026, 10, 24), check_out=date(2026, 10, 26), guests=1),
    )
    assert quote.nights == 2 and quote.total_cents == 13000


@pytest.mark.asyncio
async def test_hourly_and_nightly_inventory_cannot_mix(service):
    repository = ResourceRepository(service.repository.db)
    with pytest.raises(NightlyInventoryConflict):
        await repository.create(
            Resource(
                venue_id=1, name="Desk", resource_type="desk", hourly_rate_cents=1000
            )
        )
    # Move both listing aliases back to contact-only, then create an hourly resource.
    for property_id in (1, 2):
        listing = await service.repository.listing(property_id)
        listing.booking_enabled = False
    await service.repository.db.commit()
    resource = await repository.create(
        Resource(venue_id=1, name="Desk", resource_type="desk", hourly_rate_cents=1000)
    )
    assert resource.id
    with pytest.raises(HTTPException) as error:
        await PropertyListingService(service.repository.db).update(
            1, PropertyListingWrite(**listing_data()), OWNER
        )
    assert error.value.status_code == 409


@pytest.mark.parametrize(
    "changes",
    [
        {"check_out": TODAY + timedelta(days=2)},
        {"check_out": TODAY + timedelta(days=100)},
        {"guests": 0},
    ],
)
def test_invalid_request_schema(changes):
    with pytest.raises(ValidationError):
        booking(**changes)


@pytest.mark.parametrize(
    "changes",
    [
        {"timezone": "Invalid/Place"},
        {"offer_type": "sale"},
        {"minimum_nights": 0},
        {"max_guests": 0},
    ],
)
def test_invalid_owner_rules(changes):
    with pytest.raises(ValidationError):
        PropertyListingWrite(**listing_data(**changes))


@pytest.mark.asyncio
@pytest.mark.skipif(
    not os.getenv("STAY_TEST_POSTGRES"),
    reason="Set STAY_TEST_POSTGRES=1 to test PostgreSQL locking",
)
async def test_postgres_concurrent_overlap_and_retries(monkeypatch):
    monkeypatch.setattr(StayService, "today", staticmethod(lambda zone: TODAY))
    # Only a uniquely named test schema is created/dropped; public data is untouched.
    schema = "stay_test_" + uuid4().hex
    engine = create_async_engine(
        settings.DATABASE_URL,
        execution_options={"schema_translate_map": {None: schema}},
    )
    tables = [
        User.__table__,
        Venue.__table__,
        PropertyListing.__table__,
        Resource.__table__,
        Stay.__table__,
    ]
    try:
        async with engine.begin() as connection:
            await connection.execute(CreateSchema(schema))
            await connection.run_sync(
                lambda sync: Base.metadata.create_all(sync, tables=tables)
            )
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        async with sessions() as db:
            await db.run_sync(seed)

        async def attempt(property_id, data, user):
            async with sessions() as db:
                try:
                    stay = await StayService(db).create(property_id, data, user)
                    return stay.id
                except HTTPException as error:
                    await db.rollback()
                    return error

        outcomes = await asyncio.gather(
            attempt(1, booking(), GUEST), attempt(2, booking(), OTHER)
        )
        assert sum(isinstance(result, int) for result in outcomes) == 1
        assert [
            result.status_code
            for result in outcomes
            if isinstance(result, HTTPException)
        ] == [409]
        data = booking(
            check_in=TODAY + timedelta(days=10), check_out=TODAY + timedelta(days=13)
        )
        retries = await asyncio.gather(attempt(1, data, GUEST), attempt(1, data, GUEST))
        assert isinstance(retries[0], int) and retries[0] == retries[1]
        async with sessions() as db:
            assert await db.scalar(select(func.count(Stay.id))) == 2
    finally:
        async with engine.begin() as connection:
            await connection.execute(DropSchema(schema, cascade=True, if_exists=True))
        await engine.dispose()
