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
from cryptography.fernet import Fernet
from fastapi import FastAPI, HTTPException
from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine, inspect, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.schema import CreateSchema, DropSchema

from app.api.routers.stay_blocks import router
from app.core.config import settings
from app.core.dependencies import get_current_user
from app.db.base import Base
from app.db.session import get_db
from app.models.notification import Notification
from app.models.occupancy_import_run import OccupancyImportRun
from app.models.occupancy_source import OccupancySource, OccupancySourceBlock
from app.models.occupancy_sync import OccupancySync
from app.models.stay_block import StayBlock
from app.models.venue import Venue
from app.services import occupancy_sync_service as module
from app.services.stay_service import StayService
from app.tasks.celery_app import celery_app
from tests import test_occupancy_import, test_occupancy_sources, test_stays
from tests.test_occupancy_import import calendar, event
from tests.test_stays import GUEST, OWNER, TODAY, booking

stay_service = test_stays.service
importer = test_occupancy_import.importer
sources = test_occupancy_sources.sources
URL = "https://calendar.example/export?token=private"


@pytest.fixture
def setup(sources, monkeypatch):
    monkeypatch.setattr(settings, "OCCUPANCY_SYNC_ENABLED", True)
    monkeypatch.setattr(settings, "OCCUPANCY_SYNC_KEY", Fernet.generate_key().decode())
    monkeypatch.setattr(settings, "OCCUPANCY_IMPORT_ALLOWED_HOSTS", "calendar.example")
    monkeypatch.setattr(settings, "PROPERTY_RATE_LIMIT_ENABLED", False)
    monkeypatch.setattr(settings, "APP_ENV", "test")
    return module.OccupancySyncService(sources.db)


def sessions_for(service):
    @asynccontextmanager
    async def sessions():
        yield service.db

    return sessions


async def connect(service, allow_empty=False):
    source = await service.create(1, OWNER, "Automatic")
    await service.configure(1, OWNER, source.id, "connect", URL, allow_empty)
    return source


async def due(service, source_id):
    row = await service.connection(source_id)
    row.next_run_at = datetime.now(UTC) - timedelta(minutes=1)
    await service.db.commit()


@pytest.mark.asyncio
async def test_health_notifications_are_private_transition_based_and_atomic(setup):
    source = await connect(setup)
    sessions = sessions_for(setup)

    async def finish_failure():
        await due(setup, source.id)
        job = await module.claim(sessions)
        await module.finish(sessions, job, None, "fetch_error")

    async def notices():
        return list(
            (
                await setup.db.scalars(select(Notification).order_by(Notification.id))
            ).all()
        )

    await finish_failure()
    await finish_failure()
    rows = await notices()
    assert len(rows) == 1
    assert rows[0].user_id == OWNER.id
    assert rows[0].action_path == "/owner"
    assert URL not in rows[0].message and "token=" not in rows[0].message
    assert f"izvor #{source.id}" in rows[0].message

    await due(setup, source.id)
    job = await module.claim(sessions)
    await module.finish(sessions, job, calendar(event()))
    assert len(await notices()) == 2
    assert (await notices())[-1].title == "Kalendar se ponovo osvežava"
    await due(setup, source.id)
    job = await module.claim(sessions)
    await module.finish(sessions, job, calendar(event()))
    assert len(await notices()) == 2

    # An unsuccessful transaction must not persist a notice or suppress a retry.
    await due(setup, source.id)
    job = await module.claim(sessions)
    commit = setup.db.commit
    setup.db.commit = AsyncMock(side_effect=RuntimeError("commit failed"))
    with pytest.raises(RuntimeError):
        await module.finish(sessions, job, None, "fetch_error")
    await setup.db.rollback()
    setup.db.commit = commit
    assert len(await notices()) == 2
    await module.finish(sessions, job, None, "fetch_error")
    assert len(await notices()) == 3
    await due(setup, source.id)
    job = await module.claim(sessions)
    await module.finish(sessions, job, None, "key_error")
    assert len(await notices()) == 4
    await due(setup, source.id)
    job = await module.claim(sessions)
    await setup.configure(1, OWNER, source.id, "pause")
    assert await module.finish(sessions, job, None, "fetch_error") == "discarded"
    assert len(await notices()) == 4


