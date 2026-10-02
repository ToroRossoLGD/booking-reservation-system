import os
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.db.base import Base
from app.models.notification import Notification
from app.models.property_listing import PropertyListing
from app.models.saved_search import SavedSearch
from app.models.saved_search_match import SavedSearchMatch
from app.models.stay import Stay
from app.models.stay_block import StayBlock
from app.models.user import User
from app.models.venue import Venue
from app.repositories.property_listing_repository import PropertyListingRepository
from app.schemas.saved_search import SavedSearchWrite
from app.services.saved_search_alert_service import SavedSearchAlertService
from app.services.saved_search_service import SavedSearchService
from tests.test_stays import listing_data

TABLES = [
    User.__table__,
    Venue.__table__,
    PropertyListing.__table__,
    Stay.__table__,
    StayBlock.__table__,
    SavedSearch.__table__,
    SavedSearchMatch.__table__,
    Notification.__table__,
]
USER = SimpleNamespace(id=2)


@pytest.fixture
def store():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine, tables=TABLES)
    with Session(engine, expire_on_commit=False) as session:
        session.add_all(
            [
                User(
                    id=i,
                    email=f"alert{i}@example.com",
                    hashed_password="test",
                    role="owner" if i == 1 else "customer",
                )
                for i in (1, 2)
            ]
        )
        session.flush()
        session.add(Venue(id=1, name="Apartment", address="Test", owner_id=1))
        session.commit()
        db = MagicMock()
        db.add = session.add
        for method in (
            "scalar",
            "scalars",
            "commit",
            "refresh",
            "delete",
            "rollback",
            "flush",
        ):
            setattr(db, method, AsyncMock(side_effect=getattr(session, method)))
        yield session, db, SavedSearchService(db), SavedSearchAlertService(db)
    engine.dispose()


async def publish(db, **changes):
    listing = PropertyListing(**listing_data(**changes))
    return await PropertyListingRepository(db).save(listing)


@pytest.mark.asyncio
async def test_failed_batch_can_retry_without_lost_or_duplicate_notification(store):
    session, db, searches, alerts = store
    search = await searches.save(SavedSearchWrite(name="All", path="/"), USER)
    await searches.set_alerts(search.id, True, USER)
    search_id = search.id
    await publish(db)
    commit = db.commit.side_effect
    db.commit.side_effect = RuntimeError("commit failed")
    with pytest.raises(RuntimeError):
        await alerts.process(search_id)
    await db.rollback()
    db.commit.side_effect = commit
    assert not session.scalars(select(Notification)).all()
    assert not session.scalars(select(SavedSearchMatch)).all()
    assert await alerts.process(search_id) == 1
    assert await alerts.process(search_id) == 0


@pytest.mark.asyncio
async def test_explicit_optin_matching_dedup_and_rename(store):
    session, db, searches, alerts = store
    old = await publish(db)
    old.first_published_at = datetime.now(UTC) - timedelta(seconds=1)
    session.commit()
    search = await searches.save(
        SavedSearchWrite(name="Mountain", path="/?city=Zlatibor&offer_type=short_stay"),
        USER,
    )
    assert not search.alerts_enabled
    assert await alerts.candidates() == []

    await searches.set_alerts(search.id, True, USER)
    since = search.alerts_since
    await searches.set_alerts(search.id, True, USER)
    assert search.alerts_since == since
    new = await publish(db, title="New apartment")
    miss = await publish(db, city="Beograd")
    assert await alerts.candidates() == [search.id]
    assert await alerts.process(search.id) == 1
    notification = session.scalars(select(Notification)).one()
    assert notification.user_id == 2
    assert notification.action_path == f"/properties/{new.id}"
    assert session.get(SavedSearchMatch, (search.id, old.id)) is None
    assert not session.get(SavedSearchMatch, (search.id, miss.id)).matched
    await searches.save(SavedSearchWrite(name="Renamed", path=search.path), USER)
    assert search.alerts_enabled and search.alerts_since == since
    assert await alerts.process(search.id) == 0
    # Deleting the notification does not erase processing history.
    session.delete(notification)
    session.commit()
    assert await alerts.process(search.id) == 0
    assert await alerts.candidates() == []


