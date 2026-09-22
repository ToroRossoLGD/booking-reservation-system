import asyncio
import importlib.util
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import create_engine, func, inspect, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.schema import CreateSchema, DropSchema

from app.db.base import Base
from app.models.property_listing import PropertyListing
from app.models.rental_inquiry import RentalInquiry
from app.models.rental_message import RentalMessage
from app.models.user import User
from app.models.venue import Venue
from app.schemas.rental_inquiry import RentalInquiryUpdate
from app.schemas.rental_message import RentalMessageCreate, RentalMessagesRead
from app.services.rental_inquiry_service import RentalInquiryService
from app.services.rental_message_service import RentalMessageService
from tests.test_rental_inquiries import (
    OTHER,
    OWNER,
    TENANT,
    inquiry_data,
)
from tests.test_rental_inquiries import service as service


def message_data(body="Does Saturday afternoon work?", request_id=None):
    return RentalMessageCreate(body=body, request_id=request_id or uuid4())


@pytest.mark.asyncio
async def test_both_participants_chat_and_viewing_history_is_retained(service):
    inquiry = await service.create(1, inquiry_data(), TENANT)
    messages = RentalMessageService(service.db)
    first = await messages.send(inquiry.id, message_data(), TENANT)
    assert first.sender == "tenant"
    await messages.send(inquiry.id, message_data("Yes, Saturday is fine."), OWNER)
    assert inquiry.version == 1
    for day in (3, 4):
        await service.update(
            inquiry.id,
            RentalInquiryUpdate(
                version=inquiry.version,
                action="propose",
                owner_reply=f"Proposal {day}",
                viewing_at=datetime.now(timezone.utc) + timedelta(days=day),
            ),
            OWNER,
        )
    await service.update(
        inquiry.id,
        RentalInquiryUpdate(version=inquiry.version, action="confirm"),
        TENANT,
    )
    page = await messages.list(inquiry.id, OWNER)
    assert [item.kind for item in page["items"]] == [
        "message",
        "message",
        "message",
        "propose",
        "propose",
        "confirm",
    ]
    assert [item.body for item in page["items"] if item.kind == "propose"] == [
        "Proposal 3",
        "Proposal 4",
    ]
    assert not page["has_more"]
    assert page["items"][0].body == inquiry.message


@pytest.mark.asyncio
async def test_retry_does_not_duplicate_and_survives_closure(service):
    inquiry = await service.create(1, inquiry_data(), TENANT)
    messages = RentalMessageService(service.db)
    data = message_data()
    first = await messages.send(inquiry.id, data, TENANT)
    assert (await messages.send(inquiry.id, data, TENANT)).id == first.id
    with pytest.raises(HTTPException) as error:
        await messages.send(
            inquiry.id, message_data("Different message", data.request_id), TENANT
        )
    assert error.value.status_code == 409
    await service.update(
        inquiry.id, RentalInquiryUpdate(version=1, action="close"), OWNER
    )
    assert (await messages.send(inquiry.id, data, TENANT)).id == first.id
    with pytest.raises(HTTPException) as error:
        await messages.send(inquiry.id, message_data(), OWNER)
    assert error.value.status_code == 409
    assert len((await messages.list(inquiry.id, TENANT))["items"]) == 3


@pytest.mark.asyncio
async def test_outsider_cannot_read_send_or_mark_messages(service):
    inquiry = await service.create(1, inquiry_data(), TENANT)
    messages = RentalMessageService(service.db)
    for operation in (
        lambda: messages.list(inquiry.id, OTHER),
        lambda: messages.send(inquiry.id, message_data(), OTHER),
        lambda: messages.mark_read(
            inquiry.id, RentalMessagesRead(message_ids=[1]), OTHER
        ),
    ):
        with pytest.raises(HTTPException) as error:
            await operation()
        assert error.value.status_code == 404


@pytest.mark.asyncio
async def test_read_receipts_only_touch_selected_incoming_messages(service):
    inquiry = await service.create(1, inquiry_data(), TENANT)
    messages = RentalMessageService(service.db)
    original = (await messages.list(inquiry.id, OWNER))["items"][0]
    own = await messages.send(inquiry.id, message_data("Owner response"), OWNER)
    newer = await messages.send(
        inquiry.id, message_data("Another tenant message"), TENANT
    )
    another = await service.create(1, inquiry_data(), OTHER)
    foreign = (await messages.list(another.id, OWNER))["items"][0]
    assert (await service.list(OWNER, owner=True))["items"][1].unread_count == 2
    result = await messages.mark_read(
        inquiry.id,
        RentalMessagesRead(message_ids=[original.id, own.id, foreign.id]),
        OWNER,
    )
    assert result == {"unread_count": 1}
    items = {
        item.id: item for item in (await messages.list(inquiry.id, OWNER))["items"]
    }
    assert items[original.id].read_at is not None
    assert items[own.id].read_at is None and items[newer.id].read_at is None
    assert (await messages.list(another.id, OWNER))["items"][0].read_at is None
    read_time = items[original.id].read_at
    await messages.mark_read(
        inquiry.id, RentalMessagesRead(message_ids=[original.id]), OWNER
    )
    assert (await messages.list(inquiry.id, OWNER))["items"][0].read_at == read_time
    assert (await service.list(TENANT))["items"][0].unread_count == 1


