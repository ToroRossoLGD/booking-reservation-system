import os
from datetime import timedelta
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy import func, select

from app.models.notification import Notification
from app.models.property_listing import PropertyListing
from app.models.stay_date_change import StayDateChange
from app.schemas.stay import StayDates
from app.schemas.stay_date_change import StayDateChangeCreate
from app.services.stay_date_change_service import StayDateChangeService
from tests.test_stays import GUEST, OTHER, OWNER, TODAY, booking
from tests.test_stays import service as stay_service  # noqa: F401


@pytest.fixture
def service(stay_service):  # noqa: F811 - imported pytest fixture
    db = stay_service.repository.db
    StayDateChange.__table__.create(db.commit.side_effect.__self__.get_bind())
    return StayDateChangeService(db)


def dates(start=4, end=7):
    return StayDates(
        check_in=TODAY + timedelta(days=start),
        check_out=TODAY + timedelta(days=end),
        guests=2,
    )


async def request(service, stay, data=None):
    data = data or dates()
    quote = await service.quote(stay.id, data, GUEST)
    body = StayDateChangeCreate(**data.model_dump(), request_id=uuid4(), quote=quote)
    return body, await service.create(stay.id, body, GUEST)


@pytest.mark.asyncio
async def test_proposal_keeps_old_dates_approval_rechecks_and_retries(service):
    stay = await service.stays.create(1, booking(), GUEST)
    body, change = await request(service, stay)
    assert stay.check_in == booking().check_in
    assert (await service.create(stay.id, body, GUEST)).id == change.id
    # Pending requests do not hold the proposed dates.
    await service.stays.quote(2, dates(5, 8))
    with pytest.raises(HTTPException) as blocked:
        await service.stays.quote(2, dates(2, 5))
    assert blocked.value.status_code == 409
    accepted = await service.decide(stay.id, change.id, "accept", OWNER)
    assert accepted.status == "accepted"
    assert stay.check_in == dates().check_in
    assert stay.check_out == dates().check_out
    assert accepted.original.check_in == booking().check_in
    assert stay.nightly_prices == body.quote.model_dump(mode="json")["nightly_prices"]
    assert (
        await service.decide(stay.id, change.id, "accept", OWNER)
    ).status == "accepted"
    assert (await service.create(stay.id, body, GUEST)).id == change.id
    assert await service.db.scalar(select(func.count(Notification.id))) == 6

    await service.stays.quote(2, dates(1, 3))
    with pytest.raises(HTTPException):
        await service.stays.quote(2, dates())


@pytest.mark.asyncio
async def test_stale_quote_terms_and_withdrawn_listing_cannot_be_accepted(service):
    stay = await service.stays.create(1, booking(), GUEST)
    quote = await service.quote(stay.id, dates(), GUEST)
    body = StayDateChangeCreate(**dates().model_dump(), request_id=uuid4(), quote=quote)
    listing = await service.db.get(PropertyListing, 1)
    listing.check_in_time, listing.check_out_time = "15:00", "10:00"
    await service.db.commit()
    with pytest.raises(HTTPException) as error:
        await service.create(stay.id, body, GUEST)
    assert error.value.status_code == 409
    _, change = await request(service, stay)
    listing.is_published = False
    await service.db.commit()
    with pytest.raises(HTTPException) as error:
        await service.decide(stay.id, change.id, "accept", OWNER)
    assert error.value.status_code == 404
    assert (
        await service.decide(stay.id, change.id, "decline", OWNER)
    ).status == "declined"


