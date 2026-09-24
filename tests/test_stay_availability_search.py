from datetime import UTC, date, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.property_listing import PropertyListing
from app.models.stay import Stay
from app.models.user import User
from app.models.venue import Venue
from app.repositories import property_listing_repository as module
from app.repositories.property_listing_repository import PropertyListingRepository
from tests.test_stays import listing_data

TODAY = date(2030, 10, 1)
START = TODAY + timedelta(days=3)
END = TODAY + timedelta(days=6)


@pytest.fixture
def catalog(monkeypatch):
    class Clock(datetime):
        @classmethod
        def now(cls, tz=None):
            return datetime(2030, 10, 1, 0, 30, tzinfo=UTC).astimezone(tz)

    monkeypatch.setattr(module, "datetime", Clock)
    engine = create_engine("sqlite://")
    Base.metadata.create_all(
        engine,
        tables=[
            User.__table__,
            Venue.__table__,
            PropertyListing.__table__,
            Stay.__table__,
        ],
    )
    with Session(engine) as session:
        session.add(
            User(id=1, email="owner@example.com", hashed_password="test", role="owner")
        )
        session.flush()
        session.add(Venue(id=1, name="Apartment", address="Address", owner_id=1))
        session.flush()
        listing = PropertyListing(**listing_data())
        session.add(listing)
        session.commit()
        db = MagicMock()
        db.scalar = AsyncMock(side_effect=session.scalar)
        db.scalars = AsyncMock(side_effect=session.scalars)
        yield PropertyListingRepository(db), session, listing
    engine.dispose()


def reserve(session, listing, start, end, status="confirmed"):
    session.add(
        Stay(
            property_id=listing.id,
            venue_id=listing.venue_id,
            user_id=1,
            request_id=str(uuid4()),
            check_in=start,
            check_out=end,
            guests=1,
            status=status,
            title=listing.title,
            city=listing.city,
            timezone=listing.timezone,
            contact_email=listing.contact_email,
            nightly_rate_cents=6500,
            total_cents=19500,
            currency="EUR",
        )
    )
    session.commit()


async def search(repository, **changes):
    return await repository.search(
        **(
            dict(offer_type="short_stay", check_in=START, check_out=END, guests=2)
            | changes
        )
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "start,end,expected",
    [
        (START, END, 0),
        (START - timedelta(days=1), END + timedelta(days=1), 0),
        (START + timedelta(days=1), END - timedelta(days=1), 0),
        (START - timedelta(days=1), START + timedelta(days=1), 0),
        (END - timedelta(days=1), END + timedelta(days=1), 0),
        (START - timedelta(days=3), START, 1),
        (END, END + timedelta(days=3), 1),
    ],
)
async def test_overlap_and_checkout_boundaries(catalog, start, end, expected):
    repository, session, listing = catalog
    reserve(session, listing, start, end)
    assert (await search(repository))[1] == expected


@pytest.mark.asyncio
async def test_aliases_cancelled_stays_count_and_pagination(catalog):
    repository, session, listing = catalog
    alias = PropertyListing(**listing_data())
    session.add(alias)
    session.commit()
    reserve(session, alias, START, END)
    assert (await search(repository))[1] == 0
    stay = session.query(Stay).one()
    stay.status = "cancelled"
    session.commit()
    first, total = await search(repository, limit=1)
    second, second_total = await search(repository, limit=1, offset=1)
    assert total == second_total == 2
    assert first[0].id == alias.id and second[0].id == listing.id
    assert (await search(repository, city="Missing city"))[1] == 0
    assert (await search(repository, currency="RSD"))[1] == 0


@pytest.mark.asyncio
async def test_occupied_venue_does_not_hide_other_apartments(catalog):
    repository, session, listing = catalog
    session.add(Venue(id=2, name="Other apartment", address="Other", owner_id=1))
    session.flush()
    other = PropertyListing(**listing_data(venue_id=2))
    session.add(other)
    session.commit()
    reserve(session, listing, START, END)
    items, total = await search(repository)
    assert total == 1 and items[0].id == other.id


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "changes",
    [
        {"max_guests": 1},
        {"minimum_nights": 4},
        {"booking_enabled": False},
        {"is_published": False},
        {"offer_type": "long_term", "booking_enabled": False},
    ],
)
async def test_listing_eligibility(catalog, changes):
    repository, session, listing = catalog
    for key, value in changes.items():
        setattr(listing, key, value)
    session.commit()
    assert (await search(repository))[1] == 0


@pytest.mark.asyncio
async def test_local_timezone_and_booking_horizon(catalog):
    repository, session, listing = catalog
    assert (
        await search(repository, check_in=TODAY, check_out=TODAY + timedelta(days=2))
    )[1] == 0
    listing.timezone = "America/Los_Angeles"
    session.commit()
    assert (
        await search(repository, check_in=TODAY, check_out=TODAY + timedelta(days=2))
    )[1] == 1
    assert (
        await search(
            repository,
            check_in=TODAY + timedelta(days=362),
            check_out=TODAY + timedelta(days=364),
        )
    )[1] == 1
    assert (
        await search(
            repository,
            check_in=TODAY + timedelta(days=363),
            check_out=TODAY + timedelta(days=365),
        )
    )[1] == 0


@pytest.mark.parametrize(
    "query",
    [
        "check_in=2030-10-04",
        "guests=2",
        "check_in=invalid&check_out=2030-10-07&guests=2",
        "check_in=2030-10-04&check_out=2030-10-04&guests=2",
        "check_in=2030-10-04&check_out=2030-10-03&guests=2",
        "check_in=2030-10-04&check_out=2031-10-07&guests=2",
        "check_in=2030-10-04&check_out=2030-10-07&guests=0",
        "check_in=2030-10-04&check_out=2030-10-07&guests=101",
    ],
)
def test_invalid_availability_search_returns_422(query):
    db = AsyncMock()
    app.dependency_overrides[get_db] = lambda: db
    try:
        with TestClient(app) as client:
            assert (
                client.get(f"/properties?offer_type=short_stay&{query}").status_code
                == 422
            )
        db.scalars.assert_not_awaited()
    finally:
        app.dependency_overrides.clear()


@pytest.mark.parametrize("offer", ["", "sale", "long_term"])
def test_dates_require_short_stay(offer):
    app.dependency_overrides[get_db] = lambda: AsyncMock()
    try:
        with TestClient(app) as client:
            response = client.get(
                "/properties",
                params={
                    "offer_type": offer,
                    "check_in": str(START),
                    "check_out": str(END),
                    "guests": 2,
                },
            )
            assert response.status_code == 422
    finally:
        app.dependency_overrides.clear()
