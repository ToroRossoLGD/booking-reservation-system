from datetime import UTC, datetime

from fastapi import HTTPException
from sqlalchemy import func, select

from app.models.notification import Notification
from app.models.property_listing import PropertyListing
from app.models.property_report import PropertyModerationEvent, PropertyReport
from app.models.user import User
from app.models.venue import Venue
from app.schemas.property_moderation import (
    ModerationCase,
    ModerationHistory,
    ModerationPage,
    PropertyReportRead,
    ReportItem,
    ReportPage,
)


class PropertyModerationService:
    def __init__(self, db):
        self.db = db

    @staticmethod
    def admin(user):
        if user.role != "admin":
            raise HTTPException(403, "Administrator access required")

    @staticmethod
    def case(listing):
        return ModerationCase(
            id=listing.id,
            title=listing.title,
            state=listing.moderation_state,
            version=listing.moderation_version,
            note=listing.moderation_note,
            appeal=listing.moderation_appeal,
            is_published=listing.is_published,
        )

    async def listing(self, property_id, lock=False):
        query = select(PropertyListing).where(PropertyListing.id == property_id)
        if lock:
            query = query.with_for_update().execution_options(populate_existing=True)
        listing = await self.db.scalar(query)
        if listing is None:
            raise HTTPException(404, "Listing not found")
        return listing

    async def owner_id(self, listing):
        return await self.db.scalar(
            select(Venue.owner_id).where(Venue.id == listing.venue_id)
        )

    async def report(self, property_id, data, user):
        await self.db.scalar(
            select(User.id).where(User.id == user.id).with_for_update()
        )
        previous = await self.db.scalar(
            select(PropertyReport).where(
                PropertyReport.user_id == user.id,
                PropertyReport.request_id == str(data.request_id),
            )
        )
        if previous:
            if (previous.property_id, previous.category, previous.details) != (
                property_id,
                data.category,
                data.details,
            ):
                raise HTTPException(409, "Request identifier already used")
            return previous
        listing = await self.listing(property_id, lock=True)
        if not listing.is_published:
            raise HTTPException(404, "Listing not found")
        if await self.owner_id(listing) == user.id:
            raise HTTPException(400, "You cannot report your own listing")
        pending = select(PropertyReport).where(
            PropertyReport.user_id == user.id, PropertyReport.status == "pending"
        )
        if await self.db.scalar(
            pending.where(PropertyReport.property_id == property_id)
        ):
            raise HTTPException(409, "You already have an open report for this listing")
        if (
            await self.db.scalar(select(func.count()).select_from(pending.subquery()))
            >= 20
        ):
            raise HTTPException(429, "Open report limit reached")
        report = PropertyReport(
            property_id=property_id,
            user_id=user.id,
            request_id=str(data.request_id),
            category=data.category,
            details=data.details,
            snapshot={
                key: getattr(listing, key)
                for key in (
                    "title",
                    "description",
                    "city",
                    "offer_type",
                    "price_cents",
                    "currency",
                )
            },
        )
        self.db.add(report)
        await self.db.commit()
        await self.db.refresh(report)
        return report

    async def reports(self, user, admin=False, status=None, offset=0, limit=20):
        if admin:
            self.admin(user)
        query = select(PropertyReport).where(
            True if admin else PropertyReport.user_id == user.id
        )
        if status:
            query = query.where(PropertyReport.status == status)
        total = await self.db.scalar(select(func.count()).select_from(query.subquery()))
        rows = await self.db.scalars(
            query.order_by(PropertyReport.id.desc()).offset(offset).limit(limit)
        )
        items = []
        for report in rows.all():
            listing = await self.listing(report.property_id)
            case = self.case(listing)
            if not admin:
                # Never expose owner appeals or moderator notes to reporters.
                case = case.model_copy(update={"note": "", "appeal": ""})
            items.append(
                ReportItem(
                    **PropertyReportRead.model_validate(report).model_dump(),
                    listing=case,
                )
            )
        return ReportPage(items=items, total=total, has_next=offset + limit < total)

    async def cases(self, user, admin=False, offset=0, limit=20, state=None):
        if admin:
            self.admin(user)
        query = (
            select(PropertyListing)
            .join(Venue)
            .where(PropertyListing.moderation_version > 0)
        )
        if not admin:
            query = query.where(Venue.owner_id == user.id)
        if state:
            query = query.where(PropertyListing.moderation_state == state)
        total = await self.db.scalar(select(func.count()).select_from(query.subquery()))
        result = await self.db.scalars(
            query.order_by(PropertyListing.id.desc()).offset(offset).limit(limit)
        )
        return ModerationPage(
            items=[self.case(item) for item in result.all()],
            total=total,
            has_next=offset + limit < total,
        )

    async def history(self, property_id, user, offset=0, limit=20):
        listing = await self.listing(property_id)
        if user.role != "admin" and await self.owner_id(listing) != user.id:
            raise HTTPException(404, "Listing not found")
        query = select(PropertyModerationEvent).where(
            PropertyModerationEvent.property_id == property_id
        )
        total = await self.db.scalar(select(func.count()).select_from(query.subquery()))
        result = await self.db.scalars(
            query.order_by(PropertyModerationEvent.id.desc())
            .offset(offset)
            .limit(limit)
        )
        return ModerationHistory(
            items=list(result.all()), total=total, has_next=offset + limit < total
        )

    async def act(self, property_id, data, user, report_id=None):
        listing = await self.listing(property_id)
        owner_id = await self.owner_id(listing)
        if data.action == "appeal":
            if user.id != owner_id:
                raise HTTPException(404, "Listing not found")
        else:
            self.admin(user)
        report = None
        if report_id is not None:
            report = await self.db.scalar(
                select(PropertyReport).where(
                    PropertyReport.id == report_id,
                    PropertyReport.property_id == property_id,
                )
            )
            if report is None:
                raise HTTPException(404, "Report not found")
        if (data.action in ("hide", "dismiss")) != (report is not None):
            raise HTTPException(
                400, "This action requires the matching report workflow"
            )
        # Notifications reference user rows: lock keys before the listing to avoid
        # inversion with bookings/report submissions that lock a user first.
        ids = {user.id, owner_id} | ({report.user_id} if report else set())
        await self.db.scalars(
            select(User.id)
            .where(User.id.in_(ids))
            .order_by(User.id)
            .with_for_update(read=True, key_share=True)
        )
        listing = await self.listing(property_id, lock=True)
        if await self.owner_id(listing) != owner_id:
            raise HTTPException(409, "Ownership changed. Refresh the moderation queue")
        previous = await self.db.scalar(
            select(PropertyModerationEvent).where(
                PropertyModerationEvent.actor_id == user.id,
                PropertyModerationEvent.request_id == str(data.request_id),
            )
        )
        if previous:
            if (
                previous.property_id,
                previous.action,
                previous.note,
                previous.version,
                previous.report_id,
            ) != (property_id, data.action, data.note, data.version + 1, report_id):
                raise HTTPException(409, "Request identifier already used")
            return self.case(listing)
        if listing.moderation_version != data.version:
            raise HTTPException(409, "Moderation changed. Refresh before deciding")
        if report:
            report = await self.db.scalar(
                select(PropertyReport)
                .where(PropertyReport.id == report_id)
                .with_for_update()
                .execution_options(populate_existing=True)
            )
            if report.status != "pending":
                raise HTTPException(409, "Report already reviewed")
        state = listing.moderation_state
        allowed = {
            "hide": ("clear",),
            "dismiss": ("clear", "suspended", "appealed"),
            "appeal": ("suspended",),
            "restore": ("suspended", "appealed"),
            "uphold": ("appealed",),
        }
        if state not in allowed[data.action]:
            raise HTTPException(409, "Action is not available in the current state")
        if data.action == "hide":
            listing.is_published = False
            listing.moderation_state = "suspended"
            listing.moderation_note = data.note
            listing.moderation_appeal = ""
        elif data.action == "appeal":
            listing.moderation_state = "appealed"
            listing.moderation_appeal = data.note
        elif data.action in ("restore", "uphold"):
            listing.moderation_state = (
                "clear" if data.action == "restore" else "suspended"
            )
            listing.moderation_note = data.note
            # Restoring permission does not automatically republish the draft.
            listing.is_published = False
        listing.moderation_version += 1
        if report:
            report.status = "action_taken" if data.action == "hide" else "dismissed"
            report.resolved_at = datetime.now(UTC)
        event = PropertyModerationEvent(
            property_id=property_id,
            actor_id=user.id,
            request_id=str(data.request_id),
            report_id=report_id,
            action=data.action,
            note=data.note,
            version=listing.moderation_version,
        )
        self.db.add(event)
        await self.db.flush()
        recipients = ({owner_id} if data.action != "dismiss" else set()) | (
            {report.user_id} if report else set()
        )
        for recipient in recipients:
            self.db.add(
                Notification(
                    user_id=recipient,
                    title="Ažuriranje moderacije oglasa",
                    message=(
                        f"Oglas #{listing.id}: {listing.title}. "
                        "Otvori moderaciju za status prijave ili pregled odluke."
                    ),
                    action_path="/moderation",
                    deduplication_key=f"moderation:{event.id}:user:{recipient}",
                )
            )
        await self.db.commit()
        await self.db.refresh(listing)
        return self.case(listing)
