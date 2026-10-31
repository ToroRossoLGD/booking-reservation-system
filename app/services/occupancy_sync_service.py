from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4

from cryptography.fernet import Fernet, InvalidToken
from fastapi import HTTPException
from sqlalchemy import delete, or_, select

from app.core.config import settings
from app.models.occupancy_source import OccupancySource
from app.models.occupancy_sync import OccupancySync
from app.models.property_listing import PropertyListing
from app.models.venue import Venue
from app.repositories.stay_repository import StayRepository
from app.services.occupancy_import_service import OccupancyImportService
from app.services.occupancy_source_service import OccupancySourceService
from app.services.occupancy_url_service import fetch_calendar_url, validate_url


def cipher():
    try:
        return Fernet(settings.OCCUPANCY_SYNC_KEY.encode())
    except (ValueError, TypeError):
        raise HTTPException(503, "Calendar encryption key is not configured") from None


def available():
    if not settings.OCCUPANCY_SYNC_ENABLED or settings.DEMO_MODE:
        return False
    try:
        cipher()
        return True
    except HTTPException:
        return False


def utc(value):
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value


class OccupancySyncService(OccupancySourceService):
    async def connection(self, source_id, lock=False):
        query = select(OccupancySync).where(OccupancySync.source_id == source_id)
        if lock:
            query = query.with_for_update()
        return await self.db.scalar(query.execution_options(populate_existing=True))

    async def status(self, property_id, user, source_id):
        listing = await self.authorize(property_id, user)
        await self.get(listing.venue_id, source_id)
        row = await self.connection(source_id)
        return {
            "available": available(),
            "configured": row is not None,
            "enabled": bool(row and row.enabled),
            "allow_empty": bool(row and row.allow_empty),
            "next_run_at": row.next_run_at if row and row.enabled else None,
            "last_attempt_at": row.last_attempt_at if row else None,
            "last_success_at": row.last_success_at if row else None,
            "last_status": row.last_status if row else "unconfigured",
            "running": bool(
                row and row.lease_until and utc(row.lease_until) > datetime.now(UTC)
            ),
            "overdue": bool(
                row
                and row.enabled
                and available()
                and utc(row.next_run_at) + timedelta(minutes=15) < datetime.now(UTC)
                and (not row.lease_until or utc(row.lease_until) <= datetime.now(UTC))
            ),
        }

    async def configure(
        self, property_id, user, source_id, action, url=None, allow_empty=False
    ):
        if settings.DEMO_MODE:
            raise HTTPException(403, "Calendar connections are disabled in demo mode")
        if action in {"connect", "resume", "refresh"} and not available():
            raise HTTPException(503, "Automatic calendar refresh is disabled")
        listing = await self.authorize(property_id, user, lock=True)
        source = await self.get(listing.venue_id, source_id)
        row = await self.connection(source_id, lock=True)
        now = datetime.now(UTC)
        if action == "disconnect":
            if row:
                await self.db.execute(
                    delete(OccupancySync).where(OccupancySync.source_id == source_id)
                )
            source.revision += 1
        elif action == "pause":
            if row:
                row.enabled = False
                row.lease_token = None
                row.lease_until = None
            source.revision += 1
        else:
            if listing.offer_type != "short_stay":
                raise HTTPException(400, "Only short stays support automatic calendars")
            venue = await self.db.get(Venue, listing.venue_id)
            if action == "connect":
                validate_url(url)
                encrypted = cipher().encrypt(url.encode()).decode()
                if row is None:
                    row = OccupancySync(source_id=source_id)
                    self.db.add(row)
                row.property_id = property_id
                row.owner_id = venue.owner_id
                row.encrypted_url = encrypted
                row.allow_empty = allow_empty
                row.enabled = True
                row.last_attempt_at = None
                row.last_success_at = None
                row.last_status = "pending"
            elif row is None:
                raise HTTPException(404, "Calendar connection not found")
            elif row.owner_id != venue.owner_id:
                raise HTTPException(
                    409, "Reconnect the calendar after ownership changes"
                )
            elif action == "refresh" and not row.enabled:
                raise HTTPException(409, "Resume the connection first")
            elif action == "refresh" and row.lease_until and utc(row.lease_until) > now:
                return await self.status(property_id, user, source_id)
            else:
                row.enabled = True
                row.property_id = property_id
            row.next_run_at = now
            row.lease_token = None
            row.lease_until = None
            source.revision += 1
        await self.db.commit()
        return await self.status(property_id, user, source_id)


