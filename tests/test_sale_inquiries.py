import os
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import func, select

from app.models.notification import Notification
from app.models.property_listing import PropertyListing
from app.models.sale_inquiry import SaleInquiry, SaleMessage
from app.schemas.rental_inquiry import RentalInquiryUpdate
from app.schemas.rental_message import RentalMessageCreate, RentalMessagesRead
from app.schemas.sale_inquiry import SaleInquiryCreate, SaleInquiryRead
from app.services.rental_inquiry_service import RentalInquiryService
from app.services.rental_message_service import RentalMessageService
from tests.test_rental_inquiries import OTHER, OWNER, TENANT, inquiry_data
from tests.test_rental_inquiries import service as rentals  # noqa: F401
from tests.test_stays import listing_data


@pytest.fixture
def sales(rentals):  # noqa: F811 - imported pytest fixture
    db = rentals.db
    engine = db.commit.side_effect.__self__.get_bind()
    SaleInquiry.__table__.create(engine)
    SaleMessage.__table__.create(engine)
    db.add(
        PropertyListing(
            id=2,
            **listing_data(
                offer_type="sale", booking_enabled=False, price_cents=14000000
            ),
        )
    )
    db.commit.side_effect()
    return RentalInquiryService(db, sale=True)


def data(**changes):
    return SaleInquiryCreate(
        **(
            dict(
                request_id=uuid4(),
                message="Interested in buying and viewing this property.",
            )
            | changes
        )
    )


@pytest.mark.asyncio
async def test_sale_viewing_lifecycle_price_snapshot_notifications_and_history(sales):
    inquiry = await sales.create(2, data(), TENANT)
    assert inquiry.asking_price_cents == 14000000
    assert (
        "monthly_price_cents"
        not in SaleInquiryRead.model_validate(inquiry).model_dump()
    )
    listing = await sales.db.scalar(
        select(PropertyListing).where(PropertyListing.id == 2)
    )
    listing.price_cents = 15000000
    await sales.db.commit()
    assert (await sales.list(TENANT))["items"][0].asking_price_cents == 14000000
    assert (await sales.list(OTHER))["total"] == 0
    viewing = datetime.now(UTC) + timedelta(days=5)
    await sales.update(
        inquiry.id,
        RentalInquiryUpdate(
            version=1,
            action="propose",
            owner_reply="Meet at the front entrance.",
            viewing_at=viewing,
        ),
        OWNER,
    )
    await sales.update(
        inquiry.id, RentalInquiryUpdate(version=2, action="confirm"), TENANT
    )
    assert inquiry.status == "viewing_confirmed"
    notices = list(
        await sales.db.scalars(select(Notification).order_by(Notification.id))
    )
    assert [notice.action_path for notice in notices] == [
        "/owner/sales",
        "/sales",
        "/owner/sales",
    ]
    assert all(notice.deduplication_key.startswith("sale:") for notice in notices)
    conversation = RentalMessageService(sales.db, sale=True)
    history = await conversation.list(inquiry.id, TENANT)
    assert [message.kind for message in history["items"]] == [
        "message",
        "propose",
        "confirm",
    ]
    assert history["items"][0].sender == "buyer"
    await sales.update(
        inquiry.id, RentalInquiryUpdate(version=3, action="close"), OWNER
    )
    assert (await conversation.list(inquiry.id, TENANT))["items"][-1].kind == "close"
    with pytest.raises(HTTPException) as error:
        await conversation.send(
            inquiry.id,
            RentalMessageCreate(request_id=uuid4(), body="New message"),
            TENANT,
        )
    assert error.value.status_code == 409


@pytest.mark.asyncio
async def test_retries_wrong_offer_own_and_hidden_listings(sales):
    payload = data()
    first = await sales.create(2, payload, TENANT)
    assert (await sales.create(2, payload, TENANT)).id == first.id
    for body in (
        data(),
        payload.model_copy(update={"message": "A different request message"}),
    ):
        with pytest.raises(HTTPException) as error:
            await sales.create(2, body, TENANT)
        assert error.value.status_code == 409
    for property_id, user in ((1, OTHER), (2, OWNER)):
        with pytest.raises(HTTPException) as error:
            await sales.create(property_id, data(), user)
        assert error.value.status_code == 400
    listing = await sales.db.scalar(
        select(PropertyListing).where(PropertyListing.id == 2)
    )
    listing.is_published = False
    listing.moderation_state = "suspended"
    await sales.db.commit()
    with pytest.raises(HTTPException) as error:
        await sales.create(2, data(), OTHER)
    assert error.value.status_code == 404
    assert (await sales.create(2, payload, TENANT)).id == first.id
    assert (await sales.list(TENANT))["total"] == 1


