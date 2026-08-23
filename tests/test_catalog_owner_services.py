from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException

from app.models.reservation import ReservationStatus
from app.models.resource import Resource
from app.models.venue import Venue
from app.schemas.resource import ResourceCreate
from app.schemas.venue import VenueCreate
from app.services.owner_service import OwnerService
from app.services.resource_service import ResourceService
from app.services.venue_service import VenueService


def user(user_id=10, role="owner"):
    return SimpleNamespace(id=user_id, role=role)


def venue(**changes):
    values = {
        "id": 7,
        "name": "Riverside Sports Center",
        "description": "Indoor courts",
        "address": "12 River Road",
        "owner_id": 10,
    }
    values.update(changes)
    return SimpleNamespace(**values)


def resource(**changes):
    values = {
        "id": 4,
        "name": "Court One",
        "resource_type": "court",
        "capacity": 4,
        "hourly_rate_cents": 2500,
        "currency": "EUR",
        "venue_id": 7,
    }
    values.update(changes)
    return SimpleNamespace(**values)


@pytest.mark.asyncio
async def test_venue_creation_maps_all_business_rules_and_owner():
    service = VenueService(AsyncMock())
    service.venue_repository.create = AsyncMock(side_effect=lambda item: item)
    data = VenueCreate(
        name="Riverside Sports Center",
        description="Indoor courts",
        address="12 River Road",
        free_cancellation_hours=36,
        late_cancellation_refund_percent=25,
        minimum_booking_notice_minutes=120,
        maximum_advance_booking_days=180,
        minimum_booking_duration_minutes=45,
        maximum_booking_duration_minutes=240,
        max_active_reservations_per_customer=3,
    )

    result = await service.create_venue(data, user())

    assert isinstance(result, Venue)
    assert result.owner_id == 10
    assert result.free_cancellation_hours == 36
    assert result.late_cancellation_refund_percent == 25
    assert result.minimum_booking_notice_minutes == 120
    assert result.maximum_advance_booking_days == 180
    assert result.minimum_booking_duration_minutes == 45
    assert result.maximum_booking_duration_minutes == 240
    assert result.max_active_reservations_per_customer == 3


@pytest.mark.asyncio
async def test_get_venue_returns_not_found_for_unknown_id():
    service = VenueService(AsyncMock())
    service.venue_repository.get_by_id = AsyncMock(return_value=None)

    with pytest.raises(HTTPException) as error:
        await service.get_venue_by_id(999)

    assert error.value.status_code == 404
    assert error.value.detail == "Venue not found"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("query", "limit", "offset", "detail"),
    [
        (" x ", 20, 0, "Search query must contain at least 2 characters"),
        ("court", 0, 0, "limit must be between 1 and 100"),
        ("court", 101, 0, "limit must be between 1 and 100"),
        ("court", 20, -1, "offset must be greater than or equal to 0"),
    ],
)
async def test_venue_search_validates_before_querying(query, limit, offset, detail):
    service = VenueService(AsyncMock())
    service.venue_repository.search = AsyncMock()

    with pytest.raises(HTTPException) as error:
        await service.search_venues(query, limit, offset)

    assert error.value.status_code == 400
    assert error.value.detail == detail
    service.venue_repository.search.assert_not_awaited()


@pytest.mark.asyncio
async def test_venue_search_trims_query_and_computes_next_page():
    service = VenueService(AsyncMock())
    items = [venue()]
    service.venue_repository.search = AsyncMock(return_value=items)
    service.venue_repository.count_search = AsyncMock(return_value=25)

    result = await service.search_venues("  river  ", limit=10, offset=10)

    assert result == {
        "items": items,
        "total": 25,
        "limit": 10,
        "offset": 10,
        "has_next": True,
    }
    service.venue_repository.search.assert_awaited_once_with(
        query_text="river", limit=10, offset=10
    )
    service.venue_repository.count_search.assert_awaited_once_with(query_text="river")


@pytest.mark.asyncio
async def test_resource_creation_normalizes_currency_and_uses_venue():
    service = ResourceService(AsyncMock())
    service.venue_repository.get_by_id = AsyncMock(return_value=venue())
    service.resource_repository.create = AsyncMock(side_effect=lambda item: item)
    data = ResourceCreate(
        name="Court One",
        resource_type="court",
        capacity=4,
        hourly_rate_cents=2500,
        currency="usd",
    )

    result = await service.create_resource(7, data, user())

    assert isinstance(result, Resource)
    assert result.venue_id == 7
    assert result.currency == "USD"
    assert result.hourly_rate_cents == 2500


@pytest.mark.asyncio
async def test_resource_creation_rejects_missing_venue_without_persisting():
    service = ResourceService(AsyncMock())
    service.venue_repository.get_by_id = AsyncMock(return_value=None)
    service.resource_repository.create = AsyncMock()

    with pytest.raises(HTTPException) as error:
        await service.create_resource(
            99,
            ResourceCreate(
                name="Court One",
                resource_type="court",
                hourly_rate_cents=2500,
            ),
            user(),
        )

    assert error.value.status_code == 404
    service.resource_repository.create.assert_not_awaited()


