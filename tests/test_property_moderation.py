import os
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy import func, select

from app.models.notification import Notification
from app.models.property_listing import PropertyListing
from app.models.property_report import PropertyModerationEvent, PropertyReport
from app.models.user import User
from app.schemas.property_listing import PropertyListingRead, PropertyListingWrite
from app.schemas.property_moderation import ModerationAction, PropertyReportCreate
from app.services.property_listing_service import PropertyListingService
from app.services.property_moderation_service import PropertyModerationService
from tests.test_stays import GUEST, OTHER, OWNER, booking, listing_data
from tests.test_stays import service as stays  # noqa: F401

ADMIN = SimpleNamespace(id=4, role="admin")


@pytest.fixture
def service(stays):  # noqa: F811 - imported pytest fixture
    db = stays.repository.db
    engine = db.commit.side_effect.__self__.get_bind()
    PropertyReport.__table__.create(engine)
    PropertyModerationEvent.__table__.create(engine)
    db.add(User(id=4, role="admin", email="admin@example.com", hashed_password="test"))
    db.commit.side_effect()
    return PropertyModerationService(db)


def report_body(**changes):
    return PropertyReportCreate(
        **(
            dict(
                request_id=uuid4(),
                category="misleading",
                details="The description does not match the property.",
            )
            | changes
        )
    )


def action(kind, version=0, **changes):
    return ModerationAction(
        **(
            dict(
                request_id=uuid4(),
                action=kind,
                version=version,
                note="Please correct the listing description.",
            )
            | changes
        )
    )


@pytest.mark.asyncio
async def test_report_retry_pending_limit_ownership_and_privacy(service):
    body = report_body()
    report = await service.report(1, body, GUEST)
    assert (await service.report(1, body, GUEST)).id == report.id
    for property_id, data, user, status in (
        (1, report_body(), GUEST, 409),
        (2, body, GUEST, 409),
        (1, report_body(), OWNER, 400),
    ):
        with pytest.raises(HTTPException) as error:
            await service.report(property_id, data, user)
        assert error.value.status_code == status
    assert (await service.reports(OTHER)).total == 0
    assert (await service.reports(GUEST)).total == 1
    with pytest.raises(HTTPException):
        await service.reports(GUEST, admin=True)
    await service.act(1, action("hide"), ADMIN, report.id)
    await service.act(
        1, action("appeal", 1, note="Private explanation from owner."), OWNER
    )
    visible = (await service.reports(GUEST)).items[0]
    assert visible.listing.note == visible.listing.appeal == ""
    owner_history = (await service.history(1, OWNER)).model_dump_json()
    assert body.details not in owner_history and "user_id" not in owner_history
    with pytest.raises(HTTPException) as error:
        await service.history(1, GUEST)
    assert error.value.status_code == 404


@pytest.mark.asyncio
async def test_hide_preserves_stays_blocks_public_access_and_republication(
    service,
    stays,  # noqa: F811 - imported pytest fixture
):
    stay = await stays.create(1, booking(), GUEST)
    report = await service.report(1, report_body(), OTHER)
    command = action("hide")
    result = await service.act(1, command, ADMIN, report.id)
    assert result.state == "suspended" and not result.is_published
    assert (await service.act(1, command, ADMIN, report.id)).version == 1
    listings = PropertyListingService(service.db)
    assert (await listings.search(property_id=1)).total == 0
    for call in (listings.get_public(1), stays.quote(1, booking())):
        with pytest.raises(HTTPException) as error:
            await call
        assert error.value.status_code == 404
    assert (await stays.list(GUEST)).items[0].id == stay.id
    with pytest.raises(HTTPException) as error:
        await listings.update(1, PropertyListingWrite(**listing_data()), OWNER)
    assert error.value.status_code == 409
    draft = await listings.update(
        1,
        PropertyListingWrite(
            **listing_data(
                is_published=False, description="Corrected apartment description."
            )
        ),
        OWNER,
    )
    assert draft.moderation_state == "suspended"
    # Moderation fields cannot escape via the public/owner listing DTO.
    assert (
        "moderation_note" not in PropertyListingRead.model_validate(draft).model_dump()
    )
    await service.act(1, action("appeal", 1), OWNER)
    with pytest.raises(HTTPException):
        await service.act(1, action("restore", 1), ADMIN)
    restored = await service.act(1, action("restore", 2), ADMIN)
    assert restored.state == "clear" and not restored.is_published
    await listings.update(1, PropertyListingWrite(**listing_data()), OWNER)
    assert (await listings.get_public(1)).is_published
    assert (await service.history(1, OWNER, limit=2)).has_next


@pytest.mark.asyncio
async def test_dismiss_appeal_uphold_and_access_control(service):
    report = await service.report(1, report_body(), GUEST)
    for who, operation in ((GUEST, "hide"), (OWNER, "restore"), (OTHER, "appeal")):
        with pytest.raises(HTTPException):
            await service.act(
                1, action(operation), who, report.id if operation == "hide" else None
            )
    result = await service.act(1, action("dismiss"), ADMIN, report.id)
    assert result.state == "clear" and result.is_published
    assert (await service.reports(GUEST)).items[0].status == "dismissed"
    report = await service.report(1, report_body(), GUEST)
    await service.act(1, action("hide", 1), ADMIN, report.id)
    await service.act(1, action("appeal", 2), OWNER)
    with pytest.raises(HTTPException):
        await service.act(1, action("appeal", 3), OWNER)
    await service.act(1, action("uphold", 3), ADMIN)
    assert (await service.cases(OWNER)).items[0].state == "suspended"
    assert (await service.cases(OTHER)).total == 0


