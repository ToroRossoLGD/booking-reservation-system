import asyncio
import importlib.util
import os
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
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
from app.models.occupancy_import_run import OccupancyImportRun
from app.models.occupancy_source import OccupancySource, OccupancySourceBlock
from app.models.stay_block import StayBlock
from app.models.venue import Venue
from app.services.occupancy_import_service import OccupancyImportService
from app.services.occupancy_source_service import OccupancySourceService
from app.services.stay_service import StayService
from tests import test_occupancy_import, test_stays
from tests.test_occupancy_import import calendar, event
from tests.test_stays import GUEST, OWNER, TODAY, booking

stay_service = test_stays.service
importer = test_occupancy_import.importer


@pytest.fixture
def sources(importer):
    session = importer.db.scalar.side_effect.__self__
    OccupancySource.__table__.create(session.get_bind())
    OccupancySourceBlock.__table__.create(session.get_bind())
    return OccupancySourceService(importer.db)


async def sync(importer, source, content, apply=True, revision=None):
    return await importer.run(
        1,
        OWNER,
        content,
        apply=apply,
        source_id=source.id,
        source_revision=source.revision if revision is None else revision,
    )


@pytest.mark.asyncio
async def test_source_replacement_empty_feed_and_manual_blocks_survive(
    sources, importer
):
    source = await sources.create(1, OWNER, "Mountain channel")
    assert (await sources.create(2, OWNER, source.name)).id == source.id
    await importer.run(1, OWNER, calendar(event(30, 32)), apply=True)
    first = await sync(importer, source, calendar(event(), event(10, 12)))
    assert first["created"] == 2 and source.revision == 1
    preview = await sync(
        importer, source, calendar(event(10, 12), event(20, 22)), apply=False
    )
    assert preview["removed"] == 1 and len(preview["removed_ranges"]) == 1
    assert len(await sources.blocks(source.id)) == 2
    second = await sync(importer, source, calendar(event(10, 12), event(20, 22)))
    assert (second["created"], second["removed"]) == (1, 1)
    assert source.last_success_at is not None
    empty = await sync(importer, source, calendar())
    assert empty["removed"] == 2
    assert await sources.blocks(source.id) == []
    active = list(
        (
            await importer.db.scalars(
                select(StayBlock).where(StayBlock.active.is_(True))
            )
        ).all()
    )
    assert len(active) == 1 and active[0].reason == "iCal import"
    assert not (await sync(importer, source, calendar(event(30, 32))))["applied"]
    assert await sources.blocks(source.id) == []


@pytest.mark.asyncio
async def test_failed_commit_keeps_previous_source_inventory(
    sources, importer, monkeypatch
):
    source = await sources.create(1, OWNER, "Atomic")
    await sync(importer, source, calendar(event()))
    source_id = source.id
    monkeypatch.setattr(
        importer.db, "commit", AsyncMock(side_effect=RuntimeError("commit failed"))
    )
    with pytest.raises(RuntimeError):
        await sync(importer, source, calendar(event(20, 22)))
    await importer.db.rollback()
    blocks = await sources.blocks(source_id)
    assert len(blocks) == 1
    assert blocks[0].check_in == test_stays.booking().check_in
    refreshed = await sources.get(1, source_id)
    assert refreshed.revision == 1


@pytest.mark.asyncio
async def test_conflicts_keep_old_blocks_and_success_time(
    sources, importer, stay_service
):
    first = await sources.create(1, OWNER, "One")
    second = await sources.create(1, OWNER, "Two")
    await sync(importer, first, calendar(event(10, 12)))
    previous_success = first.last_success_at
    await sync(importer, second, calendar(event(20, 22)))
    conflict = await sync(importer, first, calendar(event(20, 22)))
    assert not conflict["applied"] and conflict["removed"] == 0
    assert first.last_status == "conflict"
    assert first.last_success_at.replace(tzinfo=None) == previous_success.replace(
        tzinfo=None
    )
    assert len(await sources.blocks(first.id)) == 1
    await stay_service.create(2, booking(), GUEST)
    assert not (await sync(importer, first, calendar(event())))["applied"]
    await sources.remove(2, OWNER, second.id)
    assert len(await sources.blocks(first.id)) == 1
    assert len(await sources.list(1, OWNER)) == 1


