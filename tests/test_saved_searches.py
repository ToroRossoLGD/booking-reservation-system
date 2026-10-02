import os
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db.base import Base
from app.models.saved_search import SavedSearch
from app.models.user import User
from app.schemas.saved_search import SavedSearchWrite
from app.services.saved_search_service import SavedSearchService


@pytest.fixture
def service():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine, tables=[User.__table__, SavedSearch.__table__])
    with Session(engine, expire_on_commit=False) as session:
        session.add_all(
            [
                User(
                    id=i,
                    email=f"user{i}@example.com",
                    hashed_password="test",
                    role="customer",
                )
                for i in (1, 2)
            ]
        )
        session.commit()
        db = MagicMock()
        db.add = session.add
        for name in ("scalar", "scalars", "commit", "refresh", "delete"):
            setattr(db, name, AsyncMock(side_effect=getattr(session, name)))
        yield SavedSearchService(db)
    engine.dispose()


@pytest.mark.parametrize(
    "path",
    [
        "//evil.example",
        "https://evil.example",
        "javascript:alert(1)",
        "/owner",
        "/?city=x#fragment",
        "/?city=x&city=y",
        "/?rooms=-1",
        "/?offer_type=short_stay&check_in=2030-10-01",
    ],
)
def test_rejects_unsafe_or_invalid_searches(path):
    with pytest.raises(ValidationError):
        SavedSearchWrite(name="Search", path=path)


def test_normalizes_filters_and_discards_pagination_and_unknown_parameters():
    data = SavedSearchWrite(
        name="  Studio  ",
        path="/?rooms=0&city=Novi+Sad&has_parking=false&offset=24&limit=99&token=secret",
    )
    assert data.name == "Studio"
    assert data.path == "/?city=Novi+Sad&has_parking=false&rooms=0"


@pytest.mark.asyncio
async def test_private_lists_upsert_limit_and_idempotent_delete(service):
    user = SimpleNamespace(id=1)
    other = SimpleNamespace(id=2)
    first = await service.save(
        SavedSearchWrite(name="A", path="/?city=City0&offset=12"), user
    )
    renamed = await service.save(SavedSearchWrite(name="B", path="/?city=City0"), user)
    assert renamed.id == first.id and renamed.name == "B"
    assert await service.list(other) == []
    await service.remove(first.id, other)
    assert len(await service.list(user)) == 1
    for i in range(1, 10):
        await service.save(SavedSearchWrite(name=str(i), path=f"/?city=City{i}"), user)
    with pytest.raises(HTTPException) as error:
        await service.save(SavedSearchWrite(name="Extra", path="/?city=Extra"), user)
    assert error.value.status_code == 409
    assert (
        await service.save(SavedSearchWrite(name="New name", path="/?city=City0"), user)
    ).id == first.id
    await service.remove(first.id, user)
    await service.remove(first.id, user)
    assert len(await service.list(user)) == 9
    await service.save(SavedSearchWrite(name="Extra", path="/?city=Extra"), user)
    await service.save(SavedSearchWrite(name="Other", path="/?city=Extra"), other)
    assert len(await service.list(other)) == 1


def test_routes_require_authentication():
    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as client:
        assert client.get("/saved-searches").status_code == 401
        assert (
            client.put("/saved-searches", json={"name": "A", "path": "/"}).status_code
            == 401
        )
        assert client.delete("/saved-searches/1").status_code == 401


def test_migration_roundtrip():
    import importlib.util
    from pathlib import Path

    from alembic.migration import MigrationContext
    from alembic.operations import Operations
    from sqlalchemy import inspect, text

    path = (
        Path(__file__).parents[1]
        / "alembic/versions/dab68421357e_add_saved_searches.py"
    )
    spec = importlib.util.spec_from_file_location("saved_search_migration", path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    engine = create_engine("sqlite://")
    with engine.begin() as connection:
        connection.execute(text("PRAGMA foreign_keys=ON"))
        connection.execute(text("CREATE TABLE users (id INTEGER PRIMARY KEY)"))
        connection.execute(text("INSERT INTO users VALUES (1)"))
        migration.op = Operations(MigrationContext.configure(connection))
        migration.upgrade()
        assert {
            column["name"]
            for column in inspect(connection).get_columns("saved_searches")
        } == set(SavedSearch.__table__.columns.keys())
        connection.execute(
            text(
                "INSERT INTO saved_searches (user_id, name, path) VALUES (1, 'A', '/')"
            )
        )
        connection.execute(text("DELETE FROM users WHERE id=1"))
        assert connection.scalar(text("SELECT COUNT(*) FROM saved_searches")) == 0
        migration.downgrade()
        assert "saved_searches" not in inspect(connection).get_table_names()
    engine.dispose()


@pytest.mark.asyncio
@pytest.mark.skipif(
    not os.getenv("STAY_TEST_POSTGRES"), reason="CI runs PostgreSQL locking"
)
async def test_postgres_simultaneous_saves_and_cap():
    import asyncio
    from uuid import uuid4

    from sqlalchemy import func, select
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
    from sqlalchemy.schema import CreateSchema, DropSchema

    from app.core.config import settings

    schema = "saved_search_test_" + uuid4().hex
    engine = create_async_engine(
        settings.DATABASE_URL,
        execution_options={"schema_translate_map": {None: schema}},
    )
    try:
        async with engine.begin() as connection:
            await connection.execute(CreateSchema(schema))
            await connection.run_sync(
                lambda sync: Base.metadata.create_all(
                    sync, tables=[User.__table__, SavedSearch.__table__]
                )
            )
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        user = SimpleNamespace(id=1)
        async with sessions() as db:
            db.add(
                User(
                    id=1,
                    email="saved@example.com",
                    hashed_password="test",
                    role="customer",
                )
            )
            await db.commit()

        async def save(path):
            async with sessions() as db:
                try:
                    return (
                        await SavedSearchService(db).save(
                            SavedSearchWrite(name="Search", path=path), user
                        )
                    ).id
                except HTTPException as error:
                    await db.rollback()
                    return error.status_code

        retries = await asyncio.gather(save("/"), save("/?offset=12"))
        assert retries[0] == retries[1]
        for i in range(8):
            await save(f"/?city=City{i}")
        results = await asyncio.gather(save("/?city=Last"), save("/?city=Extra"))
        assert results.count(409) == 1
        async with sessions() as db:
            assert await db.scalar(select(func.count(SavedSearch.id))) == 10
    finally:
        async with engine.begin() as connection:
            await connection.execute(DropSchema(schema, cascade=True, if_exists=True))
        await engine.dispose()