def test_migration_roundtrip_and_single_pending_constraint():
    import importlib.util
    from pathlib import Path

    from alembic.migration import MigrationContext
    from alembic.operations import Operations
    from sqlalchemy import create_engine, inspect, text
    from sqlalchemy.exc import IntegrityError

    path = (
        Path(__file__).parents[1]
        / "alembic/versions/fcd806435790_add_stay_date_changes.py"
    )
    spec = importlib.util.spec_from_file_location("stay_change_migration", path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    engine = create_engine("sqlite://")
    with engine.begin() as connection:
        connection.execute(text("PRAGMA foreign_keys=ON"))
        connection.execute(text("CREATE TABLE stays (id INTEGER PRIMARY KEY)"))
        connection.execute(text("INSERT INTO stays VALUES (1)"))
        migration.op = Operations(MigrationContext.configure(connection))
        migration.upgrade()
        assert {
            c["name"] for c in inspect(connection).get_columns("stay_date_changes")
        } == set(StayDateChange.__table__.columns.keys())
        insert = text(
            "INSERT INTO stay_date_changes "
            "(stay_id, request_id, check_in, check_out, original, quote, "
            "status, created_at) "
            "VALUES (1, :request, '2026-10-10', '2026-10-13', '{}', '{}', "
            ":status, CURRENT_TIMESTAMP)"
        )
        connection.execute(insert, {"request": "first", "status": "pending"})
        with pytest.raises(IntegrityError), connection.begin_nested():
            connection.execute(insert, {"request": "second", "status": "pending"})
        connection.execute(insert, {"request": "past", "status": "declined"})
        connection.execute(text("DELETE FROM stays WHERE id=1"))
        assert connection.scalar(text("SELECT count(*) FROM stay_date_changes")) == 0
        migration.downgrade()
        assert "stay_date_changes" not in inspect(connection).get_table_names()
        assert "stays" in inspect(connection).get_table_names()
    engine.dispose()


@pytest.mark.asyncio
async def test_conflicting_booking_and_price_change_leave_original_untouched(service):
    stay = await service.stays.create(1, booking(), GUEST)
    _, change = await request(service, stay, dates(8, 11))
    conflict = await service.stays.create(
        2, booking(**dates(8, 11).model_dump()), OTHER
    )
    with pytest.raises(HTTPException) as error:
        await service.decide(stay.id, change.id, "accept", OWNER)
    assert error.value.status_code == 409
    assert stay.check_in == booking().check_in
    await service.stays.cancel(conflict.id, OTHER)
    listing = await service.db.get(PropertyListing, 1)
    listing.price_cents = 7000
    await service.db.commit()
    with pytest.raises(HTTPException) as error:
        await service.decide(stay.id, change.id, "accept", OWNER)
    assert error.value.status_code == 409
    assert stay.total_cents == 19500
    assert (await service.list(stay.id, GUEST)).items[0].status == "pending"
    await service.decide(stay.id, change.id, "withdraw", GUEST)
    _, replacement = await request(service, stay, dates(8, 11))
    await service.decide(stay.id, replacement.id, "accept", OWNER)
    assert stay.total_cents == 21000


@pytest.mark.asyncio
async def test_permissions_pending_cap_and_request_payload_binding(service):
    stay = await service.stays.create(1, booking(), GUEST)
    body, change = await request(service, stay)
    for call in (
        service.list(stay.id, OTHER),
        service.quote(stay.id, dates(), OTHER),
        service.create(stay.id, body, OTHER),
    ):
        with pytest.raises(HTTPException) as error:
            await call
        assert error.value.status_code == 404
    for who, action in ((GUEST, "accept"), (GUEST, "decline"), (OWNER, "withdraw")):
        with pytest.raises(HTTPException) as error:
            await service.decide(stay.id, change.id, action, who)
        assert error.value.status_code == 403
    for replacement in (
        body.model_copy(update={"request_id": uuid4()}),
        body.model_copy(update={"check_out": body.check_out + timedelta(days=1)}),
    ):
        with pytest.raises(HTTPException) as error:
            await service.create(stay.id, replacement, GUEST)
        assert error.value.status_code == 409
    await service.decide(stay.id, change.id, "decline", OWNER)
    with pytest.raises(HTTPException):
        await service.decide(stay.id, change.id, "accept", OWNER)
    _, newer = await request(service, stay)
    assert (await service.list(stay.id, OWNER, limit=1)).items[0].id == newer.id
    assert (await service.list(stay.id, OWNER, limit=1)).has_next


@pytest.mark.asyncio
async def test_cancelled_and_arrived_stays_expire_pending_requests(
    service, monkeypatch
):
    stay = await service.stays.create(1, booking(), GUEST)
    _, change = await request(service, stay)
    await service.stays.cancel(stay.id, GUEST)
    assert (await service.list(stay.id, OWNER)).items[0].status == "expired"
    with pytest.raises(HTTPException):
        await service.decide(stay.id, change.id, "accept", OWNER)
    stay = await service.stays.create(1, booking(), GUEST)
    _, change = await request(service, stay)
    monkeypatch.setattr(service.stays, "today", lambda zone: stay.check_in)
    assert (await service.list(stay.id, GUEST)).items[0].status == "expired"
    with pytest.raises(HTTPException):
        await service.decide(stay.id, change.id, "accept", OWNER)


@pytest.mark.asyncio
async def test_alias_preparation_blocks_rules_and_guest_count(service):
    from app.schemas.stay_block import StayBlockCreate
    from app.services.stay_block_service import StayBlockService

    stay = await service.stays.create(1, booking(), GUEST)
    listing = await service.db.get(PropertyListing, 2)
    listing.preparation_days = 2
    await service.db.commit()
    await service.stays.create(2, booking(**dates(10, 13).model_dump()), OTHER)
    with pytest.raises(HTTPException) as error:
        await service.quote(stay.id, dates(6, 9), GUEST)
    assert error.value.status_code == 409
    await StayBlockService(service.db).create(
        2,
        StayBlockCreate(
            check_in=TODAY + timedelta(days=15),
            check_out=TODAY + timedelta(days=18),
            reason="Repairs",
            request_id=uuid4(),
        ),
        OWNER,
    )
    with pytest.raises(HTTPException):
        await service.quote(stay.id, dates(15, 18), GUEST)
    with pytest.raises(HTTPException):
        await service.quote(stay.id, dates().model_copy(update={"guests": 3}), GUEST)
    listing = await service.db.get(PropertyListing, 1)
    listing.advance_notice_days = 8
    await service.db.commit()
    with pytest.raises(HTTPException) as error:
        await service.quote(stay.id, dates(), GUEST)
    assert error.value.status_code == 400


@pytest.mark.asyncio
async def test_failed_commit_rolls_back_dates_history_and_notifications(service):
    stay = await service.stays.create(1, booking(), GUEST)
    _, change = await request(service, stay)
    stay_id = stay.id
    commit = service.db.commit.side_effect
    service.db.commit.side_effect = RuntimeError("database unavailable")
    with pytest.raises(RuntimeError):
        await service.decide(stay_id, change.id, "accept", OWNER)
    await service.db.rollback()
    service.db.commit.side_effect = commit
    assert (await service.repository.get(stay_id)).check_in == booking().check_in
    assert (await service.list(stay_id, OWNER)).items[0].status == "pending"
    assert await service.db.scalar(select(func.count(Notification.id))) == 4
    await service.decide(stay_id, change.id, "accept", OWNER)
    assert await service.db.scalar(select(func.count(Notification.id))) == 6


@pytest.mark.asyncio
@pytest.mark.skipif(
    not os.getenv("STAY_TEST_POSTGRES"), reason="CI runs PostgreSQL locking"
)
@pytest.mark.parametrize("competitor", [GUEST, OTHER])
async def test_postgres_approval_races_alias_booking(monkeypatch, competitor):
    import asyncio

    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
    from sqlalchemy.schema import CreateSchema, DropSchema

    from app.core.config import settings
    from app.db.base import Base
    from app.models.resource import Resource
    from app.models.stay import Stay
    from app.models.stay_block import StayBlock
    from app.models.user import User
    from app.models.venue import Venue
    from app.services.stay_service import StayService
    from tests.test_stays import seed

    monkeypatch.setattr(StayService, "today", staticmethod(lambda zone: TODAY))
    schema = "stay_change_test_" + uuid4().hex
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
                    Resource,
                    Stay,
                    StayBlock,
                    Notification,
                    StayDateChange,
                )
            ]
            await connection.run_sync(
                lambda sync: Base.metadata.create_all(sync, tables=tables)
            )
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        async with sessions() as db:
            await db.run_sync(seed)
            service = StayDateChangeService(db)
            stay = await service.stays.create(1, booking(), GUEST)
            _, change = await request(service, stay, dates(8, 11))
            stay_id = stay.id

        async def approve():
            async with sessions() as db:
                try:
                    await StayDateChangeService(db).decide(
                        stay_id, change.id, "accept", OWNER
                    )
                    return "accepted"
                except HTTPException as error:
                    assert error.status_code == 409
                    return "conflict"

        async def book():
            async with sessions() as db:
                try:
                    await StayService(db).create(
                        2, booking(**dates(8, 11).model_dump()), competitor
                    )
                    return "booked"
                except HTTPException as error:
                    assert error.status_code == 409
                    return "conflict"

        results = await asyncio.wait_for(asyncio.gather(approve(), book()), timeout=15)
        assert results.count("conflict") == 1
        async with sessions() as db:
            assert (
                await db.scalar(
                    select(func.count(Stay.id)).where(
                        Stay.status == "confirmed",
                        Stay.check_in == dates(8, 11).check_in,
                    )
                )
                == 1
            )
    finally:
        async with engine.begin() as connection:
            await connection.execute(DropSchema(schema, cascade=True, if_exists=True))
        await engine.dispose()


def test_date_change_routes_require_authentication():
    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as client:
        assert client.get("/stays/1/date-changes").status_code == 401
        for path in ("date-change-quote", "date-changes", "date-changes/1/decision"):
            assert client.post("/stays/1/" + path, json={}).status_code == 401