@pytest.mark.asyncio
async def test_encrypted_config_http_privacy_and_disconnect_keeps_blocks(
    setup, importer
):
    source = await connect(setup)
    row = await setup.connection(source.id)
    assert URL not in row.encrypted_url
    assert module.cipher().decrypt(row.encrypted_url.encode()).decode() == URL
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_db] = lambda: setup.db
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        path = f"/owner/properties/2/occupancy-sources/{source.id}/sync"
        assert (await client.get(path)).status_code == 401
        app.dependency_overrides[get_current_user] = lambda: GUEST
        assert (await client.get(path)).status_code == 403
        app.dependency_overrides[get_current_user] = lambda: OWNER
        response = await client.get(path)
        assert response.headers["cache-control"] == "private, no-store"
        assert "private" not in response.text and "encrypted_url" not in response.text
        assert response.json()["configured"]
        assert (await client.post(path, json={"action": "connect"})).status_code == 422
    await importer.run(
        1,
        OWNER,
        calendar(event()),
        apply=True,
        source_id=source.id,
        source_revision=source.revision,
    )
    await setup.configure(1, OWNER, source.id, "pause")
    assert not (await setup.status(2, OWNER, source.id))["enabled"]
    await setup.configure(1, OWNER, source.id, "resume")
    await setup.configure(1, OWNER, source.id, "disconnect")
    assert await setup.connection(source.id) is None
    assert len(await setup.blocks(source.id)) == 1


@pytest.mark.asyncio
async def test_worker_success_conflict_error_and_empty_protection(
    setup, monkeypatch, stay_service
):
    source = await connect(setup)
    sessions = sessions_for(setup)
    fetch = AsyncMock(return_value=calendar(event(10, 12)))
    monkeypatch.setattr(module, "fetch_calendar_url", fetch)
    assert await module.run_calendar_syncs(sessions) == {"applied": 1}
    row = await setup.connection(source.id)
    success = row.last_success_at
    assert len(await setup.blocks(source.id)) == 1
    assert await module.run_calendar_syncs(sessions) == {}
    await stay_service.create(2, booking(), GUEST)
    fetch.return_value = calendar(event())
    await due(setup, source.id)
    assert await module.run_calendar_syncs(sessions) == {"conflict": 1}
    assert len(await setup.blocks(source.id)) == 1
    assert module.utc(
        (await setup.connection(source.id)).last_success_at
    ) == module.utc(success)
    fetch.side_effect = HTTPException(502, "provider secret")
    await due(setup, source.id)
    assert await module.run_calendar_syncs(sessions) == {"fetch_error": 1}
    assert len(await setup.blocks(source.id)) == 1
    fetch.side_effect = None
    fetch.return_value = calendar()
    await due(setup, source.id)
    assert await module.run_calendar_syncs(sessions) == {"blocked_empty": 1}
    assert len(await setup.blocks(source.id)) == 1
    await setup.configure(1, OWNER, source.id, "connect", URL, True)
    assert await module.run_calendar_syncs(sessions) == {"applied": 1}
    assert await setup.blocks(source.id) == []


@pytest.mark.asyncio
async def test_late_results_discarded_after_pause_replacement_and_manual_import(
    setup, importer
):
    source = await connect(setup)
    sessions = sessions_for(setup)
    job = await module.claim(sessions)
    assert await module.claim(sessions) is None
    await setup.configure(1, OWNER, source.id, "pause")
    assert await module.finish(sessions, job, calendar(event())) == "discarded"
    await setup.configure(1, OWNER, source.id, "connect", URL)
    job = await module.claim(sessions)
    await importer.run(
        1,
        OWNER,
        calendar(event(20, 22)),
        apply=True,
        source_id=source.id,
        source_revision=source.revision,
    )
    assert await module.finish(sessions, job, calendar(event())) == "superseded"
    assert (await setup.blocks(source.id))[0].check_in == TODAY + timedelta(days=20)
    await due(setup, source.id)
    job = await module.claim(sessions)
    await setup.configure(1, OWNER, source.id, "connect", URL + "new")
    assert await module.finish(sessions, job, calendar()) == "discarded"


@pytest.mark.asyncio
async def test_expired_lease_and_owner_transfer_stop_old_jobs(setup, monkeypatch):
    source = await connect(setup)
    sessions = sessions_for(setup)
    old = await module.claim(sessions)
    row = await setup.connection(source.id)
    row.lease_until = datetime.now(UTC) - timedelta(seconds=1)
    await setup.db.commit()
    assert await module.finish(sessions, old, calendar(event())) == "discarded"
    replacement = await module.claim(sessions)
    assert replacement["token"] != old["token"]
    venue = await setup.db.get(Venue, 1)
    venue.owner_id = 3
    await setup.db.commit()
    assert await module.finish(sessions, replacement, calendar(event())) == "inactive"
    assert await setup.blocks(source.id) == []
    fetch = AsyncMock()
    monkeypatch.setattr(module, "fetch_calendar_url", fetch)
    assert await module.run_calendar_syncs(sessions) == {}
    fetch.assert_not_called()


@pytest.mark.asyncio
async def test_wrong_key_demo_and_global_switch_preserve_inventory(setup, monkeypatch):
    source = await connect(setup)
    sessions = sessions_for(setup)
    monkeypatch.setattr(settings, "OCCUPANCY_SYNC_KEY", Fernet.generate_key().decode())
    assert await module.run_calendar_syncs(sessions) == {"key_error": 1}
    monkeypatch.setattr(settings, "DEMO_MODE", True)
    assert await module.run_calendar_syncs(sessions) == {}
    with pytest.raises(HTTPException):
        await setup.configure(1, OWNER, source.id, "resume")
    monkeypatch.setattr(settings, "DEMO_MODE", False)
    monkeypatch.setattr(settings, "OCCUPANCY_SYNC_ENABLED", False)
    assert await module.run_calendar_syncs(sessions) == {}
    await setup.configure(1, OWNER, source.id, "disconnect")


