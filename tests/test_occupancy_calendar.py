from datetime import timedelta
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.models.property_listing import PropertyListing
from app.models.stay_block import StayBlock
from app.services.occupancy_calendar_service import OccupancyCalendarService
from app.services.stay_block_service import StayBlockService
from tests import test_stays
from tests.test_stay_blocks import block_data
from tests.test_stays import GUEST, OWNER, TODAY, booking

stay_service = test_stays.service


@pytest.mark.asyncio
async def test_shared_occupancy_privacy_cancellation_and_blocks(stay_service):
    db = stay_service.repository.db
    service = OccupancyCalendarService(db)
    stay = await stay_service.create(1, booking(), GUEST)
    blocks = StayBlockService(db)
    block = await blocks.create(
        2,
        block_data(
            check_in=TODAY + timedelta(days=8), check_out=TODAY + timedelta(days=10)
        ),
        OWNER,
    )
    content = await service.export(2, OWNER)
    assert content.count("BEGIN:VEVENT") == 2
    assert f"DTSTART;VALUE=DATE:{stay.check_in:%Y%m%d}" in content
    assert f"DTEND;VALUE=DATE:{stay.check_out:%Y%m%d}" in content
    assert "SUMMARY:Unavailable" in content
    for secret in [
        stay.contact_email,
        stay.title,
        block.reason,
        "DESCRIPTION",
        "LOCATION",
    ]:
        assert secret not in content
    assert all(len(line.encode()) <= 75 for line in content.split("\r\n"))

    def uids(value):
        return [line for line in value.splitlines() if line.startswith("UID:")]

    assert uids(content) == uids(await service.export(1, OWNER))
    stay.status = "cancelled"
    await db.commit()
    await blocks.remove(1, block.id, OWNER)
    assert "BEGIN:VEVENT" not in await service.export(1, OWNER)


@pytest.mark.asyncio
async def test_preparation_union_and_authorization(stay_service):
    db = stay_service.repository.db
    service = OccupancyCalendarService(db)
    await stay_service.create(1, booking(), GUEST)
    listing = await db.get(PropertyListing, 2)
    listing.preparation_days = 2
    await db.commit()
    await StayBlockService(db).create(
        1,
        block_data(
            check_in=TODAY + timedelta(days=7), check_out=TODAY + timedelta(days=9)
        ),
        OWNER,
    )
    content = await service.export(1, OWNER)
    assert content.count("BEGIN:VEVENT") == 1
    assert f"DTSTART;VALUE=DATE:{TODAY:%Y%m%d}" in content
    assert f"DTEND;VALUE=DATE:{TODAY + timedelta(days=9):%Y%m%d}" in content
    for user in [GUEST, SimpleNamespace(id=99, role="owner")]:
        with pytest.raises(HTTPException) as error:
            await service.export(1, user)
        assert error.value.status_code == 403
    assert await service.export(1, SimpleNamespace(id=99, role="admin"))
    with pytest.raises(HTTPException) as error:
        await service.export(999, OWNER)
    assert error.value.status_code == 404
    listing.offer_type = "sale"
    await db.commit()
    with pytest.raises(HTTPException) as error:
        await service.export(2, OWNER)
    assert error.value.status_code == 400


@pytest.mark.asyncio
async def test_window_clipping_and_http_contract(stay_service):
    from fastapi import FastAPI
    from httpx import ASGITransport, AsyncClient

    from app.api.routers.stay_blocks import router
    from app.core.dependencies import get_current_user
    from app.db.session import get_db

    db = stay_service.repository.db
    for index, (left, right) in enumerate([(-5, 2), (364, 370), (365, 380)]):
        db.add(
            StayBlock(
                venue_id=1,
                created_by_id=OWNER.id,
                request_id=f"window-{index}",
                check_in=TODAY + timedelta(days=left),
                check_out=TODAY + timedelta(days=right),
                active=True,
                reason="secret",
            )
        )
    await db.commit()
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: OWNER
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/owner/properties/1/occupancy.ics")
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/calendar")
        assert response.headers["cache-control"] == "private, no-store"
        assert "bookica-occupancy-1.ics" in response.headers["content-disposition"]
        assert response.text.count("BEGIN:VEVENT") == 2
        assert f"DTSTART;VALUE=DATE:{TODAY:%Y%m%d}" in response.text
        assert f"DTEND;VALUE=DATE:{TODAY + timedelta(days=365):%Y%m%d}" in response.text
        assert "secret" not in response.text
        app.dependency_overrides[get_current_user] = lambda: GUEST
        assert (
            await client.get("/owner/properties/1/occupancy.ics")
        ).status_code == 403
        del app.dependency_overrides[get_current_user]
        assert (
            await client.get("/owner/properties/1/occupancy.ics")
        ).status_code == 401
