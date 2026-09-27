import asyncio
import os
from datetime import date
from types import SimpleNamespace
from uuid import uuid4

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, inspect, select, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.schema import CreateSchema, DropSchema

from app.core.config import settings
from app.core.dependencies import get_current_user
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.property_view import PropertyView
from app.models.stay import Stay
from app.schemas.property_analytics import PropertyAnalytics
from app.services.property_analytics_service import PropertyAnalyticsService
from tests import test_stays
from tests.test_stay_migration import load_migration

service = test_stays.service


@pytest.fixture
def analytics(service, monkeypatch):
    PropertyView.__table__.create(service.repository.db.add.__self__.get_bind())
    monkeypatch.setattr(
        PropertyAnalyticsService, "today", staticmethod(lambda: date(2026, 1, 30))
    )
    return PropertyAnalyticsService(service.repository.db)


async def add_stay(service, start, end, **changes):
    return await service.repository.save(
        Stay(
            **(
                dict(
                    property_id=1,
                    venue_id=1,
                    user_id=2,
                    request_id=str(uuid4()),
                    check_in=date.fromisoformat(start),
                    check_out=date.fromisoformat(end),
                    guests=2,
                    status="confirmed",
                    title="Snapshot",
                    city="Belgrade",
                    timezone="Europe/Belgrade",
                    contact_email="host@example.com",
                    nightly_rate_cents=1000,
                    total_cents=2000,
                    currency="EUR",
                )
                | changes
            )
        )
    )


@pytest.mark.asyncio
async def test_view_deduplication_owner_exclusion_and_private_data(
    service, analytics, monkeypatch
):
    visitor = uuid4()
    await analytics.record_view(1, visitor)
    await analytics.record_view(1, visitor)
    await analytics.record_view(1, uuid4(), test_stays.OWNER)
    await analytics.record_view(1, uuid4(), test_stays.GUEST)
    await analytics.record_view(2, visitor)
    page = PropertyAnalytics(**await analytics.overview(test_stays.OWNER, 2026))
    assert len(page.months) == 12 and page.months[0].views == 3
    assert (await analytics.overview(test_stays.OWNER, 2026, 1))["months"][0].views == 2
    stored = (await service.repository.db.scalars(select(PropertyView))).all()
    assert len(stored) == 3 and all(str(visitor) != row.visitor_hash for row in stored)
    assert len({row.visitor_hash for row in stored}) == 3
    monkeypatch.setattr(
        PropertyAnalyticsService, "today", staticmethod(lambda: date(2026, 2, 1))
    )
    await analytics.record_view(1, visitor)
    assert (await analytics.overview(test_stays.OWNER, 2026))["months"][1].views == 1
    listing = await service.repository.listing(1)
    listing.is_published = False
    await service.repository.db.commit()
    with pytest.raises(HTTPException) as error:
        await analytics.record_view(1, uuid4())
    assert error.value.status_code == 404
    assert (await analytics.overview(test_stays.OWNER, 2026, 1))["months"][0].views == 2


@pytest.mark.asyncio
async def test_month_and_year_boundaries_currency_separation_and_cancellations(
    service, analytics
):
    await add_stay(service, "2025-12-31", "2026-01-02", total_cents=3001)
    await add_stay(service, "2026-01-31", "2026-02-02")
    await add_stay(
        service,
        "2026-02-10",
        "2026-02-13",
        property_id=2,
        currency="USD",
        total_cents=6000,
    )
    await add_stay(
        service, "2026-01-05", "2026-01-07", status="cancelled", total_cents=999999
    )
    await add_stay(service, "2024-02-28", "2024-03-01", total_cents=600)
    page = await analytics.overview(test_stays.OWNER, 2026)
    january, february = page["months"][:2]
    assert (january.reservations, january.cancelled, january.nights) == (1, 1, 2)
    assert january.booked_value_cents == {"EUR": 2501}
    assert (february.reservations, february.nights) == (1, 4)
    assert february.booked_value_cents == {"EUR": 1000, "USD": 6000}
    only_first = await analytics.overview(test_stays.OWNER, 2026, 1)
    assert only_first["months"][1].booked_value_cents == {"EUR": 1000}
    previous = await analytics.overview(test_stays.OWNER, 2025)
    assert previous["months"][11].booked_value_cents == {"EUR": 1500}
    leap = await analytics.overview(test_stays.OWNER, 2024)
    assert leap["months"][1].nights == 2 and leap["months"][2].nights == 0