@pytest.mark.asyncio
async def test_overdue_and_source_removal_discard_inflight_result(setup):
    source = await connect(setup)
    row = await setup.connection(source.id)
    row.next_run_at = datetime.now(UTC) - timedelta(minutes=16)
    await setup.db.commit()
    assert (await setup.status(1, OWNER, source.id))["overdue"]
    job = await module.claim(sessions_for(setup))
    assert not (await setup.status(1, OWNER, source.id))["overdue"]
    await setup.remove(1, OWNER, source.id)
    assert (
        await module.finish(sessions_for(setup), job, calendar(event())) == "discarded"
    )


@pytest.mark.asyncio
async def test_worker_commit_failure_rolls_back_blocks_and_success_status(
    setup, monkeypatch
):
    await connect(setup)
    job = await module.claim(sessions_for(setup))
    monkeypatch.setattr(
        setup.db, "commit", AsyncMock(side_effect=RuntimeError("commit failed"))
    )
    with pytest.raises(RuntimeError):
        await module.finish(sessions_for(setup), job, calendar(event()))
    await setup.db.rollback()
    assert await setup.blocks(job["source_id"]) == []
    row = await setup.connection(job["source_id"])
    assert row.last_success_at is None and row.last_status == "pending"


@pytest.mark.asyncio
async def test_owner_change_is_detected_before_downloading(setup, monkeypatch):
    source = await connect(setup)
    venue = await setup.db.get(Venue, 1)
    venue.owner_id = 3
    await setup.db.commit()
    fetch = AsyncMock()
    monkeypatch.setattr(module, "fetch_calendar_url", fetch)
    assert await module.run_calendar_syncs(sessions_for(setup)) == {"inactive": 1}
    fetch.assert_not_called()
    assert not (await setup.connection(source.id)).enabled


def test_sync_migration_and_schedule():
    spec = importlib.util.spec_from_file_location(
        "sync_migration", Path("alembic/versions/e16a37bc2045_occupancy_sync.py")
    )
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    with create_engine("sqlite://").begin() as connection:
        with Operations.context(MigrationContext.configure(connection)):
            migration.upgrade()
            assert "occupancy_syncs" in inspect(connection).get_table_names()
            migration.downgrade()
            assert "occupancy_syncs" not in inspect(connection).get_table_names()
    assert (
        celery_app.conf.beat_schedule["refresh-occupancy-calendars"]["schedule"] == 60
    )


@pytest.mark.asyncio
@pytest.mark.skipif(not os.getenv("STAY_TEST_POSTGRES"), reason="Requires PostgreSQL")
async def test_postgres_duplicate_workers_claim_once_and_booking_conflict(monkeypatch):
    monkeypatch.setattr(settings, "DEMO_MODE", False)
    monkeypatch.setattr(settings, "OCCUPANCY_SYNC_ENABLED", True)
    monkeypatch.setattr(settings, "OCCUPANCY_SYNC_KEY", Fernet.generate_key().decode())
    monkeypatch.setattr(settings, "OCCUPANCY_IMPORT_ALLOWED_HOSTS", "calendar.example")
    monkeypatch.setattr(StayService, "today", staticmethod(lambda zone: TODAY))
    schema = "auto_calendar_" + uuid4().hex
    engine = create_async_engine(
        settings.DATABASE_URL,
        execution_options={"schema_translate_map": {None: schema}},
    )
    tables = [
        test_stays.User.__table__,
        Venue.__table__,
        test_stays.PropertyListing.__table__,
        test_stays.Resource.__table__,
        test_stays.Stay.__table__,
        StayBlock.__table__,
        test_stays.Notification.__table__,
        OccupancyImportRun.__table__,
        OccupancySource.__table__,
        OccupancySourceBlock.__table__,
        OccupancySync.__table__,
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
            await connect(module.OccupancySyncService(db))
        jobs = await asyncio.gather(module.claim(sessions), module.claim(sessions))
        assert sum(job is not None for job in jobs) == 1
        job = next(job for job in jobs if job is not None)

        async def reserve():
            async with sessions() as db:
                try:
                    await StayService(db).create(2, booking(), GUEST)
                    return True
                except HTTPException as error:
                    assert error.status_code == 409
                    return False

        outcomes = await asyncio.gather(
            module.finish(sessions, job, calendar(event())), reserve()
        )
        assert outcomes in (["applied", False], ["conflict", True])
    finally:
        async with engine.begin() as connection:
            await connection.execute(DropSchema(schema, cascade=True))
        await engine.dispose()
