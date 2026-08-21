from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.calendar_feed import CalendarFeed
from app.models.reservation import Reservation
from app.models.resource import Resource
from app.models.venue import Venue


class CalendarFeedRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, feed: CalendarFeed) -> CalendarFeed:
        self.db.add(feed)
        await self.db.commit()
        await self.db.refresh(feed)
        return feed

    async def count_active(self, venue_id: int) -> int:
        result = await self.db.execute(
            select(CalendarFeed.id).where(
                CalendarFeed.venue_id == venue_id, CalendarFeed.revoked_at.is_(None)
            )
        )
        return len(result.scalars().all())

    async def list_for_venue(self, venue_id: int) -> list[CalendarFeed]:
        result = await self.db.execute(
            select(CalendarFeed)
            .where(CalendarFeed.venue_id == venue_id)
            .order_by(CalendarFeed.created_at.desc(), CalendarFeed.id.desc())
        )
        return list(result.scalars().all())

    async def get_for_venue(self, feed_id: int, venue_id: int) -> CalendarFeed | None:
        result = await self.db.execute(
            select(CalendarFeed).where(
                CalendarFeed.id == feed_id, CalendarFeed.venue_id == venue_id
            )
        )
        return result.scalar_one_or_none()

    async def get_active_by_hash(self, token_hash: str) -> CalendarFeed | None:
        result = await self.db.execute(
            select(CalendarFeed).where(
                CalendarFeed.token_hash == token_hash, CalendarFeed.revoked_at.is_(None)
            )
        )
        return result.scalar_one_or_none()

    async def save(self, feed: CalendarFeed) -> CalendarFeed:
        await self.db.commit()
        await self.db.refresh(feed)
        return feed

    async def get_calendar_entries(
        self, feed: CalendarFeed, starts_after: datetime, starts_before: datetime
    ):
        statuses = ["confirmed", "completed"]
        if feed.include_pending:
            statuses.append("pending")
        statement = (
            select(Reservation, Resource, Venue)
            .join(Resource, Resource.id == Reservation.resource_id)
            .join(Venue, Venue.id == Resource.venue_id)
            .where(
                Venue.id == feed.venue_id,
                Reservation.status.in_(statuses),
                Reservation.end_time >= starts_after,
                Reservation.start_time <= starts_before,
            )
        )
        if feed.resource_id is not None:
            statement = statement.where(Resource.id == feed.resource_id)
        result = await self.db.execute(
            statement.order_by(Reservation.start_time, Reservation.id)
        )
        return list(result.all())
