import importlib.util
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import create_engine, inspect, select, text
from sqlalchemy.orm import Session

from app.db.base import Base
from app.models.property_listing import PropertyListing
from app.models.rental_inquiry import RentalInquiry
from app.models.rental_message import RentalMessage
from app.models.user import User
from app.models.venue import Venue
from app.schemas.rental_inquiry import RentalInquiryCreate, RentalInquiryUpdate
from app.services.rental_inquiry_service import RentalInquiryService

OWNER = SimpleNamespace(id=1)
TENANT = SimpleNamespace(id=2)
OTHER = SimpleNamespace(id=3)


def inquiry_data(**changes):
    return RentalInquiryCreate(
        **(
            dict(
                request_id=uuid4(),
                move_in=date.today() + timedelta(days=30),
                duration_months=12,
                message="Interested in viewing this apartment.",
            )
            | changes
        )
    )


@pytest.fixture
def service():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(
        engine,
        tables=[
            User.__table__,
            Venue.__table__,
            PropertyListing.__table__,
            RentalInquiry.__table__,
            RentalMessage.__table__,
        ],
    )
    with Session(engine, expire_on_commit=False) as session:
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
        session.add(Venue(id=1, owner_id=1, name="Apartment", address="Test"))
        session.flush()
        session.add(
            PropertyListing(
                id=1,
                venue_id=1,
                title="Long-term apartment",
                description="Apartment for rent in the city.",
                city="Beograd",
                offer_type="long_term",
                area_sqm=50,
                rooms=2,
                price_cents=60000,
                currency="EUR",
                contact_email="owner@example.com",
                is_published=True,
            )
        )
        session.commit()
        db = MagicMock()
        db.add = session.add
        for name in ("scalar", "scalars", "commit", "refresh", "flush", "execute"):
            setattr(db, name, AsyncMock(side_effect=getattr(session, name)))
        yield RentalInquiryService(db)
    engine.dispose()


@pytest.mark.asyncio
async def test_inquiry_viewing_lifecycle_and_private_lists(service):
    inquiry = await service.create(1, inquiry_data(), TENANT)
    assert inquiry.status == "open" and inquiry.monthly_price_cents == 60000
    assert (await service.list(OTHER))["total"] == 0
    assert (await service.list(OTHER, owner=True))["total"] == 0
    assert (await service.list(TENANT))["total"] == 1
    assert (await service.list(OWNER, owner=True))["total"] == 1
    assert (await service.list(OWNER, owner=True, offset=1))["items"] == []
    viewing = datetime.now(timezone.utc) + timedelta(days=5)
    inquiry = await service.update(
        inquiry.id,
        RentalInquiryUpdate(
            version=1,
            action="propose",
            owner_reply="Meet at the building entrance.",
            viewing_at=viewing,
        ),
        OWNER,
    )
    assert inquiry.status == "viewing_proposed" and inquiry.version == 2
    inquiry = await service.update(
        inquiry.id, RentalInquiryUpdate(version=2, action="confirm"), TENANT
    )
    assert inquiry.status == "viewing_confirmed"
    inquiry = await service.update(
        inquiry.id, RentalInquiryUpdate(version=3, action="withdraw"), TENANT
    )
    assert inquiry.status == "withdrawn"
    with pytest.raises(HTTPException) as error:
        await service.update(
            inquiry.id,
            RentalInquiryUpdate(version=4, action="reply", owner_reply="Too late"),
            OWNER,
        )
    assert error.value.status_code == 409


@pytest.mark.asyncio
async def test_retries_active_duplicate_and_price_snapshot(service):
    data = inquiry_data()
    first = await service.create(1, data, TENANT)
    assert (await service.create(1, data, TENANT)).id == first.id
    for duplicate in (inquiry_data(), data.model_copy(update={"duration_months": 6})):
        with pytest.raises(HTTPException) as error:
            await service.create(1, duplicate, TENANT)
        assert error.value.status_code == 409
    listing = await service.db.scalar(
        select(PropertyListing).where(PropertyListing.id == 1)
    )
    listing.price_cents = 90000
    listing.is_published = False
    await service.db.commit()
    assert (await service.create(1, data, TENANT)).monthly_price_cents == 60000
    await service.update(
        first.id, RentalInquiryUpdate(version=1, action="close"), OWNER
    )
    listing.is_published = True
    await service.db.commit()
    assert (
        await service.create(1, inquiry_data(), TENANT)
    ).monthly_price_cents == 90000


@pytest.mark.asyncio
async def test_permissions_and_stale_viewing_confirmation(service):
    inquiry = await service.create(1, inquiry_data(), TENANT)
    for user, action, code in (
        (OTHER, "withdraw", 404),
        (OWNER, "withdraw", 403),
        (TENANT, "close", 403),
    ):
        with pytest.raises(HTTPException) as error:
            await service.update(
                inquiry.id, RentalInquiryUpdate(version=1, action=action), user
            )
        assert error.value.status_code == code
    for day in (5, 6):
        await service.update(
            inquiry.id,
            RentalInquiryUpdate(
                version=inquiry.version,
                action="propose",
                owner_reply="Proposed viewing",
                viewing_at=datetime.now(timezone.utc) + timedelta(days=day),
            ),
            OWNER,
        )
    with pytest.raises(HTTPException) as error:
        await service.update(
            inquiry.id, RentalInquiryUpdate(version=2, action="confirm"), TENANT
        )
    assert error.value.status_code == 409
    await service.update(
        inquiry.id, RentalInquiryUpdate(version=3, action="decline"), TENANT
    )
    assert inquiry.status == "open" and inquiry.viewing_at is None


