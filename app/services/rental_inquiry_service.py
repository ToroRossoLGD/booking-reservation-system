from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from fastapi import HTTPException
from sqlalchemy import func, select

from app.models.property_listing import PropertyListing
from app.models.rental_inquiry import RentalInquiry
from app.models.user import User
from app.models.venue import Venue


class RentalInquiryService:
    def __init__(self, db):
        self.db = db

    async def create(self, property_id, data, user):
        # Serialize retries and duplicate submissions from the same account.
        await self.db.scalar(
            select(User.id).where(User.id == user.id).with_for_update()
        )
        previous = await self.db.scalar(
            select(RentalInquiry).where(
                RentalInquiry.user_id == user.id,
                RentalInquiry.request_id == str(data.request_id),
            )
        )
        if previous:
            if (
                previous.property_id,
                previous.move_in,
                previous.duration_months,
                previous.message,
            ) != (property_id, data.move_in, data.duration_months, data.message):
                raise HTTPException(409, "This request identifier was already used")
            return previous
        listing = await self.db.scalar(
            select(PropertyListing)
            .where(PropertyListing.id == property_id)
            .with_for_update()
        )
        if listing is None or not listing.is_published:
            raise HTTPException(404, "Property not found")
        if listing.offer_type != "long_term":
            raise HTTPException(
                400, "Inquiries are available for long-term rentals only"
            )
        owner_id = await self.db.scalar(
            select(Venue.owner_id).where(Venue.id == listing.venue_id)
        )
        if owner_id == user.id:
            raise HTTPException(400, "You cannot inquire about your own property")
        if data.move_in < datetime.now(ZoneInfo(listing.timezone)).date():
            raise HTTPException(400, "Move-in date cannot be in the past")
        active = await self.db.scalar(
            select(RentalInquiry.id).where(
                RentalInquiry.user_id == user.id,
                RentalInquiry.property_id == property_id,
                RentalInquiry.status.notin_(["closed", "withdrawn"]),
            )
        )
        if active:
            raise HTTPException(
                409, "You already have an active inquiry for this property"
            )
        inquiry = RentalInquiry(
            property_id=property_id,
            owner_id=owner_id,
            user_id=user.id,
            request_id=str(data.request_id),
            title=listing.title,
            monthly_price_cents=listing.price_cents,
            currency=listing.currency,
            move_in=data.move_in,
            duration_months=data.duration_months,
            message=data.message,
        )
        self.db.add(inquiry)
        await self.db.commit()
        await self.db.refresh(inquiry)
        return inquiry

    async def list(self, user, owner=False, offset=0, limit=20):
        query = select(RentalInquiry).where(
            (RentalInquiry.owner_id if owner else RentalInquiry.user_id) == user.id
        )
        total = await self.db.scalar(select(func.count()).select_from(query.subquery()))
        items = list(
            await self.db.scalars(
                query.order_by(RentalInquiry.id.desc()).offset(offset).limit(limit)
            )
        )
        return {"items": items, "total": total, "has_next": offset + limit < total}

    async def update(self, inquiry_id, data, user):
        inquiry = await self.db.scalar(
            select(RentalInquiry)
            .where(RentalInquiry.id == inquiry_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if inquiry is None or user.id not in {inquiry.user_id, inquiry.owner_id}:
            raise HTTPException(404, "Inquiry not found")
        owner_action = data.action in {"reply", "propose", "close"}
        if user.id != (inquiry.owner_id if owner_action else inquiry.user_id):
            raise HTTPException(403, "You cannot perform this action")
        if inquiry.version != data.version:
            raise HTTPException(409, "Inquiry changed. Refresh before continuing")
        if inquiry.status in {"closed", "withdrawn"}:
            raise HTTPException(409, "This inquiry is no longer active")
        now = datetime.now(timezone.utc)
        if data.action == "propose":
            if data.viewing_at <= now:
                raise HTTPException(400, "Viewing must be in the future")
            inquiry.viewing_at = data.viewing_at
            inquiry.status = "viewing_proposed"
        elif data.action in {"confirm", "decline"}:
            if inquiry.status != "viewing_proposed":
                raise HTTPException(409, "There is no pending viewing proposal")
            if data.action == "confirm":
                viewing = inquiry.viewing_at
                # SQLite strips offsets; PostgreSQL preserves them.
                if viewing.tzinfo is None:
                    viewing = viewing.replace(tzinfo=timezone.utc)
                if viewing <= now:
                    raise HTTPException(400, "This viewing time has passed")
                inquiry.status = "viewing_confirmed"
            else:
                inquiry.status = "open"
                inquiry.viewing_at = None
        elif data.action in {"close", "withdraw"}:
            inquiry.status = "closed" if data.action == "close" else "withdrawn"
        if owner_action and data.action != "close":
            inquiry.owner_reply = data.owner_reply
        inquiry.version += 1
        await self.db.commit()
        await self.db.refresh(inquiry)
        return inquiry
