import hashlib
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from app.api.routers.calendar_feeds import get_calendar_feed
from app.core.config import settings
from app.schemas.calendar_feed import CalendarFeedCreate
from app.services.calendar_feed_service import CalendarFeedService


def user(user_id=10, role="owner"):
    return MagicMock(id=user_id, role=role)


def venue(owner_id=10, name="Central, Courts", address="1 Main; Street"):
    item = MagicMock(id=7, owner_id=owner_id, address=address)
    item.name = name
    return item


def feed(**changes):
    values = {
        "id": 3,
        "venue_id": 7,
        "resource_id": None,
        "name": "Operations Calendar",
        "token_prefix": "cal_aabbccdd",
        "token_hash": "hash",
        "include_pending": False,
        "created_by_id": 10,
        "created_at": datetime.now(UTC),
        "last_accessed_at": None,
        "revoked_at": None,
    }
    values.update(changes)
    item = MagicMock(**values)
    item.name = values["name"]
    return item


def reservation(**changes):
    values = {
        "id": 42,
        "status": "confirmed",
        "created_at": datetime(2026, 8, 20, 10, tzinfo=UTC),
        "start_time": datetime(2026, 8, 22, 12, tzinfo=UTC),
        "end_time": datetime(2026, 8, 22, 13, tzinfo=UTC),
        "user": MagicMock(email="private@example.com"),
    }
    values.update(changes)
    return MagicMock(**values)


@pytest.mark.asyncio
async def test_owner_creates_feed_and_receives_raw_token_once():
    service = CalendarFeedService(AsyncMock())
    service.venue_repository.get_by_id = AsyncMock(return_value=venue())
    service.repository.count_active = AsyncMock(return_value=0)
    service.repository.create = AsyncMock(side_effect=lambda item: item)

    result = await service.create(
        7, CalendarFeedCreate(name="Operations Calendar"), user()
    )

    assert result["feed_token"].startswith("cal_")
    assert result["feed_path"].endswith(".ics")
    stored = service.repository.create.await_args.args[0]
    assert (
        stored.token_hash == hashlib.sha256(result["feed_token"].encode()).hexdigest()
    )
    assert result["feed_token"] not in stored.token_hash


@pytest.mark.asyncio
async def test_feed_rejects_resource_from_another_venue():
    service = CalendarFeedService(AsyncMock())
    service.venue_repository.get_by_id = AsyncMock(return_value=venue())
    service.resource_repository.get_by_id = AsyncMock(
        return_value=MagicMock(venue_id=99)
    )

    with pytest.raises(HTTPException) as error:
        await service.create(
            7,
            CalendarFeedCreate(name="Court", resource_id=3),
            user(),
        )

    assert error.value.status_code == 400


@pytest.mark.asyncio
async def test_manager_can_manage_calendar_feeds():
    service = CalendarFeedService(AsyncMock())
    service.venue_repository.get_by_id = AsyncMock(return_value=venue())
    service.staff_repository.has_role = AsyncMock(return_value=True)
    service.repository.list_for_venue = AsyncMock(return_value=[])

    result = await service.list(7, user(20, "customer"))

    assert result == []
    service.staff_repository.has_role.assert_awaited_once_with(7, 20, {"manager"})


@pytest.mark.asyncio
async def test_unassigned_user_cannot_manage_calendar_feeds():
    service = CalendarFeedService(AsyncMock())
    service.venue_repository.get_by_id = AsyncMock(return_value=venue())
    service.staff_repository.has_role = AsyncMock(return_value=False)

    with pytest.raises(HTTPException) as error:
        await service.list(7, user(20, "customer"))

    assert error.value.status_code == 403


@pytest.mark.asyncio
async def test_active_feed_limit_is_enforced():
    service = CalendarFeedService(AsyncMock())
    service.venue_repository.get_by_id = AsyncMock(return_value=venue())
    service.repository.count_active = AsyncMock(
        return_value=settings.MAX_ACTIVE_CALENDAR_FEEDS
    )

    with pytest.raises(HTTPException) as error:
        await service.create(7, CalendarFeedCreate(name="Too many"), user())

    assert error.value.status_code == 409


