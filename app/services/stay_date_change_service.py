from datetime import UTC, datetime

from fastapi import HTTPException
from sqlalchemy import func, select

from app.models.notification import Notification
from app.models.stay_date_change import StayDateChange
from app.models.user import User
from app.schemas.stay import StayDates, StayRead
from app.schemas.stay_date_change import StayDateChangePage, StayDateChangeRead
from app.services.stay_service import StayService


class StayDateChangeService:
    def __init__(self, db):
        self.db = db
        self.stays = StayService(db)
        self.repository = self.stays.repository

    async def authorize(self, stay_id, user, lock=False):
        stay = await self.repository.get(stay_id)
        if stay is None:
            raise HTTPException(404, "Reservation not found")
        owner_id = await self.repository.venue_owner_id(stay.venue_id)
        if user.id not in (stay.user_id, owner_id):
            raise HTTPException(404, "Reservation not found")
        if lock:
            # Acquire notification FK key locks before inventory locks. A booking
            # by either recipient locks its user first; reversing that order can
            # deadlock when our notification insert checks its user foreign key.
            await self.db.scalars(
                select(User.id)
                .where(User.id.in_([stay.user_id, owner_id]))
                .order_by(User.id)
                .with_for_update(read=True, key_share=True)
            )
            # Same inventory order as bookings and blocks, then the reservation.
            await self.repository.listing(stay.property_id, lock=True)
            venue = await self.repository.lock_venue(stay.venue_id)
            stay = await self.repository.get(stay_id, lock=True)
            owner_id = venue.owner_id
            if user.id not in (stay.user_id, owner_id):
                raise HTTPException(404, "Reservation not found")
        return stay, owner_id

    def active(self, stay, change=None):
        if stay.status != "confirmed" or stay.check_in <= self.stays.today(
            stay.timezone
        ):
            return False
        return change is None or (
            change.check_in > self.stays.today(change.quote["timezone"])
            and change.original["check_in"] == str(stay.check_in)
            and change.original["check_out"] == str(stay.check_out)
            and change.original["total_cents"] == stay.total_cents
            and change.original["currency"] == stay.currency
        )

    def read(self, stay, change):
        result = StayDateChangeRead.model_validate(change)
        if change.status == "pending" and not self.active(stay, change):
            result = result.model_copy(update={"status": "expired"})
        return result

    async def list(self, stay_id, user, offset=0, limit=20):
        stay, _ = await self.authorize(stay_id, user)
        query = select(StayDateChange).where(StayDateChange.stay_id == stay_id)
        total = await self.db.scalar(select(func.count()).select_from(query.subquery()))
        result = await self.db.scalars(
            query.order_by(StayDateChange.id.desc()).offset(offset).limit(limit)
        )
        return StayDateChangePage(
            items=[self.read(stay, item) for item in result.all()],
            total=total,
            has_next=offset + limit < total,
        )

    async def quote_for(self, stay, dates):
        if not self.active(stay):
            raise HTTPException(
                409, "Only confirmed stays before arrival can change dates"
            )
        if dates.guests != stay.guests:
            raise HTTPException(400, "Date changes must preserve the number of guests")
        if (dates.check_in, dates.check_out) == (stay.check_in, stay.check_out):
            raise HTTPException(400, "Choose different dates")
        listing = await self.stays.bookable_listing(stay.property_id)
        quote = self.stays.validate_dates(listing, dates)
        if await self.repository.occupied(
            stay.venue_id,
            dates.check_in,
            dates.check_out,
            preparation_days=await self.repository.preparation_days(stay.venue_id),
            exclude_stay_id=stay.id,
        ):
            raise HTTPException(409, "These dates are no longer available")
        return quote

    async def quote(self, stay_id, data, user):
        stay, _ = await self.authorize(stay_id, user)
        if stay.user_id != user.id:
            raise HTTPException(403, "Only the guest can request a date change")
        return await self.quote_for(stay, data)

    async def create(self, stay_id, data, user):
        stay, owner_id = await self.authorize(stay_id, user, lock=True)
        if user.id != stay.user_id:
            raise HTTPException(403, "Only the guest can request a date change")
        previous = await self.db.scalar(
            select(StayDateChange).where(
                StayDateChange.stay_id == stay_id,
                StayDateChange.request_id == str(data.request_id),
            )
        )
        if previous:
            if (
                previous.check_in,
                previous.check_out,
                previous.original["guests"],
                previous.quote,
            ) != (
                data.check_in,
                data.check_out,
                data.guests,
                data.quote.model_dump(mode="json"),
            ):
                raise HTTPException(409, "Request identifier already used")
            return self.read(stay, previous)
        pending = await self.db.scalar(
            select(StayDateChange).where(
                StayDateChange.stay_id == stay_id, StayDateChange.status == "pending"
            )
        )
        if pending:
            if self.active(stay, pending):
                raise HTTPException(
                    409, "Withdraw the pending request before making another"
                )
            pending.status = "expired"
            pending.resolved_at = datetime.now(UTC)
            await self.db.flush()
        quote = await self.quote_for(stay, data)
        if quote.model_dump(mode="json") != data.quote.model_dump(mode="json"):
            raise HTTPException(409, "Terms changed. Request a new quote")
        change = StayDateChange(
            stay_id=stay_id,
            request_id=str(data.request_id),
            check_in=data.check_in,
            check_out=data.check_out,
            quote=quote.model_dump(mode="json"),
            original=StayRead.model_validate(stay).model_dump(mode="json"),
            status="pending",
        )
        self.db.add(change)
        await self.db.flush()
        self.notify(stay, change, owner_id)
        await self.db.commit()
        await self.db.refresh(change)
        return self.read(stay, change)

    async def decide(self, stay_id, change_id, action, user):
        stay, owner_id = await self.authorize(stay_id, user, lock=True)
        if (action == "withdraw" and user.id != stay.user_id) or (
            action != "withdraw" and user.id != owner_id
        ):
            raise HTTPException(403, "This action is not available to you")
        change = await self.db.scalar(
            select(StayDateChange)
            .where(StayDateChange.id == change_id, StayDateChange.stay_id == stay_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if change is None:
            raise HTTPException(404, "Date change not found")
        target = {"accept": "accepted", "decline": "declined", "withdraw": "withdrawn"}[
            action
        ]
        if change.status == target:
            return self.read(stay, change)
        if change.status != "pending" or not self.active(stay, change):
            raise HTTPException(409, "This date change is no longer pending")
        if action == "accept":
            dates = StayDates(
                check_in=change.check_in, check_out=change.check_out, guests=stay.guests
            )
            quote = await self.quote_for(stay, dates)
            if quote.model_dump(mode="json") != change.quote:
                raise HTTPException(
                    409, "Terms changed. The guest must submit a new request"
                )
            stay.check_in, stay.check_out = change.check_in, change.check_out
            for field in (
                "nightly_prices",
                "nightly_rate_cents",
                "total_cents",
                "currency",
                "timezone",
                "check_in_time",
                "check_out_time",
            ):
                setattr(stay, field, change.quote[field])
        change.status = target
        change.resolved_at = datetime.now(UTC)
        self.notify(stay, change, owner_id)
        await self.db.commit()
        await self.db.refresh(change)
        return self.read(stay, change)

    def notify(self, stay, change, owner_id):
        titles = {
            "pending": "Zahtev za promenu termina",
            "accepted": "Promena termina je odobrena",
            "declined": "Promena termina je odbijena",
            "withdrawn": "Zahtev za promenu termina je povučen",
        }
        for user_id, path in ((stay.user_id, "/stays"), (owner_id, "/owner/stays")):
            self.db.add(
                Notification(
                    user_id=user_id,
                    title=titles[change.status],
                    message=(
                        f"Rezervacija #{stay.id}: {stay.title}. Predloženi termin: "
                        f"{change.check_in:%d.%m.%Y.} – {change.check_out:%d.%m.%Y.}. "
                        "Otvori promene termina uz rezervaciju za detalje."
                    ),
                    action_path=path,
                    deduplication_key=f"stay-change:{change.id}:{change.status}:user:{user_id}",
                )
            )