@pytest.mark.asyncio
async def test_rental_and_sales_ids_are_separate_and_participant_only(sales, rentals):  # noqa: F811
    rental = await rentals.create(1, inquiry_data(), OTHER)
    sale = await sales.create(2, data(), TENANT)
    assert rental.id == sale.id
    assert (await rentals.list(TENANT))["total"] == 0
    assert (await sales.list(OTHER))["total"] == 0
    messages = RentalMessageService(sales.db, sale=True)
    for operation in (
        sales.update(sale.id, RentalInquiryUpdate(version=1, action="withdraw"), OTHER),
        messages.list(sale.id, OTHER),
        messages.mark_read(sale.id, RentalMessagesRead(message_ids=[1]), OTHER),
        messages.send(
            sale.id, RentalMessageCreate(request_id=uuid4(), body="Private"), OTHER
        ),
        RentalMessageService(sales.db).list(rental.id, TENANT),
    ):
        with pytest.raises(HTTPException) as error:
            await operation
        assert error.value.status_code == 404
    with pytest.raises(HTTPException) as error:
        await sales.update(
            sale.id, RentalInquiryUpdate(version=1, action="close"), TENANT
        )
    assert error.value.status_code == 403


@pytest.mark.asyncio
async def test_sale_message_retries_unread_pagination_and_stale_viewing(sales):
    inquiry = await sales.create(2, data(), TENANT)
    messages = RentalMessageService(sales.db, sale=True)
    body = RentalMessageCreate(request_id=uuid4(), body="Can we view on Saturday?")
    sent = await messages.send(inquiry.id, body, TENANT)
    assert (await messages.send(inquiry.id, body, TENANT)).id == sent.id
    assert (await sales.list(OWNER, owner=True))["items"][0].unread_count == 2
    newest = await messages.list(inquiry.id, OWNER, limit=1)
    assert newest["has_more"] and len(newest["items"]) == 1
    await messages.mark_read(
        inquiry.id, RentalMessagesRead(message_ids=[sent.id]), OWNER
    )
    assert (await sales.list(OWNER, owner=True))["items"][0].unread_count == 1
    assert inquiry.version == 1
    await sales.update(
        inquiry.id,
        RentalInquiryUpdate(
            version=1,
            action="propose",
            viewing_at=datetime.now(UTC) + timedelta(days=3),
            owner_reply="Saturday works.",
        ),
        OWNER,
    )
    with pytest.raises(HTTPException) as error:
        await sales.update(
            inquiry.id, RentalInquiryUpdate(version=1, action="confirm"), TENANT
        )
    assert error.value.status_code == 409
    await sales.update(
        inquiry.id, RentalInquiryUpdate(version=2, action="decline"), TENANT
    )
    assert inquiry.status == "open" and inquiry.viewing_at is None
    await sales.update(
        inquiry.id, RentalInquiryUpdate(version=3, action="withdraw"), TENANT
    )
    replacement = await sales.create(2, data(), TENANT)
    assert replacement.id != inquiry.id


@pytest.mark.asyncio
async def test_failed_submission_rolls_back_opening_message_and_notification(sales):
    payload = data()
    commit = sales.db.commit.side_effect
    sales.db.commit.side_effect = RuntimeError("commit failed")
    with pytest.raises(RuntimeError):
        await sales.create(2, payload, TENANT)
    await sales.db.rollback()
    sales.db.commit.side_effect = commit
    for model in (SaleInquiry, SaleMessage, Notification):
        assert await sales.db.scalar(select(func.count()).select_from(model)) == 0
    await sales.create(2, payload, TENANT)
    assert await sales.db.scalar(select(func.count(SaleInquiry.id))) == 1


def test_sale_schema_and_authenticated_routes():
    from fastapi.testclient import TestClient

    from app.main import app

    with pytest.raises(ValidationError):
        data(move_in="2026-11-01", duration_months=12)
    with TestClient(app) as client:
        for path in (
            "/sale-inquiries/mine",
            "/owner/sale-inquiries",
            "/sale-inquiries/1/messages",
        ):
            assert client.get(path).status_code == 401
        for path in (
            "/properties/1/sale-inquiries",
            "/sale-inquiries/1/messages",
            "/sale-inquiries/1/messages/read",
        ):
            assert client.post(path, json={}).status_code == 401
        assert client.patch("/sale-inquiries/1", json={}).status_code == 401


