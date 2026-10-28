"""Bounded, date-only ICS snapshot import; never fetches external URLs."""

import re
from datetime import date, timedelta
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import select

from app.core.config import settings
from app.models.occupancy_import_run import OccupancyImportRun
from app.models.stay_block import StayBlock
from app.services.stay_block_service import StayBlockService
from app.services.stay_service import StayService

MAX_BYTES = 100_000
MAX_EVENTS = 100


def invalid(message="Invalid or unsupported calendar"):
    return HTTPException(400, message)


def parse_calendar(content: str):
    # Deliberately support a strict subset instead of guessing recurrence/time zones.
    try:
        size = len(content.encode("utf-8"))
    except UnicodeEncodeError:
        raise invalid("Calendar must be valid UTF-8 text") from None
    if size > MAX_BYTES or "\x00" in content:
        raise invalid("Calendar must be UTF-8 text up to 100 KB")
    content = content.removeprefix("\ufeff")
    lines = []
    for line in content.splitlines():
        if line.startswith((" ", "\t")):
            if not lines:
                raise invalid()
            lines[-1] += line[1:]
        elif line:
            lines.append(line)
    if not lines or lines[0].upper() != "BEGIN:VCALENDAR":
        raise invalid()
    stack, events, event, calendar = [], [], None, {}
    for index, line in enumerate(lines):
        if ":" not in line:
            raise invalid()
        key, value = line.split(":", 1)
        name = key.split(";", 1)[0].upper()
        if name == "BEGIN":
            component = value.upper()
            if (not stack and index == 0 and component == "VCALENDAR") or (
                stack == ["VCALENDAR"] and component == "VEVENT"
            ):
                stack.append(component)
                if component == "VEVENT":
                    event = {}
            else:
                raise invalid("Only VCALENDAR with date-only VEVENTs is supported")
        elif name == "END":
            if not stack or stack.pop() != value.upper():
                raise invalid()
            if value.upper() == "VEVENT":
                events.append(event)
                event = None
                if len(events) > MAX_EVENTS:
                    raise invalid("A calendar can contain at most 100 events")
            elif index != len(lines) - 1:
                raise invalid()
        else:
            target = event if event is not None else calendar
            if not stack:
                raise invalid()
            # Reject duplicate semantic fields, while ignoring descriptive metadata.
            if name in {
                "DTSTART",
                "DTEND",
                "DURATION",
                "STATUS",
                "TRANSP",
                "VERSION",
                "METHOD",
            }:
                if name in target:
                    raise invalid("Duplicate calendar fields")
                target[name] = (key.upper(), value)
            if name in {"RRULE", "RDATE", "EXDATE", "EXRULE", "RECURRENCE-ID"}:
                raise invalid("Recurring events are not supported")
    if stack or calendar.get("VERSION") != ("VERSION", "2.0"):
        raise invalid()
    if "METHOD" in calendar and calendar["METHOD"][1].upper() != "PUBLISH":
        raise invalid("Scheduling messages are not supported")
    ranges, ignored = [], 0

    def day(field):
        key, value = field
        if key not in {"DTSTART;VALUE=DATE", "DTEND;VALUE=DATE"} or not re.fullmatch(
            r"\d{8}", value
        ):
            raise invalid("Only DTSTART/DTEND with VALUE=DATE are supported")
        try:
            return date(int(value[:4]), int(value[4:6]), int(value[6:]))
        except ValueError:
            raise invalid("Invalid calendar date") from None

    for item in events:
        if "DTSTART" not in item or "DURATION" in item:
            raise invalid("Events require DTSTART; DURATION is not supported")
        start = day(item["DTSTART"])
        try:
            end = day(item["DTEND"]) if "DTEND" in item else start + timedelta(days=1)
        except OverflowError:
            raise invalid("Invalid calendar date") from None
        if end <= start:
            raise invalid("Event end must follow its start")
        status = item.get("STATUS", ("", "CONFIRMED"))[1].upper()
        transparency = item.get("TRANSP", ("", "OPAQUE"))[1].upper()
        if status not in {
            "CONFIRMED",
            "TENTATIVE",
            "CANCELLED",
        } or transparency not in {"OPAQUE", "TRANSPARENT"}:
            raise invalid("Unsupported event status")
        if status == "CANCELLED" or transparency == "TRANSPARENT":
            ignored += 1
        else:
            ranges.append((start, end))
    return ranges, ignored


class OccupancyImportService(StayBlockService):
    async def history(self, property_id, user):
        listing = await self.authorize(property_id, user)
        rows = await self.db.scalars(
            select(OccupancyImportRun)
            .where(OccupancyImportRun.venue_id == listing.venue_id)
            .order_by(OccupancyImportRun.id.desc())
            .limit(10)
        )
        return list(rows.all())

    async def run(self, property_id, user, content, apply=False):
        if apply and settings.DEMO_MODE:
            raise HTTPException(403, "Calendar import is disabled in demo mode")
        listing = await self.authorize(property_id, user, lock=apply)
        if listing.offer_type != "short_stay":
            raise invalid("Only short stays support calendar import")
        ranges, ignored = parse_calendar(content)
        today = StayService.today(listing.timezone)
        horizon = today + timedelta(days=365)
        merged = []
        clipped = 0
        for start, end in sorted(ranges):
            if end <= today or start >= horizon:
                ignored += 1
                continue
            if start < today or end > horizon:
                clipped += 1
            start, end = max(start, today), min(end, horizon)
            if merged and start <= merged[-1][1]:
                merged[-1] = (merged[-1][0], max(end, merged[-1][1]))
            else:
                merged.append((start, end))
        occupied = await self.stays.occupied(
            listing.venue_id,
            today,
            horizon,
            preparation_days=await self.stays.preparation_days(listing.venue_id),
        )
        result = []
        for start, end in merged:
            overlaps = [
                item
                for item in occupied
                if item.check_in < end and item.check_out > start
            ]
            status = "ready"
            if overlaps:
                status = (
                    "existing"
                    if all(
                        isinstance(item, StayBlock)
                        and item.check_in == start
                        and item.check_out == end
                        for item in overlaps
                    )
                    else "conflict"
                )
            result.append({"check_in": start, "check_out": end, "status": status})
        conflicts = any(item["status"] == "conflict" for item in result)
        created = 0
        if apply and not conflicts:
            for item in result:
                if item["status"] == "ready":
                    self.db.add(
                        StayBlock(
                            venue_id=listing.venue_id,
                            created_by_id=user.id,
                            request_id=str(uuid4()),
                            check_in=item["check_in"],
                            check_out=item["check_out"],
                            reason="iCal import",
                            active=True,
                        )
                    )
                    created += 1
        if apply:
            # Outcome and new blocks commit together; a conflict records no blocks.
            self.db.add(
                OccupancyImportRun(
                    venue_id=listing.venue_id,
                    status="conflict" if conflicts else "applied",
                    created=created,
                    existing=sum(item["status"] == "existing" for item in result),
                    conflicts=sum(item["status"] == "conflict" for item in result),
                    ignored=ignored,
                    clipped=clipped,
                )
            )
            await self.db.commit()
        return {
            "ranges": result,
            "ignored": ignored,
            "clipped": clipped,
            "applied": apply and not conflicts,
            "created": created,
        }
