import asyncio
import os
from datetime import timedelta
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import FastAPI, HTTPException
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.schema import CreateSchema, DropSchema

from app.api.routers.stay_blocks import router
from app.core.config import settings
from app.core.dependencies import get_current_user
from app.db.base import Base
from app.db.session import get_db
from app.models.stay_block import StayBlock
from app.services.occupancy_import_service import OccupancyImportService, parse_calendar
from app.services.stay_service import StayService
from tests import test_stays
from tests.test_stays import GUEST, OWNER, TODAY, booking

stay_service = test_stays.service


def event(start=2, end=5, extra=""):
    return (
        "BEGIN:VEVENT\r\n"
        f"DTSTART;VALUE=DATE:{TODAY + timedelta(days=start):%Y%m%d}\r\n"
        f"DTEND;VALUE=DATE:{TODAY + timedelta(days=end):%Y%m%d}\r\n"
        "SUMMARY:Private guest\r\nDESCRIPTION:Never store this\r\n"
        f"{extra}END:VEVENT\r\n"
    )


def calendar(*events):
    return "BEGIN:VCALENDAR\r\nVERSION:2.0\r\n" + "".join(events) + "END:VCALENDAR\r\n"


@pytest.fixture
def importer(stay_service, monkeypatch):
    monkeypatch.setattr(settings, "DEMO_MODE", False)
    return OccupancyImportService(stay_service.repository.db)


@pytest.mark.parametrize(
    "content",
    [
        "not an ICS file",
        calendar(event(extra="RRULE:FREQ=DAILY\r\n")),
        calendar(event(extra="RECURRENCE-ID;VALUE=DATE:20261003\r\n")),
        calendar(event(extra="DURATION:P1D\r\n")),
        calendar(
            event().replace("DTSTART;VALUE=DATE:20261003", "DTSTART:20261003T120000Z")
        ),
        calendar(event().replace("20261003", "20260230")),
        calendar(event(extra="DTSTART;VALUE=DATE:20261003\r\n")),
        calendar(event(5, 2)),
        calendar(event()).replace("END:VEVENT", "END:VTODO"),
        calendar(event(extra="BEGIN:VALARM\r\nEND:VALARM\r\n")),
        calendar(*[event() for _ in range(101)]),
        "x" * 100_001,
        calendar(event()).replace("VERSION:2.0", "VERSION:1.0"),
        calendar(event()).replace("VERSION:2.0", "VERSION:2.0\r\nMETHOD:CANCEL"),
        "\ud800",
    ],
    ids=[f"invalid-{index}" for index in range(15)],
)
def test_rejects_unsupported_or_malformed_calendars(content):
    with pytest.raises(HTTPException) as error:
        parse_calendar(content)
    assert error.value.status_code == 400


def test_unfolding_single_day_and_skipped_events():
    content = calendar(
        event(extra="STATUS:CANCELLED\r\n"),
        event(extra="TRANSP:TRANSPARENT\r\n"),
        "BEGIN:VEVENT\r\nDTSTART;VALUE=\r\n DATE:20261003\r\nEND:VEVENT\r\n",
    )
    assert parse_calendar(content) == (
        [(TODAY + timedelta(days=2), TODAY + timedelta(days=3))],
        2,
    )


@pytest.mark.asyncio
async def test_preview_merge_clip_import_retry_and_shared_inventory(
    importer, stay_service
):
    content = calendar(
        event(-2, 2),
        event(2, 5),
        event(10, 12),
        event(10, 12),
        event(-10, -5),
        event(370, 372),
    )
    result = await importer.run(1, OWNER, content)
    assert len(result["ranges"]) == 2
    assert result["ranges"][0]["check_in"] == TODAY
    assert result["ignored"] == 2 and result["clipped"] == 1
    assert not result["applied"]
    assert await importer.db.scalar(select(func.count(StayBlock.id))) == 0
    result = await importer.run(1, OWNER, content, apply=True)
    assert result["created"] == 2 and result["applied"]
    retry = await importer.run(2, OWNER, content, apply=True)
    assert retry["created"] == 0 and retry["applied"]
    assert {item["status"] for item in retry["ranges"]} == {"existing"}
    assert await importer.db.scalar(select(func.count(StayBlock.id))) == 2
    block = await importer.db.scalar(select(StayBlock).limit(1))
    assert block.reason == "iCal import"
    with pytest.raises(HTTPException) as error:
        await stay_service.create(2, booking(), GUEST)
    assert error.value.status_code == 409
    await importer.remove(2, block.id, OWNER)
    assert (await stay_service.create(2, booking(), GUEST)).status == "confirmed"


