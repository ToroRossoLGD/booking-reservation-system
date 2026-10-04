from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from fastapi import HTTPException
from sqlalchemy import func, select

from app.models.property_listing import PropertyListing
from app.models.rental_inquiry import RentalInquiry
from app.models.rental_message import RentalMessage
from app.models.sale_inquiry import SaleInquiry, SaleMessage
from app.models.user import User
from app.models.venue import Venue
from app.schemas.rental_inquiry import RentalInquiryRead
from app.schemas.rental_terms import RentalTerms
from app.schemas.sale_inquiry import SaleInquiryRead
from app.services.rental_message_service import append_rental_message
from app.services.rental_notification_service import add_rental_notification


class RentalInquiryService:
    def __init__(self, db, *, sale=False):
        self.db = db
        self.sale = sale
        self.inquiry_model = SaleInquiry if sale else RentalInquiry
        self.message_model = SaleMessage if sale else RentalMessage
        self.read_schema = SaleInquiryRead if sale else RentalInquiryRead

    async def create(self, property_id, data, user):
        # Serialize retries and duplicate submissions from the same account.
        await self.db.scalar(
            select(User.id).where(User.id == user.id).with_for_update(key_share=True)
        )
        previous = await self.db.scalar(
            select(self.inquiry_model).where(
                self.inquiry_model.user_id == user.id,
                self.inquiry_model.request_id == str(data.request_id),
            )
        )
        if previous:
            fields = (
                ("property_id", "message")
                if self.sale
                else ("property_id", "move_in", "duration_months", "message")
            )
            expected = {"property_id": property_id, **data.model_dump()}
            if any(getattr(previous, field) != expected[field] for field in fields):
                raise HTTPException(409, "This request identifier was already used")
            return previous
        # Lock the recipient key before inventory, so notification FK checks do
        # not invert the user-first order of simultaneous bookings.
        expected_owner = await self.db.scalar(
            select(Venue.owner_id)
            .join(PropertyListing, PropertyListing.venue_id == Venue.id)
            .where(PropertyListing.id == property_id)
        )
        if expected_owner is not None:
            await self.db.scalar(
                select(User.id)
                .where(User.id == expected_owner)
                .with_for_update(read=True, key_share=True)
            )
        listing = await self.db.scalar(
            select(PropertyListing)
            .where(PropertyListing.id == property_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if listing is None or not listing.is_published:
            raise HTTPException(404, "Property not found")
        if listing.offer_type != ("sale" if self.sale else "long_term"):
            raise HTTPException(400, "Inquiry type does not match the listing offer")
        owner_id = await self.db.scalar(
            select(Venue.owner_id).where(Venue.id == listing.venue_id)
        )
        if owner_id != expected_owner:
            raise HTTPException(409, "Listing ownership changed. Please retry")
        if owner_id == user.id:
            raise HTTPException(400, "You cannot inquire about your own property")
        if not self.sale:
            if data.move_in < datetime.now(ZoneInfo(listing.timezone)).date():
                raise HTTPException(400, "Move-in date cannot be in the past")
            if (
                listing.available_from is not None
                and data.move_in < listing.available_from
            ):
                raise HTTPException(
                    400, "Move-in date is before the listing is available"
                )
            if (
                listing.minimum_rental_months is not None
                and data.duration_months < listing.minimum_rental_months
            ):
                raise HTTPException(400, "Duration is below the minimum rental term")
        active = await self.db.scalar(
            select(self.inquiry_model.id).where(
                self.inquiry_model.user_id == user.id,
                self.inquiry_model.property_id == property_id,
                self.inquiry_model.status.notin_(["closed", "withdrawn"]),
            )
        )
        if active:
            raise HTTPException(
                409, "You already have an active inquiry for this property"
            )
        terms = (
            {"asking_price_cents": listing.price_cents}
            if self.sale
            else {
                **{
                    field: getattr(listing, field) for field in RentalTerms.model_fields
                },
                "monthly_price_cents": listing.price_cents,
                "move_in": data.move_in,
                "duration_months": data.duration_months,
            }
        )
        inquiry = self.inquiry_model(
            **terms,
            property_id=property_id,
            owner_id=owner_id,
            user_id=user.id,
            request_id=str(data.request_id),
            title=listing.title,
            currency=listing.currency,
            message=data.message,
        )
        self.db.add(inquiry)
        await self.db.flush()
        append_rental_message(
            self.db, inquiry, user.id, data.message, message_model=self.message_model
        )
        add_rental_notification(self.db, inquiry, user.id, "created", sale=self.sale)
        await self.db.commit()
        await self.db.refresh(inquiry)
        return inquiry

    async def list(self, user, owner=False, offset=0, limit=20):
        query = select(self.inquiry_model).where(
            (self.inquiry_model.owner_id if owner else self.inquiry_model.user_id)
            == user.id
        )
        total = await self.db.scalar(select(func.count()).select_from(query.subquery()))
        items = list(
            await self.db.scalars(
                query.order_by(self.inquiry_model.id.desc()).offset(offset).limit(limit)
            )
        )
        if items:
            unread = dict(
                (
                    await self.db.execute(
                        select(self.message_model.inquiry_id, func.count())
                        .where(
                            self.message_model.inquiry_id.in_(
                                [item.id for item in items]
                            ),
                            self.message_model.sender_id != user.id,
                            self.message_model.read_at.is_(None),
                        )
                        .group_by(self.message_model.inquiry_id)
                    )
                ).all()
            )
            items = [
                self.read_schema.model_validate(item).model_copy(
                    update={"unread_count": unread.get(item.id, 0)}
                )
                for item in items
            ]
        return {"items": items, "total": total, "has_next": offset + limit < total}

    async def update(self, inquiry_id, data, user):
        inquiry = await self.db.scalar(
            select(self.inquiry_model)
            .where(self.inquiry_model.id == inquiry_id)
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
        append_rental_message(
            self.db,
            inquiry,
            user.id,
            data.owner_reply,
            kind="message" if data.action == "reply" else data.action,
            viewing_at=data.viewing_at,
            message_model=self.message_model,
        )
        inquiry.version += 1
        if data.action != "reply":
            add_rental_notification(
                self.db, inquiry, user.id, data.action, sale=self.sale
            )
        await self.db.commit()
        await self.db.refresh(inquiry)
        return inquiry