@pytest.mark.asyncio
async def test_revoking_feed_preserves_metadata_and_disables_token():
    service = CalendarFeedService(AsyncMock())
    item = feed()
    service.venue_repository.get_by_id = AsyncMock(return_value=venue())
    service.repository.get_for_venue = AsyncMock(return_value=item)
    service.repository.save = AsyncMock(side_effect=lambda value: value)

    result = await service.revoke(7, 3, user())

    assert result.revoked_at is not None


@pytest.mark.asyncio
async def test_unknown_or_revoked_token_returns_not_found():
    service = CalendarFeedService(AsyncMock())
    service.repository.get_active_by_hash = AsyncMock(return_value=None)

    with pytest.raises(HTTPException) as error:
        await service.render("invalid")

    assert error.value.status_code == 404


@pytest.mark.asyncio
async def test_calendar_contains_stable_utc_event_without_customer_data():
    service = CalendarFeedService(AsyncMock())
    item = feed(name="Bookings, Main")
    booking = reservation()
    resource = MagicMock()
    resource.name = "Court; One"
    place = venue()
    service.repository.get_active_by_hash = AsyncMock(return_value=item)
    service.repository.get_calendar_entries = AsyncMock(
        return_value=[(booking, resource, place)]
    )
    service.repository.save = AsyncMock(side_effect=lambda value: value)
    now = datetime(2026, 8, 21, 12, tzinfo=UTC)

    content, etag = await service.render("secret", now)
    unfolded = content.replace("\r\n ", "")

    assert "BEGIN:VCALENDAR\r\n" in content
    assert "UID:reservation-42@booking-reservation-system" in content
    assert "DTSTART:20260822T120000Z" in content
    assert "Court\\; One - Central\\, Courts" in unfolded
    assert "private@example.com" not in content
    assert etag.startswith('"') and etag.endswith('"')
    assert item.last_accessed_at == now


@pytest.mark.asyncio
async def test_calendar_query_uses_configured_history_and_future_window():
    service = CalendarFeedService(AsyncMock())
    item = feed()
    service.repository.get_active_by_hash = AsyncMock(return_value=item)
    service.repository.get_calendar_entries = AsyncMock(return_value=[])
    service.repository.save = AsyncMock()
    now = datetime(2026, 8, 21, 12, tzinfo=UTC)

    await service.render("secret", now)

    args = service.repository.get_calendar_entries.await_args.args
    assert args[1] == now - timedelta(days=settings.CALENDAR_FEED_PAST_DAYS)
    assert args[2] == now + timedelta(days=settings.CALENDAR_FEED_FUTURE_DAYS)


def test_long_ics_lines_are_folded_to_75_utf8_bytes():
    service = CalendarFeedService(AsyncMock())
    lines = service._fold("SUMMARY:" + "Ž" * 100)

    assert len(lines) > 1
    assert all(len(line.encode("utf-8")) <= 75 for line in lines)
    assert all(line.startswith(" ") for line in lines[1:])


def test_pending_reservation_is_marked_tentative():
    service = CalendarFeedService(AsyncMock())
    content = service._render(
        feed(include_pending=True),
        [(reservation(status="pending"), MagicMock(name="resource"), venue())],
    )

    assert "STATUS:TENTATIVE\r\n" in content


@pytest.mark.asyncio
async def test_matching_etag_returns_not_modified():
    db = AsyncMock()
    with patch.object(
        CalendarFeedService,
        "render",
        new=AsyncMock(return_value=("calendar", '"etag"')),
    ):
        response = await get_calendar_feed("token", '"etag"', db)

    assert response.status_code == 304
    assert response.headers["etag"] == '"etag"'
