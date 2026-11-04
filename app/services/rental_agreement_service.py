import calendar
from datetime import UTC, date, datetime
from zoneinfo import ZoneInfo

from fastapi import HTTPException
from sqlalchemy import select

from app.core.config import settings
from app.models.notification import Notification
from app.models.property_listing import PropertyListing
from app.models.rental_agreement import RentalAgreement, RentalCharge, RentalChargeEvent
from app.models.rental_inquiry import RentalInquiry
from app.models.user import User
from app.models.venue import Venue


def month_date(start, offset):
    year, month = divmod(start.year * 12 + start.month - 1 + offset, 12)
    return date(
        year, month + 1, min(start.day, calendar.monthrange(year, month + 1)[1])
    )


class RentalAgreementService:
    def __init__(self, db):
        self.db = db

    @staticmethod
    def today(zone):
        return datetime.now(UTC).astimezone(ZoneInfo(zone)).date()

    def writable(self):
        if settings.DEMO_MODE:
            raise HTTPException(403, "Rental agreements are read-only in demo mode")

    async def inquiry(self, inquiry_id, user):
        row = await self.db.get(RentalInquiry, inquiry_id)
        if row is None or user.id not in (row.owner_id, row.user_id):
            raise HTTPException(404, "Inquiry not found")
        return row

    async def participants(self, owner_id, tenant_id):
        await self.db.scalars(
            select(User.id)
            .where(User.id.in_(sorted({owner_id, tenant_id})))
            .order_by(User.id)
            .with_for_update(read=True, key_share=True)
        )

    def notify(self, agreement, owner, title, message):
        self.db.add(
            Notification(
                user_id=agreement.owner_id if owner else agreement.tenant_id,
                title=title,
                message=f"Dogovor #{agreement.id}: {agreement.title}. {message}",
                action_path="/owner/rentals" if owner else "/rentals",
            )
        )

    async def list(self, inquiry_id, user, offset=0):
        await self.inquiry(inquiry_id, user)
        return list(
            (
                await self.db.scalars(
                    select(RentalAgreement)
                    .where(RentalAgreement.inquiry_id == inquiry_id)
                    .order_by(RentalAgreement.id.desc())
                    .offset(offset)
                    .limit(10)
                )
            ).all()
        )

    async def get(self, agreement_id, user, lock=False):
        row = await self.db.get(RentalAgreement, agreement_id)
        if row is None or user.id not in (row.owner_id, row.tenant_id):
            raise HTTPException(404, "Agreement not found")
        if lock:
            await self.participants(row.owner_id, row.tenant_id)
            await self.db.scalar(
                select(Venue).where(Venue.id == row.venue_id).with_for_update()
            )
            await self.db.scalar(
                select(RentalInquiry)
                .where(RentalInquiry.id == row.inquiry_id)
                .with_for_update()
                .execution_options(populate_existing=True)
            )
            row = await self.db.scalar(
                select(RentalAgreement)
                .where(RentalAgreement.id == agreement_id)
                .with_for_update()
                .execution_options(populate_existing=True)
            )
        return row

    async def create(self, inquiry_id, data, user):
        self.writable()
        inquiry = await self.inquiry(inquiry_id, user)
        if user.id != inquiry.owner_id:
            raise HTTPException(403, "Only the owner can propose an agreement")
        await self.db.scalar(
            select(User.id).where(User.id == user.id).with_for_update(key_share=True)
        )
        await self.participants(inquiry.owner_id, inquiry.user_id)
        listing = await self.db.scalar(
            select(PropertyListing)
            .where(PropertyListing.id == inquiry.property_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if listing is None:
            raise HTTPException(404, "Property not found")
        venue = await self.db.scalar(
            select(Venue).where(Venue.id == listing.venue_id).with_for_update()
        )
        inquiry = await self.db.scalar(
            select(RentalInquiry)
            .where(RentalInquiry.id == inquiry_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        previous = await self.db.scalar(
            select(RentalAgreement).where(
                RentalAgreement.owner_id == user.id,
                RentalAgreement.request_id == str(data.request_id),
            )
        )
        if previous:
            if previous.inquiry_id != inquiry_id or any(
                getattr(previous, field) != getattr(data, field)
                for field in (
                    "start_date",
                    "months",
                    "monthly_cents",
                    "deposit_cents",
                    "notes",
                )
            ):
                raise HTTPException(409, "Request identifier was already used")
            return previous
        if (
            venue.owner_id != user.id
            or listing.offer_type != "long_term"
            or inquiry.status in ("closed", "withdrawn")
        ):
            raise HTTPException(409, "This inquiry cannot receive an agreement")
        if data.start_date < self.today(listing.timezone):
            raise HTTPException(400, "Agreement cannot start in the past")
        try:
            end_date = month_date(data.start_date, data.months)
        except ValueError:
            raise HTTPException(
                400, "Agreement end date is outside the supported range"
            ) from None
        if await self.db.scalar(
            select(RentalAgreement.id).where(
                RentalAgreement.inquiry_id == inquiry_id,
                RentalAgreement.status.in_(("proposed", "accepted")),
            )
        ):
            raise HTTPException(
                409, "An active agreement already exists for this inquiry"
            )
        agreement = RentalAgreement(
            inquiry_id=inquiry_id,
            venue_id=venue.id,
            owner_id=user.id,
            tenant_id=inquiry.user_id,
            request_id=str(data.request_id),
            title=inquiry.title,
            currency=inquiry.currency,
            timezone=listing.timezone,
            end_date=end_date,
            **data.model_dump(exclude={"request_id"}),
            status="proposed",
            version=1,
        )
        self.db.add(agreement)
        await self.db.flush()
        self.notify(
            agreement,
            False,
            "Predlog dogovora o najmu",
            "Pregledaj uslove i prihvati ili odbij predlog.",
        )
        await self.db.commit()
        return agreement

    async def act(self, agreement_id, data, user):
        self.writable()
        agreement = await self.get(agreement_id, user, lock=True)
        expected = (
            agreement.owner_id if data.action == "withdraw" else agreement.tenant_id
        )
        if user.id != expected:
            raise HTTPException(403, "You cannot perform this action")
        if agreement.version != data.version or agreement.status != "proposed":
            raise HTTPException(409, "Agreement changed; refresh before continuing")
        if data.action == "accept":
            inquiry = await self.db.get(RentalInquiry, agreement.inquiry_id)
            venue = await self.db.get(Venue, agreement.venue_id)
            if venue.owner_id != agreement.owner_id or inquiry.status in (
                "closed",
                "withdrawn",
            ):
                raise HTTPException(409, "The proposal is no longer available")
            if agreement.start_date < self.today(agreement.timezone):
                raise HTTPException(409, "Ask the owner for a new start date")
            overlap = await self.db.scalar(
                select(RentalAgreement.id).where(
                    RentalAgreement.venue_id == agreement.venue_id,
                    RentalAgreement.status == "accepted",
                    RentalAgreement.start_date < agreement.end_date,
                    RentalAgreement.end_date > agreement.start_date,
                )
            )
            if overlap:
                raise HTTPException(
                    409, "Another accepted rental agreement covers these dates"
                )
            agreement.accepted_at = datetime.now(UTC)
            for index in range(agreement.months):
                self.db.add(
                    RentalCharge(
                        agreement_id=agreement.id,
                        sequence=index + 1,
                        due_date=month_date(agreement.start_date, index),
                        amount_cents=agreement.monthly_cents,
                    )
                )
            if agreement.deposit_cents:
                self.db.add(
                    RentalCharge(
                        agreement_id=agreement.id,
                        sequence=0,
                        due_date=agreement.start_date,
                        amount_cents=agreement.deposit_cents,
                    )
                )
        agreement.status = {
            "accept": "accepted",
            "decline": "declined",
            "withdraw": "withdrawn",
        }[data.action]
        agreement.version += 1
        titles = {
            "accept": "Dogovor o najmu je prihvaćen",
            "decline": "Predlog najma je odbijen",
            "withdraw": "Predlog najma je povučen",
        }
        self.notify(
            agreement,
            data.action != "withdraw",
            titles[data.action],
            "Otvori upit za detalje dogovora.",
        )
        await self.db.commit()
        return agreement

    async def charges(self, agreement_id, user):
        await self.get(agreement_id, user)
        return list(
            (
                await self.db.scalars(
                    select(RentalCharge)
                    .where(RentalCharge.agreement_id == agreement_id)
                    .order_by(RentalCharge.sequence)
                )
            ).all()
        )

    async def record_payment(self, agreement_id, charge_id, data, user):
        self.writable()
        agreement = await self.get(agreement_id, user, lock=True)
        if user.id != agreement.owner_id:
            raise HTTPException(403, "Only the owner can record payments")
        charge = await self.db.scalar(
            select(RentalCharge)
            .where(
                RentalCharge.id == charge_id, RentalCharge.agreement_id == agreement_id
            )
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if charge is None:
            raise HTTPException(404, "Charge not found")
        if agreement.status != "accepted" or charge.version != data.version:
            raise HTTPException(
                409, "Payment record changed; refresh before continuing"
            )
        if charge.paid != data.paid:
            charge.paid = data.paid
            charge.version += 1
            charge.updated_at = datetime.now(UTC)
            self.db.add(
                RentalChargeEvent(
                    charge_id=charge.id,
                    actor_id=user.id,
                    paid=data.paid,
                    version=charge.version,
                )
            )
            self.notify(
                agreement,
                False,
                "Promena evidencije uplate",
                "Vlasnik je ažurirao ručnu evidenciju kirije ili depozita. "
                "Proveri raspored.",
            )
        await self.db.commit()
        return charge

    async def events(self, agreement_id, charge_id, user):
        await self.get(agreement_id, user)
        charge = await self.db.get(RentalCharge, charge_id)
        if charge is None or charge.agreement_id != agreement_id:
            raise HTTPException(404, "Charge not found")
        return list(
            (
                await self.db.scalars(
                    select(RentalChargeEvent)
                    .where(RentalChargeEvent.charge_id == charge_id)
                    .order_by(RentalChargeEvent.id.desc())
                    .limit(20)
                )
            ).all()
        )