@pytest.mark.asyncio
async def test_non_owner_cannot_create_resource_for_another_venue():
    service = ResourceService(AsyncMock())
    service.venue_repository.get_by_id = AsyncMock(return_value=venue(owner_id=99))
    service.resource_repository.create = AsyncMock()

    with pytest.raises(HTTPException) as error:
        await service.create_resource(
            7,
            ResourceCreate(
                name="Court One",
                resource_type="court",
                hourly_rate_cents=2500,
            ),
            user(),
        )

    assert error.value.status_code == 403
    service.resource_repository.create.assert_not_awaited()


@pytest.mark.asyncio
async def test_admin_can_create_resource_for_any_venue():
    service = ResourceService(AsyncMock())
    service.venue_repository.get_by_id = AsyncMock(return_value=venue(owner_id=99))
    service.resource_repository.create = AsyncMock(side_effect=lambda item: item)

    result = await service.create_resource(
        7,
        ResourceCreate(name="Court One", resource_type="court", hourly_rate_cents=2500),
        user(1, "admin"),
    )

    assert result.venue_id == 7


@pytest.mark.asyncio
async def test_resource_list_rejects_unknown_venue_before_query():
    service = ResourceService(AsyncMock())
    service.venue_repository.get_by_id = AsyncMock(return_value=None)
    service.resource_repository.get_by_venue_id = AsyncMock()

    with pytest.raises(HTTPException) as error:
        await service.get_resources_by_venue(99)

    assert error.value.status_code == 404
    service.resource_repository.get_by_venue_id.assert_not_awaited()


@pytest.mark.asyncio
async def test_resource_lookup_rejects_unknown_resource():
    service = ResourceService(AsyncMock())
    service.resource_repository.get_by_id = AsyncMock(return_value=None)

    with pytest.raises(HTTPException) as error:
        await service.get_resource_by_id(99)

    assert error.value.status_code == 404


@pytest.mark.asyncio
async def test_resource_delete_rejects_orphaned_venue_without_deleting():
    service = ResourceService(AsyncMock())
    service.resource_repository.get_by_id = AsyncMock(return_value=resource())
    service.venue_repository.get_by_id = AsyncMock(return_value=None)
    service.resource_repository.delete = AsyncMock()

    with pytest.raises(HTTPException) as error:
        await service.delete_resource(4, user())

    assert error.value.status_code == 404
    service.resource_repository.delete.assert_not_awaited()


@pytest.mark.asyncio
async def test_resource_delete_enforces_owner_and_admin_override():
    service = ResourceService(AsyncMock())
    item = resource()
    service.resource_repository.get_by_id = AsyncMock(return_value=item)
    service.venue_repository.get_by_id = AsyncMock(return_value=venue(owner_id=99))
    service.resource_repository.delete = AsyncMock()

    with pytest.raises(HTTPException) as error:
        await service.delete_resource(4, user())
    assert error.value.status_code == 403
    service.resource_repository.delete.assert_not_awaited()

    await service.delete_resource(4, user(1, "admin"))
    service.resource_repository.delete.assert_awaited_once_with(item)


@pytest.mark.asyncio
async def test_resource_search_normalizes_optional_filter_and_maps_venue_data():
    service = ResourceService(AsyncMock())
    service.resource_repository.search = AsyncMock(return_value=[(resource(), venue())])
    service.resource_repository.count_search = AsyncMock(return_value=11)

    result = await service.search_resources(
        "  court  ", limit=10, offset=0, resource_type="   "
    )

    assert result.total == 11
    assert result.has_next is True
    assert result.items[0].venue_name == "Riverside Sports Center"
    service.resource_repository.search.assert_awaited_once_with(
        query_text="court", limit=10, offset=0, resource_type=None
    )
    service.resource_repository.count_search.assert_awaited_once_with(
        query_text="court", resource_type=None
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("query", "limit", "offset"),
    [("x", 20, 0), ("court", 0, 0), ("court", 101, 0), ("court", 20, -1)],
)
async def test_resource_search_rejects_invalid_inputs_before_query(
    query, limit, offset
):
    service = ResourceService(AsyncMock())
    service.resource_repository.search = AsyncMock()

    with pytest.raises(HTTPException) as error:
        await service.search_resources(query, limit, offset)

    assert error.value.status_code == 400
    service.resource_repository.search.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("start", "end", "minimum_capacity", "limit", "offset", "query"),
    [
        (datetime(2026, 9, 1, 9), datetime(2026, 9, 1, 10), 1, 20, 0, None),
        (
            datetime(2026, 9, 1, 10, tzinfo=UTC),
            datetime(2026, 9, 1, 9, tzinfo=UTC),
            1,
            20,
            0,
            None,
        ),
        (
            datetime(2026, 9, 1, 23, tzinfo=UTC),
            datetime(2026, 9, 2, 1, tzinfo=UTC),
            1,
            20,
            0,
            None,
        ),
        (
            datetime(2026, 9, 1, 9, tzinfo=UTC),
            datetime(2026, 9, 1, 10, tzinfo=UTC),
            0,
            20,
            0,
            None,
        ),
        (
            datetime(2026, 9, 1, 9, tzinfo=UTC),
            datetime(2026, 9, 1, 10, tzinfo=UTC),
            1,
            20,
            0,
            "x",
        ),
    ],
)
async def test_available_search_rejects_invalid_intervals_and_filters(
    start, end, minimum_capacity, limit, offset, query
):
    service = ResourceService(AsyncMock())
    service.resource_repository.get_available_candidates = AsyncMock()

    with pytest.raises(HTTPException) as error:
        await service.search_available_resources(
            start,
            end,
            minimum_capacity,
            limit,
            offset,
            query_text=query,
        )

    assert error.value.status_code == 400
    service.resource_repository.get_available_candidates.assert_not_awaited()