@pytest.mark.asyncio
async def test_cursor_pagination_remains_stable_when_new_messages_arrive(service):
    inquiry = await service.create(1, inquiry_data(), TENANT)
    messages = RentalMessageService(service.db)
    for index in range(4):
        await messages.send(inquiry.id, message_data(f"Message {index}"), OWNER)
    newest = await messages.list(inquiry.id, TENANT, limit=2)
    assert [item.body for item in newest["items"]] == ["Message 2", "Message 3"]
    await messages.send(inquiry.id, message_data("Arrived later"), OWNER)
    older = await messages.list(
        inquiry.id, TENANT, before_id=newest["next_before_id"], limit=2
    )
    assert [item.body for item in older["items"]] == ["Message 0", "Message 1"]
    oldest = await messages.list(
        inquiry.id, TENANT, before_id=older["next_before_id"], limit=2
    )
    assert oldest["items"][0].body == inquiry.message
    assert not oldest["has_more"] and oldest["next_before_id"] is None


@pytest.mark.parametrize("body", ["", "   ", "x" * 3001])
def test_message_validation(body):
    with pytest.raises(ValidationError):
        message_data(body)


def test_migration_preserves_existing_messages_without_inventing_reply_dates():
    path = (
        Path(__file__).parents[1]
        / "alembic/versions/b27e4c8d9130_add_rental_conversations.py"
    )
    spec = importlib.util.spec_from_file_location("conversation_migration", path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    engine = create_engine("sqlite://")
    Base.metadata.create_all(
        engine,
        tables=[
            User.__table__,
            Venue.__table__,
            PropertyListing.__table__,
            RentalInquiry.__table__,
        ],
    )
    with engine.begin() as connection:
        connection.execute(
            RentalInquiry.__table__.insert().values(
                id=1,
                property_id=1,
                owner_id=1,
                user_id=2,
                request_id=str(uuid4()),
                title="Apartment",
                monthly_price_cents=60000,
                currency="EUR",
                move_in=inquiry_data().move_in,
                duration_months=12,
                message="Original tenant inquiry",
                owner_reply="Last existing reply",
            )
        )
        migration.op = Operations(MigrationContext.configure(connection))
        migration.upgrade()
        rows = (
            connection.execute(
                select(RentalMessage.__table__).order_by(RentalMessage.id)
            )
            .mappings()
            .all()
        )
        assert [row["body"] for row in rows] == [
            "Original tenant inquiry",
            "Last existing reply",
        ]
        assert rows[0]["created_at"] is not None
        assert rows[1]["created_at"] is None and rows[1]["kind"] == "legacy_reply"
        assert {
            column["name"]
            for column in inspect(connection).get_columns("rental_messages")
        } == set(RentalMessage.__table__.columns.keys())
        migration.downgrade()
        assert "rental_messages" not in inspect(connection).get_table_names()
        assert (
            connection.scalar(select(RentalInquiry.message))
            == "Original tenant inquiry"
        )
    engine.dispose()


@pytest.mark.asyncio
@pytest.mark.skipif(
    not os.getenv("STAY_TEST_POSTGRES"), reason="CI enables PostgreSQL locking tests"
)
async def test_postgres_concurrent_message_retries():
    from app.core.config import settings

    schema = "rental_chat_test_" + uuid4().hex
    engine = create_async_engine(
        settings.DATABASE_URL,
        execution_options={"schema_translate_map": {None: schema}},
    )
    tables = [
        User.__table__,
        Venue.__table__,
        PropertyListing.__table__,
        RentalInquiry.__table__,
        RentalMessage.__table__,
    ]
    try:
        async with engine.begin() as connection:
            await connection.execute(CreateSchema(schema))
            await connection.run_sync(
                lambda sync: Base.metadata.create_all(sync, tables=tables)
            )
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        async with sessions() as db:
            db.add_all(
                [
                    User(
                        id=i,
                        email=f"chat{i}@example.com",
                        hashed_password="test",
                        role="owner" if i == 1 else "customer",
                    )
                    for i in (1, 2)
                ]
            )
            await db.flush()
            db.add(Venue(id=1, owner_id=1, name="Chat apartment", address="Test"))
            await db.flush()
            db.add(
                PropertyListing(
                    id=1,
                    venue_id=1,
                    title="Apartment",
                    description="A long term rental apartment",
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
            await db.commit()
            inquiry = await RentalInquiryService(db).create(1, inquiry_data(), TENANT)
            inquiry_id = inquiry.id
        data = message_data()

        async def send():
            async with sessions() as db:
                return await RentalMessageService(db).send(inquiry_id, data, TENANT)

        first, second = await asyncio.gather(send(), send())
        assert first.id == second.id
        async with sessions() as db:
            assert await db.scalar(select(func.count(RentalMessage.id))) == 2
    finally:
        async with engine.begin() as connection:
            await connection.execute(DropSchema(schema, cascade=True, if_exists=True))
        await engine.dispose()
