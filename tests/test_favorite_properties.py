import asyncio
import importlib.util
import os
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, delete, event, func, inspect, select, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.orm import Session
from sqlalchemy.schema import CreateSchema, DropSchema

from app.api.routers.favorite_properties import router
from app.core.dependencies import get_current_user
from app.db.base import Base
from app.db.session import get_db
from app.models.favorite_property import FavoriteProperty
from app.models.property_listing import PropertyListing
from app.models.user import User
from app.models.venue import Venue
from app.services.favorite_property_service import FavoritePropertyService

USER = SimpleNamespace(id=2, role="customer")
OTHER = SimpleNamespace(id=3, role="customer")
TABLES = [
    User.__table__,
    Venue.__table__,
    PropertyListing.__table__,
    FavoriteProperty.__table__,
]


def seed(session):
    session.add_all(
        [
            User(
                id=i,
                email=f"saved{i}@example.com",
                hashed_password="test",
                role="owner" if i == 1 else "customer",
            )
            for i in (1, 2, 3)
        ]
    )
    session.flush()
    session.add(Venue(id=1, owner_id=1, name="Apartment", address="Test"))
    session.flush()
    for i, offer in enumerate(("short_stay", "long_term", "sale", "long_term"), 1):
        session.add(
            PropertyListing(
                id=i,
                venue_id=1,
                title=f"Apartment {i}",
                description="A bright apartment in the city.",
                city="Beograd",
                offer_type=offer,
                area_sqm=50,
                rooms=2,
                price_cents=60000,
                currency="EUR",
                contact_email="owner@example.com",
                is_published=i != 4,
            )
        )
    session.commit()


@pytest.fixture
def service():
    engine = create_engine("sqlite://")
    event.listen(
        engine,
        "connect",
        lambda connection, _: connection.execute("PRAGMA foreign_keys=ON"),
    )
    Base.metadata.create_all(engine, tables=TABLES)
    with Session(engine, expire_on_commit=False) as session:
        seed(session)
        db = MagicMock()
        db.add = session.add
        for method in ("commit", "scalar", "scalars", "execute"):
            setattr(db, method, AsyncMock(side_effect=getattr(session, method)))
        yield FavoritePropertyService(db)
    engine.dispose()


@pytest.mark.asyncio
async def test_save_all_offer_types_and_idempotent_remove(service):
    for property_id in (1, 2, 3):
        assert await service.save(property_id, USER) == {
            "property_id": property_id,
            "saved": True,
        }
    await service.save(1, USER)
    first = await service.list(USER, limit=2)
    assert first["total"] == 3 and first["has_next"]
    assert [item.id for item in first["items"]] == [3, 2]
    last = await service.list(USER, offset=2, limit=2)
    assert [item.id for item in last["items"]] == [1] and not last["has_next"]
    await service.remove(2, USER)
    await service.remove(2, USER)
    assert (await service.list(USER))["total"] == 2
    await service.save(2, USER)
    assert (await service.list(USER))["items"][0].id == 2


@pytest.mark.asyncio
async def test_favorites_are_private_and_other_user_cannot_remove_them(service):
    await service.save(1, USER)
    assert (await service.list(OTHER))["total"] == 0
    assert await service.status(OTHER, [1, 2]) == {"property_ids": []}
    await service.remove(1, OTHER)
    assert await service.status(USER, [1, 1, 2, 999]) == {"property_ids": [1]}
    await service.save(1, OTHER)
    await service.remove(1, USER)
    assert await service.status(OTHER, [1]) == {"property_ids": [1]}