async def claim(sessions):
    """Claim only the connection row, release transaction before network IO."""
    now = datetime.now(UTC)
    async with sessions() as db:
        row = await db.scalar(
            select(OccupancySync)
            .where(
                OccupancySync.enabled.is_(True),
                OccupancySync.next_run_at <= now,
                or_(
                    OccupancySync.lease_until.is_(None),
                    OccupancySync.lease_until <= now,
                ),
            )
            .order_by(OccupancySync.next_run_at, OccupancySync.source_id)
            .with_for_update(skip_locked=True)
            .limit(1)
        )
        if row is None:
            return None
        source = await db.get(OccupancySource, row.source_id)
        listing = await db.get(PropertyListing, row.property_id)
        venue = await db.get(Venue, source.venue_id) if source else None
        if (
            not source
            or not listing
            or not venue
            or listing.venue_id != source.venue_id
            or listing.offer_type != "short_stay"
            or venue.owner_id != row.owner_id
        ):
            row.enabled = False
            row.last_status = "inactive"
            row.last_attempt_at = now
            row.lease_token = None
            row.lease_until = None
            await db.commit()
            return {"skip": True}
        token = str(uuid4())
        row.lease_token = token
        row.lease_until = now + timedelta(minutes=2)
        job = {
            "source_id": source.id,
            "revision": source.revision,
            "venue_id": source.venue_id,
            "property_id": row.property_id,
            "owner_id": row.owner_id,
            "encrypted_url": row.encrypted_url,
            "token": token,
        }
        await db.commit()
        return job


async def finish(sessions, job, content, failure=None):
    # Match manual booking lock order: listing -> venue -> connection.
    async with sessions() as db:
        stays = StayRepository(db)
        listing = await stays.listing(job["property_id"], lock=True)
        venue = await stays.lock_venue(listing.venue_id) if listing else None
        row = await OccupancySyncService(db).connection(job["source_id"], lock=True)
        if (
            row is None
            or not row.enabled
            or row.lease_token != job["token"]
            or not row.lease_until
            or utc(row.lease_until) <= datetime.now(UTC)
        ):
            return "discarded"
        if not available():
            return "discarded"
        now = datetime.now(UTC)
        source = await db.get(OccupancySource, job["source_id"])
        valid = (
            source
            and listing
            and venue
            and listing.venue_id == job["venue_id"]
            and listing.offer_type == "short_stay"
            and venue.owner_id == job["owner_id"]
        )
        row.lease_token = None
        row.lease_until = None
        row.last_attempt_at = now
        row.next_run_at = now + timedelta(hours=1)
        if not valid:
            row.enabled = False
            row.last_status = "inactive"
        elif source.revision != job["revision"]:
            row.last_status = "superseded"
            row.next_run_at = now + timedelta(minutes=1)
        elif failure:
            row.last_status = failure
            row.next_run_at = now + timedelta(minutes=15)
        else:
            actor = SimpleNamespace(id=job["owner_id"], role="owner")
            importer = OccupancyImportService(db)
            preview = await importer.run(
                job["property_id"], actor, content, source_id=source.id
            )
            if not row.allow_empty and not preview["ranges"] and preview["removed"]:
                row.last_status = "blocked_empty"
            else:
                result = await importer.run(
                    job["property_id"],
                    actor,
                    content,
                    apply=True,
                    source_id=source.id,
                    source_revision=job["revision"],
                    commit=False,
                )
                row.last_status = "applied" if result["applied"] else "conflict"
                if result["applied"]:
                    row.last_success_at = now
        await db.commit()
        return row.last_status


async def run_calendar_syncs(sessions, limit=10):
    counts = {}
    if not available():
        return counts
    for _ in range(limit):
        if not available():
            break
        job = await claim(sessions)
        if job is None:
            break
        if job.get("skip"):
            counts["inactive"] = counts.get("inactive", 0) + 1
            continue
        content, failure = None, None
        try:
            url = cipher().decrypt(job["encrypted_url"].encode()).decode()
        except (InvalidToken, HTTPException, UnicodeError):
            failure = "key_error"
        if failure is None:
            try:
                content = await fetch_calendar_url(url)
            except HTTPException:
                failure = "fetch_error"
        result = await finish(sessions, job, content, failure)
        counts[result] = counts.get(result, 0) + 1
    return counts