@pytest.mark.asyncio
async def test_owner_scope_and_empty_year(service, analytics):
    await add_stay(service, "2026-01-31", "2026-02-02")
    await analytics.record_view(1, uuid4())
    other = SimpleNamespace(id=3, role="owner")
    page = await analytics.overview(other, 2026)
    assert page["properties"] == []
    assert all(
        month.views == month.reservations == month.nights == 0
        for month in page["months"]
    )
    with pytest.raises(HTTPException) as error:
        await analytics.overview(other, 2026, 1)
    assert error.value.status_code == 404
    empty = await analytics.overview(test_stays.OWNER, 2030)
    assert all(
        month.views == month.reservations == month.nights == 0
        for month in empty["months"]
    )


def test_analytics_permissions_and_query_validation():
    app.dependency_overrides[get_db] = lambda: None
    app.dependency_overrides[get_current_user] = lambda: test_stays.GUEST
    try:
        with TestClient(app) as client:
            assert client.get("/owner/property-analytics?year=2026").status_code == 403
            app.dependency_overrides[get_current_user] = lambda: test_stays.OWNER
            for query in ("year=1999", "year=2101", "year=2026&property_id=0", ""):
                assert (
                    client.get(f"/owner/property-analytics?{query}").status_code == 422
                )
            assert (
                client.post(
                    "/properties/1/views", json={"visitor_id": "invalid"}
                ).status_code
                == 422
            )
    finally:
        app.dependency_overrides.clear()


def test_view_migration_roundtrip():
    engine = create_engine("sqlite://")
    with engine.begin() as connection:
        connection.execute(
            text("CREATE TABLE property_listings (id INTEGER PRIMARY KEY)")
        )
        connection.execute(text("INSERT INTO property_listings VALUES (1)"))
        migration = load_migration(
            "c94f1d546807_create_property_views.py",
            Operations(MigrationContext.configure(connection)),
        )
        migration.upgrade()
        assert inspect(connection).get_unique_constraints("property_views")[0][
            "column_names"
        ] == ["property_id", "viewed_on", "visitor_hash"]
        migration.downgrade()
        assert "property_views" not in inspect(connection).get_table_names()
        assert connection.scalar(text("SELECT id FROM property_listings")) == 1
    engine.dispose()


@pytest.mark.asyncio
@pytest.mark.skipif(
    not os.getenv("STAY_TEST_POSTGRES"),
    reason="PostgreSQL concurrency check runs in CI",
)
async def test_postgres_concurrent_views_count_once():
    schema = "property_analytics_test_" + uuid4().hex
    engine = create_async_engine(
        settings.DATABASE_URL,
        execution_options={"schema_translate_map": {None: schema}},
    )
    tables = [
        test_stays.User.__table__,
        test_stays.Venue.__table__,
        test_stays.PropertyListing.__table__,
        Stay.__table__,
        PropertyView.__table__,
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
        visitor = uuid4()

        async def record():
            async with sessions() as db:
                await PropertyAnalyticsService(db).record_view(1, visitor)

        await asyncio.gather(record(), record(), record())
        async with sessions() as db:
            page = await PropertyAnalyticsService(db).overview(
                test_stays.OWNER, PropertyAnalyticsService.today().year
            )
            assert sum(month.views for month in page["months"]) == 1
    finally:
        async with engine.begin() as connection:
            await connection.execute(DropSchema(schema, cascade=True))
        await engine.dispose()
