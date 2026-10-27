from datetime import UTC, datetime, timedelta
from uuid import NAMESPACE_URL, uuid5

from fastapi import HTTPException

from app.core.config import settings
from app.services.stay_block_service import StayBlockService
from app.services.stay_service import StayService


class OccupancyCalendarService(StayBlockService):
    async def export(self, property_id, user):
        listing = await self.authorize(property_id, user)
        if listing.offer_type != "short_stay":
            raise HTTPException(400, "Only short-stay occupancy can be exported")
        start = StayService.today(listing.timezone)
        end = start + timedelta(days=365)
        gap = await self.stays.preparation_days(listing.venue_id)
        occupied = await self.stays.occupied(listing.venue_id, start, end, gap)
        # Merge shared inventory and preparation overlaps without exposing sources.
        intervals = []
        for entry in occupied:
            left, right = max(start, entry.check_in), min(end, entry.check_out)
            if left >= right:
                continue
            if intervals and left <= intervals[-1][1]:
                intervals[-1] = (intervals[-1][0], max(right, intervals[-1][1]))
            else:
                intervals.append((left, right))
        stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
        lines = [
            "BEGIN:VCALENDAR",
            "VERSION:2.0",
            "PRODID:-//Bookica//Occupancy Snapshot//EN",
            "CALSCALE:GREGORIAN",
        ]
        for left, right in intervals:
            identity = (
                f"{settings.FRONTEND_URL}/occupancy/{listing.venue_id}/{left}/{right}"
            )
            lines.extend(
                [
                    "BEGIN:VEVENT",
                    f"UID:{uuid5(NAMESPACE_URL, identity)}@bookica",
                    f"DTSTAMP:{stamp}",
                    f"DTSTART;VALUE=DATE:{left:%Y%m%d}",
                    f"DTEND;VALUE=DATE:{right:%Y%m%d}",
                    "SUMMARY:Unavailable",
                    "CLASS:PRIVATE",
                    "STATUS:CONFIRMED",
                    "TRANSP:OPAQUE",
                    "END:VEVENT",
                ]
            )
        lines.append("END:VCALENDAR")
        return "\r\n".join(lines) + "\r\n"
