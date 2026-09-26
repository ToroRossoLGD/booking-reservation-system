from datetime import timedelta
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.api.routers.property_listings import owner_property
from app.core.dependencies import get_current_user
from app.db.session import get_db
from app.main import app
from app.models.stay import Stay
from app.services.stay_service import StayService
from tests import test_stays

service = test_stays.service


def test_owner_routes_reject_guests_and_invalid_filters():
    app.dependency_overrides[get_db] = lambda: None
    app.dependency_overrides[get_current_user] = lambda: test_stays.GUEST
    try:
        with TestClient(app) as client:
            assert client.get("/owner/stays").status_code == 403
            assert client.get("/owner/properties/1").status_code == 403
            app.dependency_overrides[get_current_user] = lambda: test_stays.OWNER
            for query in (
                "property_id=0",
                "status=pending",
                "day=tomorrow",
                "offset=-1",
                "limit=101",
            ):
                assert client.get(f"/owner/stays?{query}").status_code == 422
    finally:
        app.dependency_overrides.clear()


async def add_stay(service, **changes):
    stay = Stay(
        **(
            dict(
                property_id=1,
                venue_id=1,
                user_id=2,
                request_id=str(uuid4()),
                check_in=test_stays.TODAY,
                check_out=test_stays.TODAY + timedelta(days=2),
                guests=2,
                status="confirmed",
                title="Saved title",
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
    return await service.repository.save(stay)


@pytest.mark.asyncio
async def test_counts_filters_and_options_cover_all_pages(service):
    for _ in range(22):
        await add_stay(service)
    await add_stay(service, property_id=2, status="cancelled")
    await add_stay(
        service,
        property_id=2,
        check_in=test_stays.TODAY - timedelta(days=2),
        check_out=test_stays.TODAY,
    )
    page = await service.owner_overview(test_stays.OWNER, limit=1)
    assert (page.total, len(page.items), page.has_next) == (24, 1, True)
    assert (page.arrivals_today, page.departures_today) == (22, 1)
    assert {p.id for p in page.properties} == {1, 2}
    filtered = await service.owner_overview(
        test_stays.OWNER, property_id=2, status="cancelled"
    )
    assert filtered.total == 1 and filtered.items[0].status == "cancelled"
    assert (filtered.arrivals_today, filtered.departures_today) == (0, 1)
    arrivals = await service.owner_overview(
        test_stays.OWNER, day="arrivals", offset=20, limit=20
    )
    assert arrivals.total == 22 and len(arrivals.items) == 2 and not arrivals.has_next
    assert arrivals.items[0].guest_email == "user2@example.com"
    departures = await service.owner_overview(test_stays.OWNER, day="departures")
    assert departures.total == 1 and departures.items[0].property_id == 2


@pytest.mark.asyncio
async def test_daily_views_use_each_snapshot_timezone_and_sort_local_times(
    service, monkeypatch
):
    monkeypatch.setattr(
        StayService,
        "today",
        staticmethod(
            lambda zone: (
                test_stays.TODAY + timedelta(days=1)
                if zone == "Pacific/Kiritimati"
                else test_stays.TODAY
            )
        ),
    )
    late = await add_stay(service, check_in_time="16:00")
    early = await add_stay(
        service,
        timezone="Pacific/Kiritimati",
        check_in=test_stays.TODAY + timedelta(days=1),
        check_in_time="09:00",
    )
    unknown = await add_stay(service)
    await add_stay(service, timezone="Pacific/Kiritimati", check_in=test_stays.TODAY)
    page = await service.owner_overview(test_stays.OWNER, day="arrivals")
    assert page.arrivals_today == 3
    assert [item.id for item in page.items] == [early.id, late.id, unknown.id]


@pytest.mark.asyncio
async def test_other_owner_cannot_read_counts_options_or_private_listing(service):
    await add_stay(service)
    other = SimpleNamespace(id=3, role="owner")
    page = await service.owner_overview(other, property_id=1)
    assert (page.total, page.arrivals_today, page.departures_today) == (0, 0, 0)
    assert page.properties == []
    with pytest.raises(HTTPException) as error:
        await owner_property(1, service.repository.db, other)
    assert error.value.status_code == 403
    listing = await service.repository.listing(1)
    listing.is_published = False
    await service.repository.db.commit()
    result = await owner_property(1, service.repository.db, test_stays.OWNER)
    assert result.id == 1 and not result.is_published
    with pytest.raises(HTTPException) as error:
        await owner_property(999, service.repository.db, test_stays.OWNER)
    assert error.value.status_code == 404
