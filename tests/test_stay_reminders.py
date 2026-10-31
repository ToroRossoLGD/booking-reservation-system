import asyncio
import importlib.util
import os
from contextlib import asynccontextmanager
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
from app.models.stay_reminder import StayReminderDelivery, StayReminderPreference
from app.services.stay_reminder_service import (
    run_stay_reminders,
    set_reminder_preference,
)
from app.services.stay_service import StayService
from tests import test_stays
from tests.test_stays import GUEST, OWNER, booking

service = test_stays.service
NOW = datetime(2026, 10, 2, 7, tzinfo=UTC)


def test_migration_roundtrip_and_beat_registration():
    from app.tasks.celery_app import celery_app

    spec = importlib.util.spec_from_file_location(
        "reminder_migration", Path("alembic/versions/f27b48cd3156_stay_reminders.py")
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    engine = create_engine("sqlite://")
    with engine.begin() as connection:
        module.op = Operations(MigrationContext.configure(connection))
        module.upgrade()
        assert "stay_reminder_deliveries" in inspect(connection).get_table_names()
        assert inspect(connection).get_unique_constraints("stay_reminder_deliveries")[
            0
        ]["column_names"] == ["stay_id", "user_id", "kind", "event_date"]
        module.downgrade()
        assert "stay_reminder_deliveries" not in inspect(connection).get_table_names()
    engine.dispose()
    assert (
        celery_app.conf.beat_schedule["send-stay-reminders"]["task"]
        == "send_stay_reminders"
    )


@pytest.fixture
def db(service, monkeypatch):
    session = service.repository.db.scalar.side_effect.__self__
    for table in (StayReminderPreference.__table__, StayReminderDelivery.__table__):
        table.create(session.get_bind())
    monkeypatch.setattr(settings, "STAY_REMINDERS_ENABLED", True)
    monkeypatch.setattr(settings, "DEMO_MODE", False)
    return service.repository.db


def sessions_for(db):
    @asynccontextmanager
    async def sessions():
        yield db

    return sessions


@pytest.mark.asyncio
async def test_arrival_departure_durable_dedup_and_opt_out(db, service):
    stay = await service.create(1, booking(), GUEST)
    sessions = sessions_for(db)
    assert await run_stay_reminders(sessions, NOW - timedelta(seconds=1)) == {"sent": 0}
    assert await run_stay_reminders(sessions, NOW) == {"sent": 2}
    reminders = list((await db.scalars(select(StayReminderDelivery))).all())
    assert {r.user_id for r in reminders} == {1, 2}
    assert {r.kind for r in reminders} == {"arrival"}
    await db.execute(delete(Notification))
    await db.commit()
    assert await run_stay_reminders(sessions, NOW) == {"sent": 0}
    await set_reminder_preference(db, GUEST.id, False)
    assert await run_stay_reminders(sessions, NOW + timedelta(days=3)) == {"sent": 1}
    row = (await db.scalars(select(Notification))).one()
    assert row.user_id == OWNER.id and row.action_path == "/owner/stays"
    assert "odlazak" in row.title and "Europe/Belgrade" in row.message
    await set_reminder_preference(db, GUEST.id, True)
    assert await run_stay_reminders(sessions, NOW + timedelta(days=3)) == {"sent": 1}
    assert stay.status == "confirmed"


@pytest.mark.asyncio
async def test_cancelled_changed_dates_and_disabled_worker(db, service, monkeypatch):
    stay = await service.create(1, booking(), GUEST)
    sessions = sessions_for(db)
    monkeypatch.setattr(settings, "STAY_REMINDERS_ENABLED", False)
    assert await run_stay_reminders(sessions, NOW) == {"sent": 0}
    monkeypatch.setattr(settings, "STAY_REMINDERS_ENABLED", True)
    monkeypatch.setattr(settings, "DEMO_MODE", True)
    assert await run_stay_reminders(sessions, NOW) == {"sent": 0}
    monkeypatch.setattr(settings, "DEMO_MODE", False)
    assert await run_stay_reminders(sessions, NOW) == {"sent": 2}
    stay.check_in += timedelta(days=1)
    await db.commit()
    assert await run_stay_reminders(sessions, NOW) == {"sent": 0}
    assert await run_stay_reminders(sessions, NOW + timedelta(days=1)) == {"sent": 2}
    await service.cancel(stay.id, GUEST)
    assert await run_stay_reminders(sessions, NOW + timedelta(days=3)) == {"sent": 0}


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "zone,now",
    [
        ("Pacific/Kiritimati", datetime(2026, 10, 1, 19, tzinfo=UTC)),
        ("Pacific/Pago_Pago", datetime(2026, 10, 2, 20, tzinfo=UTC)),
        ("Europe/Belgrade", NOW),
    ],
)
async def test_local_timezone_boundaries(db, service, zone, now):
    stay = await service.create(1, booking(), GUEST)
    stay.timezone = zone
    await db.commit()
    assert await run_stay_reminders(sessions_for(db), now - timedelta(seconds=1)) == {
        "sent": 0
    }
    assert await run_stay_reminders(sessions_for(db), now) == {"sent": 2}


