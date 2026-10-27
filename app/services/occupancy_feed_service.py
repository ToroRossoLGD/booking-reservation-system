import hashlib
import re
import secrets
from datetime import UTC, datetime
from types import SimpleNamespace

from fastapi import HTTPException
from sqlalchemy import select

from app.core.config import settings
from app.models.occupancy_feed import OccupancyFeed
from app.models.venue import Venue
from app.services.occupancy_calendar_service import OccupancyCalendarService


class OccupancyFeedService(OccupancyCalendarService):
    async def manage(self, property_id, user, action="read"):
        if action != "read" and settings.DEMO_MODE:
            raise HTTPException(403, "Calendar subscriptions are disabled in demo mode")
        # Venue lock serializes creation/rotation/revocation across listing aliases.
        listing = await self.authorize(property_id, user, lock=action != "read")
        if listing.offer_type != "short_stay" and action == "rotate":
            raise HTTPException(400, "Only short stays support occupancy feeds")
        venue = await self.db.scalar(select(Venue).where(Venue.id == listing.venue_id))
        feed = await self.db.scalar(
            select(OccupancyFeed)
            .where(OccupancyFeed.venue_id == listing.venue_id)
            .execution_options(populate_existing=True)
        )
        if action == "read":
            source = await self.stays.listing(feed.property_id) if feed else None
            return {
                "active": bool(
                    feed
                    and feed.token_hash
                    and feed.owner_id == venue.owner_id
                    and source
                    and source.venue_id == feed.venue_id
                    and source.offer_type == "short_stay"
                )
            }
        token = None
        if action == "rotate":
            token = secrets.token_urlsafe(32)
            if feed is None:
                feed = OccupancyFeed(venue_id=listing.venue_id)
                self.db.add(feed)
            feed.property_id = property_id
            feed.owner_id = venue.owner_id
            feed.token_hash = hashlib.sha256(token.encode()).hexdigest()
        elif feed:
            feed.token_hash = None
        if feed:
            feed.updated_at = datetime.now(UTC)
        await self.db.commit()
        return {
            "active": action == "rotate",
            "path": f"/occupancy-feeds/{token}.ics" if token else None,
        }

    async def render(self, token):
        if not re.fullmatch(r"[A-Za-z0-9_-]{43}", token):
            raise HTTPException(404, "Calendar not found")
        feed = await self.db.scalar(
            select(OccupancyFeed).where(
                OccupancyFeed.token_hash == hashlib.sha256(token.encode()).hexdigest()
            )
        )
        if feed is None:
            raise HTTPException(404, "Calendar not found")
        venue = await self.db.scalar(select(Venue).where(Venue.id == feed.venue_id))
        if venue is None or venue.owner_id != feed.owner_id:
            raise HTTPException(404, "Calendar not found")
        listing = await self.stays.listing(feed.property_id)
        if listing is None or listing.venue_id != feed.venue_id:
            raise HTTPException(404, "Calendar not found")
        try:
            return await self.export(
                feed.property_id, SimpleNamespace(id=feed.owner_id, role="owner")
            )
        except HTTPException:
            raise HTTPException(404, "Calendar not found") from None