@pytest.mark.asyncio
async def test_conflict_after_preview_is_atomic_and_respects_preparation(
    importer, stay_service
):
    content = calendar(event(1, 2), event(20, 22))
    assert {
        item["status"] for item in (await importer.run(1, OWNER, content))["ranges"]
    } == {"ready"}
    listing = await importer.stays.listing(2)
    listing.preparation_days = 1
    await importer.db.commit()
    await stay_service.create(2, booking(), GUEST)
    result = await importer.run(1, OWNER, content, apply=True)
    assert not result["applied"] and result["created"] == 0
    assert [item["status"] for item in result["ranges"]] == ["conflict", "ready"]
    assert await importer.db.scalar(select(func.count(StayBlock.id))) == 0


@pytest.mark.asyncio
async def test_permissions_demo_type_and_http(importer, monkeypatch):
    for actor in (GUEST, SimpleNamespace(id=99, role="owner")):
        with pytest.raises(HTTPException) as error:
            await importer.run(1, actor, calendar(event()), apply=True)
        assert error.value.status_code == 403
    monkeypatch.setattr(settings, "DEMO_MODE", True)
    with pytest.raises(HTTPException) as error:
        await importer.run(1, OWNER, calendar(event()), apply=True)
    assert error.value.status_code == 403
    monkeypatch.setattr(settings, "DEMO_MODE", False)
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_db] = lambda: importer.db
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        path = "/owner/properties/1/occupancy-import"
        assert (
            await client.post(path, json={"content": calendar(event())})
        ).status_code == 401
        app.dependency_overrides[get_current_user] = lambda: OWNER
        preview = await client.post(
            path + "/preview", json={"content": calendar(event())}
        )
        assert preview.status_code == 200 and not preview.json()["applied"]
        assert "Private guest" not in preview.text
        assert (
            await client.post(path, json={"content": "x" * 100_001})
        ).status_code == 422
        assert (await client.post(path, json={"content": calendar(event())})).json()[
            "created"
        ] == 1
    listing = await importer.stays.listing(1)
    listing.offer_type = "sale"
    await importer.db.commit()
    with pytest.raises(HTTPException) as error:
        await importer.run(1, OWNER, calendar(event()))
    assert error.value.status_code == 400


@pytest.mark.asyncio
@pytest.mark.skipif(not os.getenv("STAY_TEST_POSTGRES"), reason="Requires PostgreSQL")
async def test_postgres_import_serializes_with_alias_booking(monkeypatch):
    monkeypatch.setattr(settings, "DEMO_MODE", False)
    monkeypatch.setattr(StayService, "today", staticmethod(lambda zone: TODAY))
    schema = "import_test_" + uuid4().hex
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
                        test_stays.User.__table__,
                        test_stays.Venue.__table__,
                        test_stays.PropertyListing.__table__,
                        test_stays.Resource.__table__,
                        test_stays.Stay.__table__,
                        StayBlock.__table__,
                        test_stays.Notification.__table__,
                    ],
                )
            )
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        async with sessions() as db:
            await db.run_sync(test_stays.seed)

        async def import_attempt():
            async with sessions() as db:
                return (
                    await OccupancyImportService(db).run(
                        1, OWNER, calendar(event()), apply=True
                    )
                )["applied"]

        async def booking_attempt():
            async with sessions() as db:
                try:
                    await StayService(db).create(2, booking(), GUEST)
                    return True
                except HTTPException as error:
                    assert error.status_code == 409
                    return False

        outcomes = await asyncio.gather(import_attempt(), booking_attempt())
        assert sum(outcomes) == 1
    finally:
        async with engine.begin() as connection:
            await connection.execute(DropSchema(schema, cascade=True))
        await engine.dispose()
