from __future__ import annotations

import hashlib
import secrets
from datetime import UTC, datetime, timedelta

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.calendar_feed import CalendarFeed
from app.models.user import User
from app.repositories.calendar_feed_repository import CalendarFeedRepository
from app.repositories.resource_repository import ResourceRepository
from app.repositories.venue_repository import VenueRepository
from app.repositories.venue_staff_repository import VenueStaffRepository
from app.schemas.calendar_feed import CalendarFeedCreate


class CalendarFeedService:
    def __init__(self, db: AsyncSession):
        self.repository = CalendarFeedRepository(db)
        self.venue_repository = VenueRepository(db)
        self.resource_repository = ResourceRepository(db)
        self.staff_repository = VenueStaffRepository(db)

    @staticmethod
    def _hash_token(token: str) -> str:
        return hashlib.sha256(token.encode()).hexdigest()

    async def _authorize(self, venue_id: int, user: User):
        venue = await self.venue_repository.get_by_id(venue_id)
        if venue is None:
            raise HTTPException(status_code=404, detail="Venue not found")
        if user.role == "admin" or venue.owner_id == user.id:
            return venue
        if await self.staff_repository.has_role(venue_id, user.id, {"manager"}):
            return venue
        raise HTTPException(
            status_code=403, detail="You cannot manage calendar feeds for this venue"
        )

    async def create(self, venue_id: int, data: CalendarFeedCreate, user: User) -> dict:
        await self._authorize(venue_id, user)
        if data.resource_id is not None:
            resource = await self.resource_repository.get_by_id(data.resource_id)
            if resource is None or resource.venue_id != venue_id:
                raise HTTPException(
                    status_code=400, detail="Resource does not belong to this venue"
                )
        if (
            await self.repository.count_active(venue_id)
            >= settings.MAX_ACTIVE_CALENDAR_FEEDS
        ):
            raise HTTPException(
                status_code=409,
                detail=(
                    "A venue can have at most "
                    f"{settings.MAX_ACTIVE_CALENDAR_FEEDS} active calendar feeds"
                ),
            )
        prefix = secrets.token_hex(4)
        token = f"cal_{prefix}_{secrets.token_urlsafe(32)}"
        feed = await self.repository.create(
            CalendarFeed(
                venue_id=venue_id,
                resource_id=data.resource_id,
                name=data.name,
                token_prefix=f"cal_{prefix}",
                token_hash=self._hash_token(token),
                include_pending=data.include_pending,
                created_by_id=user.id,
            )
        )
        return {
            **feed.__dict__,
            "feed_token": token,
            "feed_path": f"/calendar-feeds/{token}.ics",
        }

    async def list(self, venue_id: int, user: User):
        await self._authorize(venue_id, user)
        return await self.repository.list_for_venue(venue_id)

    async def revoke(self, venue_id: int, feed_id: int, user: User):
        await self._authorize(venue_id, user)
        feed = await self.repository.get_for_venue(feed_id, venue_id)
        if feed is None:
            raise HTTPException(status_code=404, detail="Calendar feed not found")
        if feed.revoked_at is None:
            feed.revoked_at = datetime.now(UTC)
            feed = await self.repository.save(feed)
        return feed

    @staticmethod
    def _escape(value: str) -> str:
        return (
            value.replace("\\", "\\\\")
            .replace(";", "\\;")
            .replace(",", "\\,")
            .replace("\r\n", "\\n")
            .replace("\n", "\\n")
        )

    @staticmethod
    def _utc(value: datetime) -> str:
        if value.tzinfo is None:
            value = value.replace(tzinfo=UTC)
        return value.astimezone(UTC).strftime("%Y%m%dT%H%M%SZ")

    @staticmethod
    def _fold(line: str) -> list[str]:
        lines = []
        current = ""
        for char in line:
            candidate = current + char
            if len(candidate.encode("utf-8")) > 75:
                lines.append(current)
                current = " " + char
            else:
                current = candidate
        lines.append(current)
        return lines

    def _render(self, feed: CalendarFeed, entries: list[tuple]) -> str:
        lines = [
            "BEGIN:VCALENDAR",
            "VERSION:2.0",
            "PRODID:-//Booking Reservation System//Calendar Feed//EN",
            "CALSCALE:GREGORIAN",
            "METHOD:PUBLISH",
            f"X-WR-CALNAME:{self._escape(feed.name)}",
        ]
        for reservation, resource, venue in entries:
            calendar_status = (
                "TENTATIVE" if reservation.status == "pending" else "CONFIRMED"
            )
            lines.extend(
                [
                    "BEGIN:VEVENT",
                    f"UID:reservation-{reservation.id}@booking-reservation-system",
                    f"DTSTAMP:{self._utc(reservation.created_at)}",
                    f"DTSTART:{self._utc(reservation.start_time)}",
                    f"DTEND:{self._utc(reservation.end_time)}",
                    "SUMMARY:"
                    f"{self._escape(resource.name)} - {self._escape(venue.name)}",
                    f"LOCATION:{self._escape(venue.address)}",
                    f"DESCRIPTION:Reservation #{reservation.id} ({reservation.status})",
                    f"STATUS:{calendar_status}",
                    "END:VEVENT",
                ]
            )
        lines.append("END:VCALENDAR")
        folded = [physical for logical in lines for physical in self._fold(logical)]
        return "\r\n".join(folded) + "\r\n"

    async def render(
        self, token: str, current_time: datetime | None = None
    ) -> tuple[str, str]:
        feed = await self.repository.get_active_by_hash(self._hash_token(token))
        if feed is None:
            raise HTTPException(status_code=404, detail="Calendar feed not found")
        now = current_time or datetime.now(UTC)
        entries = await self.repository.get_calendar_entries(
            feed,
            now - timedelta(days=settings.CALENDAR_FEED_PAST_DAYS),
            now + timedelta(days=settings.CALENDAR_FEED_FUTURE_DAYS),
        )
        content = self._render(feed, entries)
        feed.last_accessed_at = now
        await self.repository.save(feed)
        etag = f'"{hashlib.sha256(content.encode()).hexdigest()}"'
        return content, etag