def test_sales_migration_roundtrip_and_active_uniqueness():
    import importlib.util
    from pathlib import Path

    from alembic.migration import MigrationContext
    from alembic.operations import Operations
    from sqlalchemy import create_engine, inspect, text
    from sqlalchemy.exc import IntegrityError

    path = (
        Path(__file__).parents[1]
        / "alembic/versions/b2ea28657912_add_sale_inquiries.py"
    )
    spec = importlib.util.spec_from_file_location("sales_migration", path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    engine = create_engine("sqlite://")
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE users (id INTEGER PRIMARY KEY)"))
        connection.execute(
            text("CREATE TABLE property_listings (id INTEGER PRIMARY KEY)")
        )
        connection.execute(
            text("CREATE TABLE rental_inquiries (id INTEGER PRIMARY KEY)")
        )
        connection.execute(text("INSERT INTO rental_inquiries VALUES (42)"))
        migration.op = Operations(MigrationContext.configure(connection))
        migration.upgrade()
        for model in (SaleInquiry, SaleMessage):
            assert {
                c["name"] for c in inspect(connection).get_columns(model.__tablename__)
            } == set(model.__table__.columns.keys())
        row = dict(
            property_id=1,
            owner_id=1,
            user_id=2,
            request_id="a",
            title="Sale",
            asking_price_cents=10000000,
            currency="EUR",
            message="Interested",
            owner_reply="",
            status="open",
            version=1,
            created_at=datetime.now(UTC),
        )
        connection.execute(SaleInquiry.__table__.insert().values(**row))
        with pytest.raises(IntegrityError), connection.begin_nested():
            connection.execute(
                SaleInquiry.__table__.insert().values(**(row | {"request_id": "b"}))
            )
        connection.execute(SaleInquiry.__table__.update().values(status="withdrawn"))
        connection.execute(
            SaleInquiry.__table__.insert().values(**(row | {"request_id": "b"}))
        )
        migration.downgrade()
        assert "sale_inquiries" not in inspect(connection).get_table_names()
        assert connection.scalar(text("SELECT id FROM rental_inquiries")) == 42
    engine.dispose()


@pytest.mark.asyncio
@pytest.mark.skipif(
    not os.getenv("STAY_TEST_POSTGRES"), reason="CI runs PostgreSQL locking"
)
async def test_postgres_duplicate_sales_and_conflicting_viewing_decisions():
    import asyncio

    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
    from sqlalchemy.schema import CreateSchema, DropSchema

    from app.core.config import settings
    from app.db.base import Base
    from app.models.user import User
    from app.models.venue import Venue

    schema = "sales_test_" + uuid4().hex
    engine = create_async_engine(
        settings.DATABASE_URL,
        execution_options={"schema_translate_map": {None: schema}},
    )
    try:
        async with engine.begin() as connection:
            await connection.execute(CreateSchema(schema))
            tables = [
                model.__table__
                for model in (
                    User,
                    Venue,
                    PropertyListing,
                    SaleInquiry,
                    SaleMessage,
                    Notification,
                )
            ]
            await connection.run_sync(
                lambda sync: Base.metadata.create_all(sync, tables=tables)
            )
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        async with sessions() as db:
            db.add_all(
                [
                    User(
                        id=i,
                        email=f"sale{i}@example.com",
                        hashed_password="test",
                        role="owner" if i == 1 else "customer",
                    )
                    for i in (1, 2)
                ]
            )
            await db.flush()
            db.add(Venue(id=1, name="Property", address="Test", owner_id=1))
            await db.flush()
            db.add(
                PropertyListing(
                    id=1, **listing_data(offer_type="sale", booking_enabled=False)
                )
            )
            await db.commit()
        payload = data()

        async def create(body):
            async with sessions() as db:
                try:
                    return (
                        await RentalInquiryService(db, sale=True).create(
                            1, body, TENANT
                        )
                    ).id
                except HTTPException as error:
                    assert error.status_code == 409
                    return "conflict"

        repeated = await asyncio.wait_for(
            asyncio.gather(create(payload), create(payload)), 15
        )
        assert repeated[0] == repeated[1]
        assert await create(data()) == "conflict"
        inquiry_id = repeated[0]
        async with sessions() as db:
            assert await db.scalar(select(func.count(Notification.id))) == 1
            await RentalInquiryService(db, sale=True).update(
                inquiry_id,
                RentalInquiryUpdate(
                    version=1,
                    action="propose",
                    viewing_at=datetime.now(UTC) + timedelta(days=4),
                    owner_reply="Meet at the entrance.",
                ),
                OWNER,
            )

        async def decide(action):
            async with sessions() as db:
                try:
                    await RentalInquiryService(db, sale=True).update(
                        inquiry_id,
                        RentalInquiryUpdate(version=2, action=action),
                        TENANT,
                    )
                    return "ok"
                except HTTPException as error:
                    assert error.status_code == 409
                    return "conflict"

        results = await asyncio.wait_for(
            asyncio.gather(decide("confirm"), decide("decline")), 15
        )
        assert sorted(results) == ["conflict", "ok"]
    finally:
        async with engine.begin() as connection:
            await connection.execute(DropSchema(schema, cascade=True, if_exists=True))
        await engine.dispose()