@pytest.mark.asyncio
async def test_atomic_rollback_and_no_overdue_catchup(db, service):
    await service.create(1, booking(), GUEST)
    original = db.commit
    db.commit = AsyncMock(side_effect=RuntimeError("failed"))
    with pytest.raises(RuntimeError):
        await run_stay_reminders(sessions_for(db), NOW)
    await db.rollback()
    db.commit = original
    assert not list((await db.scalars(select(StayReminderDelivery))).all())
    assert await run_stay_reminders(sessions_for(db), NOW + timedelta(days=1)) == {
        "sent": 0
    }
    assert await run_stay_reminders(sessions_for(db), NOW) == {"sent": 2}


@pytest.mark.asyncio
async def test_preferences_auth_isolation_validation_and_demo(db, monkeypatch):
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_db] = lambda: db
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        path = "/notifications/stay-reminders"
        assert (await client.get(path)).status_code == 401
        app.dependency_overrides[get_current_user] = lambda: GUEST
        result = await client.get(path)
        assert result.json() == {"enabled": True}
        assert result.headers["cache-control"] == "private, no-store"
        assert (
            await client.put(path, json={"enabled": False, "user_id": 1})
        ).status_code == 422
        assert (await client.put(path, json={"enabled": "false"})).status_code == 422
        assert (await client.put(path, json={"enabled": False})).json() == {
            "enabled": False
        }
        app.dependency_overrides[get_current_user] = lambda: OWNER
        assert (await client.get(path)).json() == {"enabled": True}
        monkeypatch.setattr(settings, "DEMO_MODE", True)
        assert (await client.put(path, json={"enabled": False})).status_code == 403


@pytest.mark.asyncio
@pytest.mark.skipif(os.getenv("STAY_TEST_POSTGRES") != "1", reason="PostgreSQL opt-in")
async def test_postgres_concurrent_workers_and_cancel(monkeypatch):
    monkeypatch.setattr(settings, "STAY_REMINDERS_ENABLED", True)
    monkeypatch.setattr(settings, "DEMO_MODE", False)
    monkeypatch.setattr(
        StayService, "today", staticmethod(lambda zone: test_stays.TODAY)
    )
    schema = "stay_reminders_" + uuid4().hex
    engine = create_async_engine(
        settings.DATABASE_URL,
        execution_options={"schema_translate_map": {None: schema}},
    )
    tables = [
        test_stays.User.__table__,
        test_stays.Venue.__table__,
        test_stays.PropertyListing.__table__,
        test_stays.Resource.__table__,
        test_stays.Stay.__table__,
        test_stays.StayBlock.__table__,
        Notification.__table__,
        StayReminderPreference.__table__,
        StayReminderDelivery.__table__,
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
            stay = await StayService(db).create(1, booking(), GUEST)
        results = await asyncio.gather(
            run_stay_reminders(sessions, NOW), run_stay_reminders(sessions, NOW)
        )
        assert sum(result["sent"] for result in results) == 2
        async with sessions() as db:
            await StayService(db).cancel(stay.id, GUEST)
        assert await run_stay_reminders(sessions, NOW + timedelta(days=3)) == {
            "sent": 0
        }
    finally:
        async with engine.begin() as connection:
            await connection.execute(DropSchema(schema, cascade=True))
        await engine.dispose()