@pytest.mark.asyncio
async def test_available_search_paginates_after_capacity_filtering():
    service = ResourceService(AsyncMock())
    start = datetime(2026, 9, 1, 9, tzinfo=UTC)
    candidates = [(resource(id=index), venue()) for index in range(1, 5)]
    service.resource_repository.get_available_candidates = AsyncMock(
        return_value=candidates
    )
    service.reservation_repository.get_capacity_availability = AsyncMock(
        side_effect=[(4, 4), (4, 1), (4, 3), (4, 4)]
    )

    result = await service.search_available_resources(
        start,
        start + timedelta(hours=1),
        minimum_capacity=2,
        limit=2,
        offset=1,
        query_text="  court  ",
        resource_type="  court  ",
    )

    assert result.total == 3
    assert [item.id for item in result.items] == [3, 4]
    assert result.has_next is False
    service.resource_repository.get_available_candidates.assert_awaited_once_with(
        start_time=start,
        end_time=start + timedelta(hours=1),
        minimum_capacity=2,
        query_text="court",
        resource_type="court",
    )


@pytest.mark.asyncio
async def test_owner_resource_and_reservation_views_map_joined_rows():
    service = OwnerService(AsyncMock())
    owner = user()
    item = resource()
    location = venue()
    booking = SimpleNamespace(
        id=15,
        start_time=datetime(2026, 9, 1, 9, tzinfo=UTC),
        end_time=datetime(2026, 9, 1, 10, tzinfo=UTC),
        status="confirmed",
        user_id=30,
    )
    service.resource_repository.get_by_owner_id = AsyncMock(
        return_value=[(item, location)]
    )
    service.reservation_repository.get_by_owner_id = AsyncMock(
        return_value=[(booking, item, location)]
    )

    resources = await service.get_my_resources(owner)
    reservations = await service.get_my_reservations(owner)

    assert resources[0].venue_name == location.name
    assert reservations[0].resource_name == item.name
    assert reservations[0].venue_id == location.id
    service.resource_repository.get_by_owner_id.assert_awaited_once_with(owner.id)
    service.reservation_repository.get_by_owner_id.assert_awaited_once_with(owner.id)


@pytest.mark.asyncio
async def test_owner_stats_normalize_missing_statuses_and_map_top_resources():
    service = OwnerService(AsyncMock())
    repository = service.owner_repository
    repository.count_owner_reservations_by_status = AsyncMock(
        return_value={"confirmed": 4, "cancelled": 2, "unexpected": 99}
    )
    repository.get_owner_top_resources = AsyncMock(return_value=[(4, "Court One", 7)])
    repository.count_owner_venues = AsyncMock(return_value=2)
    repository.count_owner_resources = AsyncMock(return_value=5)
    repository.count_owner_reservations = AsyncMock(return_value=12)
    repository.get_owner_total_revenue_cents = AsyncMock(return_value=87500)

    result = await service.get_owner_stats(user())

    assert result.total_venues == 2
    assert result.total_resources == 5
    assert result.total_reservations == 12
    assert result.total_revenue_cents == 87500
    assert set(result.reservations_by_status) == {
        status.value for status in ReservationStatus
    }
    assert result.reservations_by_status["confirmed"] == 4
    assert result.reservations_by_status["pending"] == 0
    assert "unexpected" not in result.reservations_by_status
    assert result.top_resources[0].reservation_count == 7


@pytest.mark.asyncio
async def test_owner_venue_list_is_scoped_to_current_user():
    service = OwnerService(AsyncMock())
    expected = [venue()]
    service.venue_repository.get_by_owner_id = AsyncMock(return_value=expected)

    result = await service.get_my_venues(user(42))

    assert result == expected
    service.venue_repository.get_by_owner_id.assert_awaited_once_with(42)