@pytest.mark.asyncio
async def test_hidden_listings_stay_private_and_reappear_with_current_prices(service):
    for property_id in (4, 999):
        with pytest.raises(HTTPException) as error:
            await service.save(property_id, USER)
        assert error.value.status_code == 404
    await service.save(2, USER)
    listing = await service.db.scalar(
        select(PropertyListing).where(PropertyListing.id == 2)
    )
    listing.is_published = False
    listing.price_cents = 95000
    await service.db.commit()
    assert (await service.list(USER))["total"] == 0
    assert await service.status(USER, [2, 4]) == {"property_ids": []}
    with pytest.raises(HTTPException) as error:
        await service.save(2, USER)
    assert error.value.status_code == 404
    listing.is_published = True
    await service.db.commit()
    assert (await service.list(USER))["items"][0].price_cents == 95000
    listing.is_published = False
    await service.db.commit()
    await service.remove(2, USER)
    assert await service.db.scalar(select(func.count(FavoriteProperty.id))) == 0


@pytest.mark.asyncio
async def test_deleted_listing_removes_saved_references(service):
    await service.save(1, USER)
    await service.save(1, OTHER)
    await service.db.execute(delete(PropertyListing).where(PropertyListing.id == 1))
    await service.db.commit()
    assert await service.db.scalar(select(func.count(FavoriteProperty.id))) == 0
    assert (await service.list(USER))["total"] == 0


def test_authentication_and_query_limits():
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_db] = lambda: AsyncMock()
    with TestClient(app) as client:
        for method, path in (
            ("GET", "/favorites/properties"),
            ("GET", "/favorites/properties/status?property_ids=1"),
            ("PUT", "/favorites/properties/1"),
            ("DELETE", "/favorites/properties/1"),
        ):
            assert client.request(method, path).status_code == 401
        app.dependency_overrides[get_current_user] = lambda: USER
        for query in ("limit=0", "limit=51", "offset=-1"):
            assert client.get(f"/favorites/properties?{query}").status_code == 422
        for query in ("", "property_ids=0", "property_ids=-1", "property_ids=1&" * 51):
            assert (
                client.get(f"/favorites/properties/status?{query}").status_code == 422
            )


def test_migration_round_trip_and_constraints():
    path = (
        Path(__file__).parents[1]
        / "alembic/versions/c38f5d9e0241_add_saved_properties.py"
    )
    spec = importlib.util.spec_from_file_location("saved_properties_migration", path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    engine = create_engine("sqlite://")
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE users (id INTEGER PRIMARY KEY)"))
        connection.execute(
            text("CREATE TABLE property_listings (id INTEGER PRIMARY KEY)")
        )
        connection.execute(text("INSERT INTO property_listings VALUES (42)"))
        migration.op = Operations(MigrationContext.configure(connection))
        migration.upgrade()
        inspector = inspect(connection)
        assert {
            column["name"] for column in inspector.get_columns("favorite_properties")
        } == set(FavoriteProperty.__table__.columns.keys())
        assert inspector.get_unique_constraints("favorite_properties")[0][
            "column_names"
        ] == ["user_id", "property_id"]
        assert all(
            fk["options"]["ondelete"] == "CASCADE"
            for fk in inspector.get_foreign_keys("favorite_properties")
        )
        migration.downgrade()
        assert "favorite_properties" not in inspect(connection).get_table_names()
        assert connection.scalar(text("SELECT id FROM property_listings")) == 42
    engine.dispose()


@pytest.mark.asyncio
@pytest.mark.skipif(
    not os.getenv("STAY_TEST_POSTGRES"), reason="CI enables PostgreSQL locking tests"
)
async def test_postgres_simultaneous_saves_create_one_favorite():
    from app.core.config import settings

    schema = "saved_properties_test_" + uuid4().hex
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
            await db.run_sync(seed)

        async def save():
            async with sessions() as db:
                return await FavoritePropertyService(db).save(1, USER)

        assert (
            await asyncio.gather(save(), save())
            == [{"property_id": 1, "saved": True}] * 2
        )
        async with sessions() as db:
            assert await db.scalar(select(func.count(FavoriteProperty.id))) == 1
    finally:
        async with engine.begin() as connection:
            await connection.execute(DropSchema(schema, cascade=True, if_exists=True))
        await engine.dispose()
