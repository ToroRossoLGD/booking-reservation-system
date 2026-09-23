from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from app.db.session import get_db
from app.main import app
from app.schemas.property_listing import PropertyListingWrite, PropertySearch
from tests.test_property_listings import payload, service  # noqa: F401


@pytest.mark.asyncio
async def test_combined_filters_boundaries_currency_and_draft_privacy(service):  # noqa: F811
    owner = SimpleNamespace(id=1, role="owner")
    defaults = dict(
        is_published=True,
        offer_type="long_term",
        price_cents=50000,
        area_sqm=30,
        rooms=0,
    )
    for changes in [
        {},
        {"price_cents": 60000},
        {"price_cents": 49999},
        {"price_cents": 60001},
        {"currency": "RSD"},
        {"offer_type": "short_stay"},
        {"is_published": False},
        {"area_sqm": 29},
        {"area_sqm": 41},
        {"rooms": 1},
        {"city": "Beograd"},
    ]:
        await service.create(
            PropertyListingWrite(**payload(**(defaults | changes))), owner
        )
    filters = PropertySearch(
        city="novi",
        offer_type="long_term",
        currency="EUR",
        min_price_cents=50000,
        max_price_cents=60000,
        min_area_sqm=30,
        max_area_sqm=40,
        rooms=0,
        sort="price_asc",
        limit=1,
    )
    first = await service.search(**filters.model_dump())
    second = await service.search(**(filters.model_dump() | {"offset": 1}))
    assert first.total == second.total == 2
    assert first.items[0].price_cents == 50000 and first.has_next
    assert second.items[0].price_cents == 60000 and not second.has_next


@pytest.mark.asyncio
async def test_sorting_ties_and_zero_price_bound(service):  # noqa: F811
    owner = SimpleNamespace(id=1, role="owner")
    for price, area in [(50000, 30), (50000, 50), (60000, 40)]:
        await service.create(
            PropertyListingWrite(
                **payload(is_published=True, price_cents=price, area_sqm=area)
            ),
            owner,
        )
    for sort, expected in [
        ("newest", [3, 2, 1]),
        ("price_asc", [2, 1, 3]),
        ("price_desc", [3, 2, 1]),
        ("area_desc", [2, 3, 1]),
    ]:
        ids = []
        for offset in range(3):
            page = await service.search(
                offer_type="sale", currency="EUR", sort=sort, limit=1, offset=offset
            )
            ids.append(page.items[0].id)
        assert ids == expected
    assert (
        await service.search(offer_type="sale", currency="EUR", max_price_cents=0)
    ).total == 0


@pytest.mark.parametrize(
    "query",
    [
        "min_price_cents=1",
        "sort=price_asc",
        "sort=price_desc&offer_type=sale",
        "min_price_cents=1&currency=EUR",
        "currency=GBP",
        "rooms=-1",
        "rooms=101",
        "rooms=0.5",
        "min_area_sqm=0",
        "max_area_sqm=100001",
        "sort=invalid",
        "min_area_sqm=50&max_area_sqm=49",
        "min_price_cents=-1",
        "min_price_cents=1000000000001",
        "min_price_cents=1.1",
        "offer_type=sale&currency=EUR&min_price_cents=2&max_price_cents=1",
    ],
)
def test_invalid_search_returns_422_without_querying_database(query):
    db = AsyncMock()
    app.dependency_overrides[get_db] = lambda: db
    try:
        with TestClient(app) as client:
            assert client.get(f"/properties?{query}").status_code == 422
        db.scalar.assert_not_awaited()
        db.scalars.assert_not_awaited()
    finally:
        app.dependency_overrides.clear()
