import asyncio
import hashlib
import importlib.util
import logging
import os
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from fastapi import FastAPI, HTTPException
from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine, inspect
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.schema import CreateSchema, DropSchema

from app.api.routers.stay_blocks import router
from app.core.config import settings
from app.core.dependencies import get_current_user
from app.core.feed_logging import OccupancyAccessFilter
from app.db.base import Base
from app.db.session import get_db
from app.models.occupancy_feed import OccupancyFeed
from app.models.property_listing import PropertyListing
from app.models.user import User
from app.models.venue import Venue
from app.services.occupancy_feed_service import OccupancyFeedService
from tests import test_stays
from tests.test_stays import GUEST, OWNER, booking

stay_service = test_stays.service


@pytest.mark.asyncio
@pytest.mark.skipif(not os.getenv("STAY_TEST_POSTGRES"), reason="Requires PostgreSQL")
async def test_concurrent_alias_rotation_keeps_only_one_token(monkeypatch):
    monkeypatch.setattr(settings, "DEMO_MODE", False)
    schema = "feed_test_" + uuid4().hex
    engine = create_async_engine(
        settings.DATABASE_URL,
        execution_options={"schema_translate_map": {None: schema}},
    )
    try:
        async with engine.begin() as connection:
            await connection.execute(CreateSchema(schema))
            await connection.run_sync(
                lambda sync: Base.metadata.create_all(
                    sync,
                    tables=[
                        User.__table__,
                        Venue.__table__,
                        PropertyListing.__table__,
                        test_stays.Resource.__table__,
                        test_stays.Stay.__table__,
                        test_stays.StayBlock.__table__,
                        test_stays.Notification.__table__,
                        OccupancyFeed.__table__,
                    ],
                )
            )
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        async with sessions() as db:
            await db.run_sync(test_stays.seed)

        async def rotate(property_id):
            async with sessions() as db:
                return await OccupancyFeedService(db).manage(
                    property_id, OWNER, "rotate"
                )

        results = await asyncio.gather(rotate(1), rotate(2))
        async with sessions() as db:
            stored = await db.get(OccupancyFeed, 1)
            hashes = [
                hashlib.sha256(result["path"].split("/")[-1][:-4].encode()).hexdigest()
                for result in results
            ]
            assert hashes[0] != hashes[1]
            assert sum(value == stored.token_hash for value in hashes) == 1
            await OccupancyFeedService(db).manage(2, OWNER, "revoke")
            assert stored.token_hash is None
    finally:
        async with engine.begin() as connection:
            await connection.execute(DropSchema(schema, cascade=True))
        await engine.dispose()


@pytest.fixture
def feeds(stay_service, monkeypatch):
    monkeypatch.setattr(settings, "DEMO_MODE", False)
    db = stay_service.repository.db
    session = db.scalar.side_effect.__self__
    OccupancyFeed.__table__.create(session.get_bind())
    return OccupancyFeedService(db)


@pytest.mark.asyncio
async def test_rotation_revocation_aliases_and_live_occupancy(feeds, stay_service):
    assert await feeds.manage(1, OWNER) == {"active": False}
    result = await feeds.manage(1, OWNER, "rotate")
    token = result["path"].split("/")[-1][:-4]
    stored = await feeds.db.get(OccupancyFeed, 1)
    assert stored.token_hash == hashlib.sha256(token.encode()).hexdigest()
    assert token not in str(stored.__dict__)
    assert await feeds.manage(2, OWNER) == {"active": True}
    assert "BEGIN:VEVENT" not in await feeds.render(token)
    stay = await stay_service.create(2, booking(), GUEST)
    assert "BEGIN:VEVENT" in await feeds.render(token)
    stay.status = "cancelled"
    await feeds.db.commit()
    assert "BEGIN:VEVENT" not in await feeds.render(token)
    replacement = await feeds.manage(2, OWNER, "rotate")
    new_token = replacement["path"].split("/")[-1][:-4]
    assert new_token != token
    with pytest.raises(HTTPException) as error:
        await feeds.render(token)
    assert error.value.status_code == 404
    assert await feeds.render(new_token)
    await feeds.manage(1, OWNER, "revoke")
    await feeds.manage(1, OWNER, "revoke")
    with pytest.raises(HTTPException):
        await feeds.render(new_token)


@pytest.mark.asyncio
async def test_authorization_owner_transfer_and_demo(feeds, monkeypatch):
    for actor in [GUEST, SimpleNamespace(id=99, role="owner")]:
        with pytest.raises(HTTPException) as error:
            await feeds.manage(1, actor, "rotate")
        assert error.value.status_code == 403
    result = await feeds.manage(1, OWNER, "rotate")
    venue = await feeds.db.get(Venue, 1)
    venue.owner_id = 3
    await feeds.db.commit()
    with pytest.raises(HTTPException):
        await feeds.render(result["path"].split("/")[-1][:-4])
    assert await feeds.manage(1, SimpleNamespace(id=3, role="owner")) == {
        "active": False
    }
    monkeypatch.setattr(settings, "DEMO_MODE", True)
    with pytest.raises(HTTPException) as error:
        await feeds.manage(1, SimpleNamespace(id=3, role="owner"), "rotate")
    assert error.value.status_code == 403


@pytest.mark.asyncio
async def test_http_public_token_and_private_management(feeds):
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_db] = lambda: feeds.db
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        path = "/owner/properties/1/occupancy-feed"
        assert (await client.post(path)).status_code == 401
        app.dependency_overrides[get_current_user] = lambda: OWNER
        response = await client.post(path)
        assert response.status_code == 200
        assert response.headers["cache-control"] == "no-store"
        public_path = response.json()["path"]
        assert (await client.get(path)).json() == {"active": True}
        del app.dependency_overrides[get_current_user]
        public = await client.get(public_path)
        assert public.status_code == 200
        assert public.headers["cache-control"] == "private, no-store"
        assert public.headers["content-type"].startswith("text/calendar")
        assert (await client.get("/occupancy-feeds/invalid.ics")).status_code == 404
        app.dependency_overrides[get_current_user] = lambda: OWNER
        await client.delete(path)
        assert (await client.get(public_path)).status_code == 404


def test_migration_roundtrip_and_log_filter():
    path = Path("alembic/versions/b83f04e9c712_occupancy_feeds.py")
    spec = importlib.util.spec_from_file_location("feed_migration", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    with create_engine("sqlite://").begin() as connection:
        with Operations.context(MigrationContext.configure(connection)):
            module.upgrade()
            assert "occupancy_feeds" in inspect(connection).get_table_names()
            module.downgrade()
            assert "occupancy_feeds" not in inspect(connection).get_table_names()
    sensitive = logging.LogRecord(
        "uvicorn.access",
        20,
        "",
        0,
        '%s "%s %s HTTP/1.1" %s',
        ("peer", "GET", "/occupancy-feeds/secret.ics", 200),
        None,
    )
    assert not OccupancyAccessFilter().filter(sensitive)
    safe = logging.LogRecord("uvicorn.access", 20, "", 0, "GET /health 200", (), None)
    assert OccupancyAccessFilter().filter(safe)