def test_alert_migration_preserves_data_and_cascades():
    import importlib.util
    from pathlib import Path

    from alembic.migration import MigrationContext
    from alembic.operations import Operations
    from sqlalchemy import inspect, text

    path = (
        Path(__file__).parents[1]
        / "alembic/versions/ebc79532468f_add_saved_search_alerts.py"
    )
    spec = importlib.util.spec_from_file_location("alert_migration", path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    engine = create_engine("sqlite://")
    with engine.begin() as connection:
        connection.execute(text("PRAGMA foreign_keys=ON"))
        connection.execute(text("CREATE TABLE saved_searches (id INTEGER PRIMARY KEY)"))
        connection.execute(
            text(
                "CREATE TABLE property_listings "
                "(id INTEGER PRIMARY KEY, is_published BOOLEAN)"
            )
        )
        connection.execute(text("INSERT INTO saved_searches VALUES (1)"))
        connection.execute(
            text("INSERT INTO property_listings VALUES (1, true), (2, false)")
        )
        migration.op = Operations(MigrationContext.configure(connection))
        migration.upgrade()
        assert connection.execute(
            text("SELECT alerts_enabled, alerts_since FROM saved_searches")
        ).one() == (False, None)
        assert connection.scalar(
            text("SELECT first_published_at FROM property_listings WHERE id=1")
        )
        assert (
            connection.scalar(
                text("SELECT first_published_at FROM property_listings WHERE id=2")
            )
            is None
        )
        connection.execute(text("INSERT INTO saved_search_matches VALUES (1, 1, true)"))
        connection.execute(text("DELETE FROM saved_searches WHERE id=1"))
        assert connection.scalar(text("SELECT count(*) FROM saved_search_matches")) == 0
        migration.downgrade()
        assert "saved_search_matches" not in inspect(connection).get_table_names()
        assert connection.scalar(text("SELECT count(*) FROM property_listings")) == 2
    engine.dispose()


@pytest.mark.asyncio
@pytest.mark.skipif(
    not os.getenv("STAY_TEST_POSTGRES"), reason="CI runs PostgreSQL locking"
)
async def test_postgres_overlapping_workers_deliver_once():
    import asyncio
    from uuid import uuid4

    from sqlalchemy import func
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
    from sqlalchemy.schema import CreateSchema, DropSchema

    from app.core.config import settings

    schema = "search_alert_test_" + uuid4().hex
    engine = create_async_engine(
        settings.DATABASE_URL,
        execution_options={"schema_translate_map": {None: schema}},
    )
    try:
        async with engine.begin() as connection:
            await connection.execute(CreateSchema(schema))
            await connection.run_sync(
                lambda sync: Base.metadata.create_all(sync, tables=TABLES)
            )
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        async with sessions() as db:
            db.add_all(
                [
                    User(
                        id=i,
                        email=f"alerts{i}@example.com",
                        hashed_password="test",
                        role="customer",
                    )
                    for i in (1, 2)
                ]
            )
            await db.flush()
            db.add(Venue(id=1, owner_id=1, name="Apartment", address="Test"))
            await db.commit()
            service = SavedSearchService(db)
            search = await service.save(SavedSearchWrite(name="All", path="/"), USER)
            await service.set_alerts(search.id, True, USER)
            search_id = search.id
            await publish(db)

        async def process():
            async with sessions() as db:
                return await SavedSearchAlertService(db).process(search_id)

        assert sum(await asyncio.gather(process(), process())) == 1
        async with sessions() as db:
            assert await db.scalar(select(func.count(Notification.id))) == 1
            assert (
                await db.scalar(select(func.count()).select_from(SavedSearchMatch)) == 1
            )
            assert await SavedSearchAlertService(db).candidates() == []
    finally:
        async with engine.begin() as connection:
            await connection.execute(DropSchema(schema, cascade=True, if_exists=True))
        await engine.dispose()


@pytest.mark.asyncio
async def test_optout_reenable_no_backfill_and_ownership(store):
    session, db, searches, alerts = store
    search = await searches.save(SavedSearchWrite(name="All", path="/"), USER)
    with pytest.raises(HTTPException) as error:
        await searches.set_alerts(search.id, True, SimpleNamespace(id=1))
    assert error.value.status_code == 404
    await searches.set_alerts(search.id, True, USER)
    await searches.set_alerts(search.id, False, USER)
    paused_listing = await publish(db)
    paused_listing.first_published_at = datetime.now(UTC) - timedelta(seconds=1)
    session.commit()
    assert await alerts.process(search.id) == 0
    await searches.set_alerts(search.id, True, USER)
    assert await alerts.process(search.id) == 0
    await publish(db)
    assert await alerts.process(search.id) == 1
    assert len(session.scalars(select(Notification)).all()) == 1


@pytest.mark.asyncio
async def test_first_publication_only_withdrawal_and_own_listings(store):
    session, db, searches, alerts = store
    search = await searches.save(SavedSearchWrite(name="All", path="/"), USER)
    own = await searches.save(
        SavedSearchWrite(name="Own", path="/"), SimpleNamespace(id=1)
    )
    await searches.set_alerts(search.id, True, USER)
    await searches.set_alerts(own.id, True, SimpleNamespace(id=1))
    listing = await publish(db, is_published=False)
    assert listing.first_published_at is None
    listing.is_published = True
    await PropertyListingRepository(db).save(listing)
    first_time = listing.first_published_at
    assert await alerts.process(own.id) == 0
    assert await alerts.candidates() == [search.id]
    assert await alerts.process(search.id) == 1
    listing.is_published = False
    await PropertyListingRepository(db).save(listing)
    listing.is_published = True
    await PropertyListingRepository(db).save(listing)
    assert listing.first_published_at == first_time
    assert await alerts.process(search.id) == 0
    withdrawn = await publish(db)
    withdrawn.is_published = False
    await PropertyListingRepository(db).save(withdrawn)
    assert await alerts.process(search.id) == 0


@pytest.mark.asyncio
async def test_date_price_filters_and_batch_progress(store):
    session, db, searches, alerts = store
    today = datetime.now(UTC).date()
    start, end = today + timedelta(days=5), today + timedelta(days=8)
    path = (
        f"/?offer_type=short_stay&check_in={start}&check_out={end}&guests=2"
        "&currency=EUR&max_price_cents=7000&rooms=0&has_parking=false"
    )
    search = await searches.save(SavedSearchWrite(name="Trip", path=path), USER)
    await searches.set_alerts(search.id, True, USER)
    await publish(
        db,
        rooms=0,
        has_parking=False,
        seasonal_rates=[
            {"start": str(start), "end": str(end), "price_cents": 9000, "label": "Peak"}
        ],
    )
    match = await publish(db, rooms=0, has_parking=False)
    assert await alerts.process(search.id, limit=1) == 0
    assert await alerts.candidates() == [search.id]
    assert await alerts.process(search.id, limit=1) == 1
    notification = session.scalars(select(Notification)).one()
    assert (
        notification.action_path
        == f"/properties/{match.id}?check_in={start}&check_out={end}&guests=2"
    )
    assert await alerts.candidates() == []
