import importlib.util
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from fastapi import HTTPException
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.property_listing import PropertyListing
from app.models.user import User
from app.models.venue import Venue
from app.schemas.property_listing import PropertyListingWrite
from app.services.property_listing_service import PropertyListingService


def payload(**changes):
    data = dict(
        venue_id=1,
        title="Stan na Limanu",
        description="Svetao stan blizu reke i parka.",
        city="Novi Sad",
        offer_type="sale",
        area_sqm=64,
        rooms=3,
        price_cents=15600000,
        currency="EUR",
        contact_email="owner@example.com",
        is_published=False,
    )
    return data | changes


@pytest.fixture
def service():
    # Exercise repository SQL against an isolated database, never the configured DB.
    engine = create_engine("sqlite://")
    Base.metadata.create_all(
        engine, tables=[User.__table__, Venue.__table__, PropertyListing.__table__]
    )
    with Session(engine) as session:
        session.add_all(
            [
                User(
                    id=1, email="one@example.com", hashed_password="test", role="owner"
                ),
                User(
                    id=2, email="two@example.com", hashed_password="test", role="owner"
                ),
            ]
        )
        session.flush()
        session.add_all(
            [
                Venue(id=1, name="One", address="Address one", owner_id=1),
                Venue(id=2, name="Two", address="Address two", owner_id=2),
            ]
        )
        session.commit()
        db = MagicMock()
        db.add = session.add
        for method in ("get", "commit", "refresh", "scalar", "scalars", "execute"):
            setattr(db, method, AsyncMock(side_effect=getattr(session, method)))
        yield PropertyListingService(db)
    engine.dispose()


@pytest.mark.asyncio
async def test_publish_search_update_and_withdraw(service):
    owner = SimpleNamespace(id=1, role="owner")
    listing = await service.create(PropertyListingWrite(**payload()), owner)
    assert (await service.search()).total == 0
    assert (await service.search(owner_id=1)).total == 1
    with pytest.raises(HTTPException) as error:
        await service.get_public(listing.id)
    assert error.value.status_code == 404

    await service.update(
        listing.id, PropertyListingWrite(**payload(is_published=True)), owner
    )
    page = await service.search(city="novi", offer_type="sale")
    assert page.total == 1
    assert page.items[0].price_cents == 15600000
    assert (await service.get_public(listing.id)).title == "Stan na Limanu"
    assert (await service.search(offer_type="short_stay")).total == 0
    assert (await service.search(city="%")).total == 0

    await service.update(
        listing.id, PropertyListingWrite(**payload(is_published=False)), owner
    )
    assert (await service.search()).total == 0


@pytest.mark.asyncio
async def test_ownership_and_pagination(service):
    owner = SimpleNamespace(id=1, role="owner")
    other = SimpleNamespace(id=2, role="owner")
    first = await service.create(PropertyListingWrite(**payload()), owner)
    for data, actor, listing_id in [
        (payload(venue_id=1), other, None),
        (payload(venue_id=2), other, first.id),
        (payload(venue_id=2), owner, first.id),
    ]:
        with pytest.raises(HTTPException) as error:
            if listing_id is None:
                await service.create(PropertyListingWrite(**data), actor)
            else:
                await service.update(listing_id, PropertyListingWrite(**data), actor)
        assert error.value.status_code == 403
    assert (await service.search(owner_id=2)).total == 0
    await service.create(PropertyListingWrite(**payload(title="Drugi stan")), owner)
    page = await service.search(owner_id=1, limit=1)
    assert page.total == 2 and page.has_next
    assert page.items[0].title == "Drugi stan"
    page = await service.search(owner_id=1, limit=1, offset=1)
    assert page.items[0].id == first.id and not page.has_next


@pytest.mark.parametrize(
    "changes",
    [
        {"price_cents": 0},
        {"rooms": -1},
        {"area_sqm": 0},
        {"offer_type": "hourly"},
        {"currency": "BAD"},
        {"contact_email": "not-an-email"},
        {"title": "   "},
        {"description": "short"},
    ],
)
def test_invalid_listing_rejected(changes):
    with pytest.raises(ValidationError):
        PropertyListingWrite(**payload(**changes))


def test_customer_cannot_create_or_list_owner_properties():
    app.dependency_overrides[get_db] = lambda: AsyncMock()
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(
        id=3, role="customer"
    )
    try:
        with TestClient(app) as client:
            assert client.post("/properties", json=payload()).status_code == 403
            assert client.put("/properties/1", json=payload()).status_code == 403
            assert client.get("/owner/properties").status_code == 403
            assert client.get("/properties?limit=0").status_code == 422
            assert client.get("/properties?offset=-1").status_code == 422
            assert client.get("/properties?offer_type=hourly").status_code == 422
    finally:
        app.dependency_overrides.clear()


def test_migration_upgrade_and_downgrade_preserve_existing_venues():
    path = (
        Path(__file__).parents[1]
        / "alembic/versions/c4e9a2b7d610_create_property_listings.py"
    )
    spec = importlib.util.spec_from_file_location("property_migration", path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    engine = create_engine("sqlite://")
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE venues (id INTEGER PRIMARY KEY)"))
        connection.execute(text("INSERT INTO venues (id) VALUES (42)"))
        migration.op = Operations(MigrationContext.configure(connection))
        migration.upgrade()
        inspector = inspect(connection)
        assert {
            column["name"] for column in inspector.get_columns("property_listings")
        } == set(PropertyListing.__table__.columns.keys()) - {
            "booking_enabled",
            "max_guests",
            "minimum_nights",
            "timezone",
        }
        assert len(inspector.get_indexes("property_listings")) == 4
        assert len(inspector.get_check_constraints("property_listings")) == 4
        migration.downgrade()
        assert "property_listings" not in inspect(connection).get_table_names()
        assert connection.scalar(text("SELECT id FROM venues")) == 42
    engine.dispose()
