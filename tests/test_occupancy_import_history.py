import importlib.util
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from fastapi import FastAPI, HTTPException
from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine, func, inspect, select

from app.api.routers.stay_blocks import router
from app.core.dependencies import get_current_user
from app.db.session import get_db
from app.models.occupancy_import_run import OccupancyImportRun
from app.models.stay_block import StayBlock
from app.models.venue import Venue
from tests import test_occupancy_import, test_stays
from tests.test_occupancy_import import calendar, event
from tests.test_stays import GUEST, OWNER, booking

stay_service = test_stays.service
importer = test_occupancy_import.importer


@pytest.mark.asyncio
async def test_history_records_confirmations_only_and_shared_aliases(importer):
    assert await importer.history(1, OWNER) == []
    await importer.run(1, OWNER, calendar(event()))
    with pytest.raises(HTTPException):
        await importer.run(1, OWNER, "invalid", apply=True)
    assert await importer.history(1, OWNER) == []
    await importer.run(1, OWNER, calendar(event()), apply=True)
    await importer.run(2, OWNER, calendar(event()), apply=True)
    history = await importer.history(2, OWNER)
    assert [row.created for row in history] == [0, 1]
    assert history[0].existing == 1 and history[0].status == "applied"
    assert history[0].created_at is not None
    # Bounded newest-first view, with a deterministic tie-breaker.
    for _ in range(11):
        await importer.run(1, OWNER, calendar(event()), apply=True)
    history = await importer.history(1, OWNER)
    assert len(history) == 10
    assert [row.id for row in history] == list(range(13, 3, -1))


@pytest.mark.asyncio
async def test_conflict_outcome_is_saved_without_creating_any_blocks(
    importer, stay_service
):
    await stay_service.create(2, booking(), GUEST)
    result = await importer.run(1, OWNER, calendar(event(), event(20, 22)), apply=True)
    assert not result["applied"]
    row = (await importer.history(2, OWNER))[0]
    assert (row.status, row.conflicts, row.created) == ("conflict", 1, 0)
    assert await importer.db.scalar(select(func.count(StayBlock.id))) == 0


@pytest.mark.asyncio
async def test_import_and_history_rollback_together(importer, monkeypatch):
    monkeypatch.setattr(
        importer.db, "commit", AsyncMock(side_effect=RuntimeError("db unavailable"))
    )
    with pytest.raises(RuntimeError):
        await importer.run(1, OWNER, calendar(event()), apply=True)
    await importer.db.rollback()
    assert await importer.db.scalar(select(func.count(StayBlock.id))) == 0
    assert await importer.db.scalar(select(func.count(OccupancyImportRun.id))) == 0


@pytest.mark.asyncio
async def test_http_permissions_isolation_and_private_response(importer):
    await importer.run(1, OWNER, calendar(event()), apply=True)
    # A different venue's record must not appear even for the same owner.
    importer.db.add(Venue(id=2, name="Other", address="Elsewhere", owner_id=1))
    await importer.db.flush()
    importer.db.add(
        OccupancyImportRun(
            venue_id=2,
            status="applied",
            created=99,
            existing=0,
            conflicts=0,
            ignored=0,
            clipped=0,
        )
    )
    await importer.db.commit()
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_db] = lambda: importer.db
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        path = "/owner/properties/2/occupancy-import/history"
        assert (await client.get(path)).status_code == 401
        for user in [GUEST, SimpleNamespace(id=3, role="owner")]:
            app.dependency_overrides[get_current_user] = lambda: user
            assert (await client.get(path)).status_code == 403
        for user in [OWNER, SimpleNamespace(id=3, role="admin")]:
            app.dependency_overrides[get_current_user] = lambda: user
            response = await client.get(path)
            assert response.status_code == 200
            assert response.headers["cache-control"] == "private, no-store"
            assert len(response.json()) == 1 and response.json()[0]["created"] == 1
            assert set(response.json()[0]) == {
                "id",
                "created_at",
                "status",
                "created",
                "existing",
                "conflicts",
                "ignored",
                "clipped",
            }


def test_history_migration_roundtrip():
    path = Path("alembic/versions/c94e15fa0823_occupancy_import_history.py")
    spec = importlib.util.spec_from_file_location("history_migration", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    with create_engine("sqlite://").begin() as connection:
        with Operations.context(MigrationContext.configure(connection)):
            module.upgrade()
            assert "occupancy_import_runs" in inspect(connection).get_table_names()
            assert inspect(connection).get_indexes("occupancy_import_runs")[0][
                "column_names"
            ] == ["venue_id", "id"]
            module.downgrade()
            assert "occupancy_import_runs" not in inspect(connection).get_table_names()