@pytest.mark.asyncio
async def test_reject_invalid_property_and_dates(service):
    for property_id, user, data, code in (
        (999, TENANT, inquiry_data(), 404),
        (1, OWNER, inquiry_data(), 400),
        (1, TENANT, inquiry_data(move_in=date(2000, 1, 1)), 400),
    ):
        with pytest.raises(HTTPException) as error:
            await service.create(property_id, data, user)
        assert error.value.status_code == code
    listing = await service.db.scalar(
        select(PropertyListing).where(PropertyListing.id == 1)
    )
    for field, value, code in (
        ("is_published", False, 404),
        ("offer_type", "short_stay", 400),
    ):
        listing.is_published = True
        setattr(listing, field, value)
        await service.db.commit()
        with pytest.raises(HTTPException) as error:
            await service.create(1, inquiry_data(), TENANT)
        assert error.value.status_code == code


@pytest.mark.asyncio
async def test_expired_proposal_cannot_be_accepted(service):
    inquiry = await service.create(1, inquiry_data(), TENANT)
    with pytest.raises(HTTPException) as error:
        await service.update(
            inquiry.id,
            RentalInquiryUpdate(
                version=1,
                action="propose",
                owner_reply="Come tomorrow",
                viewing_at=datetime.now(timezone.utc) - timedelta(days=1),
            ),
            OWNER,
        )
    assert error.value.status_code == 400
    inquiry.status = "viewing_proposed"
    inquiry.viewing_at = datetime.now(timezone.utc) - timedelta(days=1)
    await service.db.commit()
    with pytest.raises(HTTPException) as error:
        await service.update(
            inquiry.id, RentalInquiryUpdate(version=1, action="confirm"), TENANT
        )
    assert error.value.status_code == 400


@pytest.mark.parametrize(
    "changes",
    [
        {"message": "   "},
        {"duration_months": 0},
        {"duration_months": 121},
        {"move_in": "invalid"},
    ],
)
def test_request_validation(changes):
    with pytest.raises(ValidationError):
        inquiry_data(**changes)


@pytest.mark.parametrize(
    "data",
    [
        dict(action="propose", owner_reply="Hello"),
        dict(action="propose", owner_reply="Hello", viewing_at="2030-01-01T12:00:00"),
        dict(action="reply", owner_reply="   "),
        dict(action="confirm", owner_reply="Unexpected reply"),
    ],
)
def test_action_validation(data):
    with pytest.raises(ValidationError):
        RentalInquiryUpdate(version=1, **data)


def test_migration_round_trip_preserves_existing_tables():
    path = (
        Path(__file__).parents[1]
        / "alembic/versions/a19d72b6e430_add_rental_inquiries.py"
    )
    spec = importlib.util.spec_from_file_location("rental_migration", path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    engine = create_engine("sqlite://")
    with engine.begin() as connection:
        connection.execute(
            text("CREATE TABLE property_listings (id INTEGER PRIMARY KEY)")
        )
        connection.execute(text("INSERT INTO property_listings VALUES (42)"))
        migration.op = Operations(MigrationContext.configure(connection))
        migration.upgrade()
        inspector = inspect(connection)
        assert {
            column["name"] for column in inspector.get_columns("rental_inquiries")
        } == set(RentalInquiry.__table__.columns.keys())
        assert len(inspector.get_indexes("rental_inquiries")) == 3
        assert len(inspector.get_unique_constraints("rental_inquiries")) == 1
        migration.downgrade()
        assert "rental_inquiries" not in inspect(connection).get_table_names()
        assert connection.scalar(text("SELECT id FROM property_listings")) == 42
    engine.dispose()


def test_routes_reject_unauthenticated_and_customer_owner_access():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from app.api.routers.rental_inquiries import router
    from app.core.dependencies import get_current_user
    from app.db.session import get_db

    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_db] = lambda: AsyncMock()
    with TestClient(app) as client:
        assert client.get("/rental-inquiries/mine").status_code == 401
        assert client.get("/rental-inquiries/1/messages").status_code == 401
        assert (
            client.post(
                "/rental-inquiries/1/messages",
                json={"body": "Hello", "request_id": str(uuid4())},
            ).status_code
            == 401
        )
        assert (
            client.post(
                "/rental-inquiries/1/messages/read", json={"message_ids": [1]}
            ).status_code
            == 401
        )
        assert (
            client.post(
                "/properties/1/rental-inquiries",
                json=inquiry_data().model_dump(mode="json"),
            ).status_code
            == 401
        )
        app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(
            id=2, role="customer"
        )
        assert client.get("/owner/rental-inquiries").status_code == 403
        assert client.get("/rental-inquiries/mine?offset=-1").status_code == 422
        assert client.get("/rental-inquiries/1/messages?limit=51").status_code == 422
        assert client.get("/rental-inquiries/1/messages?before_id=0").status_code == 422
        assert (
            client.post(
                "/rental-inquiries/1/messages/read",
                json={"message_ids": list(range(51))},
            ).status_code
            == 422
        )
