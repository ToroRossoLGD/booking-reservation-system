import asyncio
import importlib.util
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine, delete, inspect, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.schema import CreateSchema, DropSchema

from app.api.routers.notifications import router
from app.core.config import settings
from app.core.dependencies import get_current_user
from app.db.base import Base
from app.db.session import get_db
from app.models.notification import Notification
from app.models.rental_inquiry import RentalInquiry
from app.models.sale_inquiry import SaleInquiry
from app.models.viewing_reminder import (
    ViewingReminderDelivery,
    ViewingReminderPreference,
)
from app.services.viewing_reminder_service import (
    run_viewing_reminders,
    set_viewing_preference,
)
from tests import test_stays
from tests.test_stay_reminders import sessions_for

service = test_stays.service
NOW = datetime(2026, 11, 1, 10, tzinfo=UTC)
TABLES = [
    RentalInquiry.__table__,
    SaleInquiry.__table__,
    ViewingReminderPreference.__table__,
    ViewingReminderDelivery.__table__,
]


@pytest.fixture
def db(service, monkeypatch):
    db = service.repository.db
    session = db.scalar.side_effect.__self__
    for table in TABLES:
        table.create(session.get_bind())
    monkeypatch.setattr(settings, "VIEWING_REMINDERS_ENABLED", True)
    monkeypatch.setattr(settings, "DEMO_MODE", False)
    return db


async def seed_inquiry(db, sale=False, **changes):
    values = dict(
        property_id=1,
        owner_id=1,
        user_id=2,
        request_id=str(uuid4()),
        title="Test apartment",
        currency="EUR",
        message="Private inquiry",
        status="viewing_confirmed",
        viewing_at=NOW + timedelta(hours=24),
    )
    if sale:
        values["asking_price_cents"] = 10000000
    else:
        values.update(monthly_price_cents=60000, move_in=NOW.date(), duration_months=12)
    row = (SaleInquiry if sale else RentalInquiry)(**(values | changes))
    db.add(row)
    await db.commit()
    return row


@pytest.mark.asyncio
@pytest.mark.parametrize("sale", [False, True])
async def test_window_recipients_dismissal_and_changed_time(db, sale):
    row = await seed_inquiry(db, sale)
    sessions = sessions_for(db)
    assert await run_viewing_reminders(sessions, NOW - timedelta(seconds=1)) == {
        "sent": 0
    }
    assert await run_viewing_reminders(sessions, NOW) == {"sent": 2}
    notices = list((await db.scalars(select(Notification))).all())
    assert {n.user_id for n in notices} == {1, 2}
    assert {n.action_path for n in notices} == (
        {"/sales", "/owner/sales"} if sale else {"/rentals", "/owner/rentals"}
    )
    assert all(
        "UTC" in n.message and "Private inquiry" not in n.message for n in notices
    )
    await db.execute(delete(Notification))
    await db.commit()
    assert await run_viewing_reminders(sessions, NOW) == {"sent": 0}
    row.viewing_at += timedelta(minutes=30)
    row.status = "viewing_proposed"
    await db.commit()
    assert await run_viewing_reminders(sessions, NOW + timedelta(hours=1)) == {
        "sent": 0
    }
    row.status = "viewing_confirmed"
    await db.commit()
    assert await run_viewing_reminders(sessions, NOW + timedelta(hours=1)) == {
        "sent": 2
    }


@pytest.mark.asyncio
@pytest.mark.parametrize("status", ["open", "viewing_proposed", "closed", "withdrawn"])
async def test_inactive_inquiries_are_skipped(db, status):
    await seed_inquiry(db, status=status)
    assert await run_viewing_reminders(sessions_for(db), NOW) == {"sent": 0}