@pytest.mark.asyncio
async def test_failed_moderation_rolls_back_listing_report_events_and_notifications(
    service,
):
    report = await service.report(1, report_body(), GUEST)
    report_id = report.id
    commit = service.db.commit.side_effect
    service.db.commit.side_effect = RuntimeError("database failure")
    command = action("hide")
    with pytest.raises(RuntimeError):
        await service.act(1, command, ADMIN, report_id)
    await service.db.rollback()
    service.db.commit.side_effect = commit
    assert (await service.listing(1)).is_published
    assert await service.db.scalar(select(func.count(PropertyModerationEvent.id))) == 0
    assert await service.db.scalar(select(func.count(Notification.id))) == 0
    assert (await service.reports(GUEST)).items[0].status == "pending"
    await service.act(1, command, ADMIN, report_id)
    assert await service.db.scalar(select(func.count(Notification.id))) == 2


def test_migration_preserves_public_listings_and_enforces_suspension():
    import importlib.util
    from pathlib import Path

    from alembic.migration import MigrationContext
    from alembic.operations import Operations
    from sqlalchemy import create_engine, inspect, text
    from sqlalchemy.exc import IntegrityError

    path = (
        Path(__file__).parents[1]
        / "alembic/versions/a1d917546801_add_property_moderation.py"
    )
    spec = importlib.util.spec_from_file_location("moderation_migration", path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    engine = create_engine("sqlite://")
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE users (id INTEGER PRIMARY KEY)"))
        connection.execute(
            text(
                "CREATE TABLE property_listings "
                "(id INTEGER PRIMARY KEY, is_published BOOLEAN)"
            )
        )
        connection.execute(text("INSERT INTO property_listings VALUES (1, true)"))
        migration.op = Operations(MigrationContext.configure(connection))
        migration.upgrade()
        assert connection.execute(
            text(
                "SELECT is_published, moderation_state, moderation_version "
                "FROM property_listings"
            )
        ).one() == (True, "clear", 0)
        with pytest.raises(IntegrityError), connection.begin_nested():
            connection.execute(
                text("UPDATE property_listings SET moderation_state='suspended'")
            )
        connection.execute(
            text(
                "UPDATE property_listings SET is_published=false, "
                "moderation_state='suspended'"
            )
        )
        migration.downgrade()
        assert "property_reports" not in inspect(connection).get_table_names()
        assert connection.scalar(text("SELECT count(*) FROM property_listings")) == 1
    engine.dispose()


def test_routes_reject_unauthenticated_access():
    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as client:
        for path in (
            "/property-reports/mine",
            "/admin/property-reports",
            "/owner/property-moderation",
            "/admin/property-moderation",
            "/properties/1/moderation-history",
        ):
            assert client.get(path).status_code == 401
        for path in (
            "/properties/1/reports",
            "/properties/1/moderation",
            "/admin/properties/1/reports/1/decision",
        ):
            assert client.post(path, json={}).status_code == 401


@pytest.mark.asyncio
@pytest.mark.skipif(
    not os.getenv("STAY_TEST_POSTGRES"), reason="CI runs PostgreSQL locking"
)
async def test_postgres_concurrent_moderation_decisions(monkeypatch):
    import asyncio

    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
    from sqlalchemy.schema import CreateSchema, DropSchema

    from app.core.config import settings
    from app.db.base import Base
    from app.models.venue import Venue

    schema = "moderation_test_" + uuid4().hex
    engine = create_async_engine(
        settings.DATABASE_URL,
        execution_options={"schema_translate_map": {None: schema}},
    )
    try:
        async with engine.begin() as connection:
            await connection.execute(CreateSchema(schema))
            tables = [
                m.__table__
                for m in (
                    User,
                    Venue,
                    PropertyListing,
                    PropertyReport,
                    PropertyModerationEvent,
                    Notification,
                )
            ]
            await connection.run_sync(
                lambda sync: Base.metadata.create_all(sync, tables=tables)
            )
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        async with sessions() as db:
            db.add_all(
                [
                    User(
                        id=i,
                        email=f"mod{i}@example.com",
                        hashed_password="test",
                        role="admin" if i == 4 else "customer",
                    )
                    for i in (1, 2, 4)
                ]
            )
            await db.flush()
            db.add(Venue(id=1, owner_id=1, name="Apartment", address="Test"))
            await db.flush()
            db.add(PropertyListing(id=1, **listing_data()))
            await db.commit()
            report = await PropertyModerationService(db).report(1, report_body(), GUEST)
            report_id = report.id

        async def decide(kind):
            async with sessions() as db:
                try:
                    await PropertyModerationService(db).act(
                        1, action(kind), ADMIN, report_id
                    )
                    return "ok"
                except HTTPException as error:
                    assert error.status_code == 409
                    return "conflict"

        results = await asyncio.wait_for(
            asyncio.gather(decide("hide"), decide("dismiss")), timeout=15
        )
        assert sorted(results) == ["conflict", "ok"]
        async with sessions() as db:
            assert await db.scalar(select(func.count(PropertyModerationEvent.id))) == 1
    finally:
        async with engine.begin() as connection:
            await connection.execute(DropSchema(schema, cascade=True, if_exists=True))
        await engine.dispose()