@pytest.mark.asyncio
async def test_stale_confirmation_unauthorized_source_and_limits(
    sources, importer, monkeypatch
):
    source = await sources.create(1, OWNER, "One")
    preview = await sync(importer, source, calendar(event()), apply=False)
    await sync(importer, source, calendar(event(20, 22)))
    with pytest.raises(HTTPException) as error:
        await sync(importer, source, calendar(), revision=preview["source_revision"])
    assert error.value.status_code == 409
    importer.db.add(Venue(id=2, name="Other", address="Other", owner_id=1))
    await importer.db.flush()
    foreign = OccupancySource(venue_id=2, name="foreign", revision=0)
    importer.db.add(foreign)
    await importer.db.commit()
    with pytest.raises(HTTPException) as error:
        await sync(importer, foreign, calendar())
    assert error.value.status_code == 404
    for user in (GUEST, SimpleNamespace(id=99, role="owner")):
        with pytest.raises(HTTPException):
            await sources.remove(1, user, source.id)
    for index in range(9):
        await sources.create(1, OWNER, str(index))
    with pytest.raises(HTTPException):
        await sources.create(1, OWNER, "eleventh")
    monkeypatch.setattr(settings, "DEMO_MODE", True)
    with pytest.raises(HTTPException):
        await sources.remove(1, OWNER, source.id)


@pytest.mark.asyncio
async def test_source_routes_and_revision_required(sources, importer):
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_db] = lambda: importer.db
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        path = "/owner/properties/1/occupancy-sources"
        assert (await client.get(path)).status_code == 401
        app.dependency_overrides[get_current_user] = lambda: OWNER
        assert (await client.post(path, json={"name": " "})).status_code == 422
        source = (await client.post(path, json={"name": "Channel"})).json()
        listing = await client.get(path)
        assert listing.headers["cache-control"] == "private, no-store"
        assert listing.json()[0]["name"] == "Channel"
        data = {"content": calendar(event()), "source_id": source["id"]}
        import_path = "/owner/properties/1/occupancy-import"
        assert (await client.post(import_path, json=data)).status_code == 409
        preview = (await client.post(import_path + "/preview", json=data)).json()
        data["source_revision"] = preview["source_revision"]
        assert (await client.post(import_path, json=data)).json()["created"] == 1
        assert (await client.delete(path + f"/{source['id']}")).status_code == 204
        assert (await client.get(path)).json() == []


def test_source_migration_roundtrip():
    spec = importlib.util.spec_from_file_location(
        "source_migration", Path("alembic/versions/d05f26ab1934_occupancy_sources.py")
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    with create_engine("sqlite://").begin() as connection:
        with Operations.context(MigrationContext.configure(connection)):
            module.upgrade()
            assert "occupancy_source_blocks" in inspect(connection).get_table_names()
            module.downgrade()
            assert "occupancy_sources" not in inspect(connection).get_table_names()


@pytest.mark.asyncio
@pytest.mark.skipif(not os.getenv("STAY_TEST_POSTGRES"), reason="Requires PostgreSQL")
async def test_concurrent_source_confirmations_cannot_overwrite_newer_snapshot(
    monkeypatch,
):
    monkeypatch.setattr(settings, "DEMO_MODE", False)
    monkeypatch.setattr(StayService, "today", staticmethod(lambda zone: TODAY))
    schema = "source_test_" + uuid4().hex
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
            source = await OccupancySourceService(db).create(1, OWNER, "Concurrent")
            source_id = source.id

        async def attempt(property_id, content):
            async with sessions() as db:
                try:
                    return await OccupancyImportService(db).run(
                        property_id,
                        OWNER,
                        content,
                        apply=True,
                        source_id=source_id,
                        source_revision=0,
                    )
                except HTTPException as error:
                    assert error.status_code == 409
                    return None

        outcomes = await asyncio.gather(
            attempt(1, calendar(event())), attempt(2, calendar(event(20, 22)))
        )
        assert sum(value is not None for value in outcomes) == 1
        async with sessions() as db:
            assert len(await OccupancySourceService(db).blocks(source_id)) == 1
    finally:
        async with engine.begin() as connection:
            await connection.execute(DropSchema(schema, cascade=True))
        await engine.dispose()