@pytest.mark.asyncio
async def test_opt_out_expired_demo_and_atomic_rollback(db, monkeypatch):
    await seed_inquiry(db)
    sessions = sessions_for(db)
    assert await run_viewing_reminders(sessions, NOW + timedelta(hours=24)) == {
        "sent": 0
    }
    await set_viewing_preference(db, 2, False)
    monkeypatch.setattr(settings, "DEMO_MODE", True)
    assert await run_viewing_reminders(sessions, NOW) == {"sent": 0}
    monkeypatch.setattr(settings, "DEMO_MODE", False)
    original = db.commit
    db.commit = AsyncMock(side_effect=RuntimeError("failed"))
    with pytest.raises(RuntimeError):
        await run_viewing_reminders(sessions, NOW)
    await db.rollback()
    db.commit = original
    assert not list((await db.scalars(select(ViewingReminderDelivery))).all())
    assert not list((await db.scalars(select(Notification))).all())
    assert await run_viewing_reminders(sessions, NOW) == {"sent": 1}
    await set_viewing_preference(db, 2, True)
    assert await run_viewing_reminders(sessions, NOW) == {"sent": 1}


@pytest.mark.asyncio
async def test_preference_auth_validation_and_isolation(db, monkeypatch):
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_db] = lambda: db
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        path = "/notifications/viewing-reminders"
        assert (await client.get(path)).status_code == 401
        app.dependency_overrides[get_current_user] = lambda: test_stays.GUEST
        response = await client.get(path)
        assert response.json() == {"enabled": True}
        assert response.headers["cache-control"] == "private, no-store"
        assert (await client.put(path, json={"enabled": "false"})).status_code == 422
        assert (
            await client.put(path, json={"enabled": False, "user_id": 1})
        ).status_code == 422
        assert (await client.put(path, json={"enabled": False})).json() == {
            "enabled": False
        }
        app.dependency_overrides[get_current_user] = lambda: test_stays.OWNER
        assert (await client.get(path)).json() == {"enabled": True}
        monkeypatch.setattr(settings, "DEMO_MODE", True)
        assert (await client.put(path, json={"enabled": False})).status_code == 403


def test_migration_and_schedule():
    from app.tasks.celery_app import celery_app

    spec = importlib.util.spec_from_file_location(
        "viewing_migration", Path("alembic/versions/a38c59de4267_viewing_reminders.py")
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    engine = create_engine("sqlite://")
    with engine.begin() as connection:
        module.op = Operations(MigrationContext.configure(connection))
        module.upgrade()
        assert (
            len(
                inspect(connection).get_unique_constraints(
                    "viewing_reminder_deliveries"
                )
            )
            == 2
        )
        module.downgrade()
        assert not inspect(connection).get_table_names()
    engine.dispose()
    assert (
        celery_app.conf.beat_schedule["send-viewing-reminders"]["task"]
        == "send_viewing_reminders"
    )


@pytest.mark.asyncio
@pytest.mark.skipif(os.getenv("STAY_TEST_POSTGRES") != "1", reason="PostgreSQL opt-in")
async def test_postgres_concurrent_workers(monkeypatch):
    monkeypatch.setattr(settings, "VIEWING_REMINDERS_ENABLED", True)
    monkeypatch.setattr(settings, "DEMO_MODE", False)
    schema = "viewing_reminders_" + uuid4().hex
    engine = create_async_engine(
        settings.DATABASE_URL,
        execution_options={"schema_translate_map": {None: schema}},
    )
    tables = [
        test_stays.User.__table__,
        test_stays.Venue.__table__,
        test_stays.PropertyListing.__table__,
        Notification.__table__,
        *TABLES,
    ]
    try:
        async with engine.begin() as connection:
            await connection.execute(CreateSchema(schema))
            await connection.run_sync(
                lambda sync: Base.metadata.create_all(sync, tables=tables)
            )
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        async with sessions() as db:
            await db.run_sync(test_stays.seed)
            await seed_inquiry(db)
            await seed_inquiry(db, True)
        results = await asyncio.gather(
            run_viewing_reminders(sessions, NOW), run_viewing_reminders(sessions, NOW)
        )
        assert sum(result["sent"] for result in results) == 4
    finally:
        async with engine.begin() as connection:
            await connection.execute(DropSchema(schema, cascade=True))
        await engine.dispose()
